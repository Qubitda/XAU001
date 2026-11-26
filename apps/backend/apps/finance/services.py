from decimal import Decimal
from django.db import transaction
from apps.organizations.models import Organization
from config.exceptions import DomainError
from .models import DealerLedgerEntry


@transaction.atomic
def reserve_organization_limits(
    *,
    organization_id,
    settlement_method: str,
    total_has_gold_gram: Decimal,
    total_labor_and_stone_usd: Decimal,
    total_wholesale_usd: Decimal,
    reference_no: str,
    actor=None,
) -> Organization:
    """
    Concurrency-safe & idempotent credit & has-gold limit validation and ledger debit
    using row-level locking on Organization.
    Same (organization, reference_no, ORDER_DEBIT) will NEVER double-deduct limits.
    """
    org = Organization.objects.select_for_update().get(id=organization_id)

    # Idempotency guard: if this order was already debited, return immediately without re-charging.
    existing = DealerLedgerEntry.objects.filter(
        organization=org,
        reference_no=reference_no,
        entry_type=DealerLedgerEntry.EntryType.ORDER_DEBIT,
    ).first()
    if existing is not None:
        return org

    usd_debit = Decimal("0.00")
    has_debit = Decimal("0.0000")

    if settlement_method == "HAS_PLUS_CURRENCY":
        if org.used_has_gram + total_has_gold_gram > org.has_limit_gram:
            raise DomainError(
                f"Firma Has Altın limiti aşılıyor (Kalan: {org.remaining_has_gram} gr, Talep: {total_has_gold_gram} gr).",
                code="HAS_LIMIT_EXCEEDED",
                status_code=409,
            )
        if org.used_credit_usd + total_labor_and_stone_usd > org.credit_limit_usd:
            raise DomainError(
                f"Firma döviz işçilik/taş kredi limiti aşılıyor (Kalan: {org.remaining_credit_usd} USD).",
                code="CREDIT_LIMIT_EXCEEDED",
                status_code=409,
            )
        usd_debit = total_labor_and_stone_usd
        has_debit = total_has_gold_gram
    elif settlement_method in ("OPEN_ACCOUNT", "CONSIGNMENT"):
        if org.used_credit_usd + total_wholesale_usd > org.credit_limit_usd:
            raise DomainError(
                f"Firma açık hesap / konsinye kredi limiti aşılıyor (Kalan: {org.remaining_credit_usd} USD, Talep: {total_wholesale_usd} USD).",
                code="CREDIT_LIMIT_EXCEEDED",
                status_code=409,
            )
        usd_debit = total_wholesale_usd
    else:
        # FX_CASH: settled upfront in cash/wire; still records immutable ledger entry with zero credit usage
        usd_debit = Decimal("0.00")
        has_debit = Decimal("0.0000")

    org.used_credit_usd += usd_debit
    org.used_has_gram += has_debit
    org.save(update_fields=["used_credit_usd", "used_has_gram", "updated_at"])

    DealerLedgerEntry.objects.create(
        organization=org,
        entry_type=DealerLedgerEntry.EntryType.ORDER_DEBIT,
        reference_no=reference_no,
        amount_usd=usd_debit,
        has_gold_gram=has_debit,
        note=f"B2B sipariş ({settlement_method})",
        created_by=actor,
    )
    return org


@transaction.atomic
def reverse_organization_limits(
    *,
    organization_id,
    reference_no: str,
    entry_type: str = DealerLedgerEntry.EntryType.ORDER_REVERSAL,
    note: str = "",
    actor=None,
) -> Organization:
    """
    Idempotent counter-entry mechanism for cancelled or refunded B2B orders.
    Reverses the original ORDER_DEBIT once and safely restores credit & has-gold limits.
    """
    if entry_type not in (
        DealerLedgerEntry.EntryType.ORDER_REVERSAL,
        DealerLedgerEntry.EntryType.REFUND_CREDIT,
    ):
        raise DomainError("Geçersiz ters kayıt türü.", code="INVALID_REVERSAL_TYPE", status_code=400)

    org = Organization.objects.select_for_update().get(id=organization_id)

    already_reversed = DealerLedgerEntry.objects.filter(
        organization=org,
        reference_no=reference_no,
        entry_type__in=[
            DealerLedgerEntry.EntryType.ORDER_REVERSAL,
            DealerLedgerEntry.EntryType.REFUND_CREDIT,
        ],
    ).exists()
    if already_reversed:
        return org

    debit = DealerLedgerEntry.objects.filter(
        organization=org,
        reference_no=reference_no,
        entry_type=DealerLedgerEntry.EntryType.ORDER_DEBIT,
    ).first()
    if debit is None:
        return org

    org.used_credit_usd = max(Decimal("0.00"), org.used_credit_usd - debit.amount_usd)
    org.used_has_gram = max(Decimal("0.0000"), org.used_has_gram - debit.has_gold_gram)
    org.save(update_fields=["used_credit_usd", "used_has_gram", "updated_at"])

    DealerLedgerEntry.objects.create(
        organization=org,
        entry_type=entry_type,
        reference_no=reference_no,
        amount_usd=-debit.amount_usd,
        has_gold_gram=-debit.has_gold_gram,
        note=note or f"Sipariş ters kayıt ({entry_type})",
        created_by=actor,
    )
    return org


@transaction.atomic
def record_dealer_ledger_settlement(
    *,
    organization_id,
    entry_type: str,
    reference_no: str,
    amount_usd: Decimal = Decimal("0.00"),
    has_gold_gram: Decimal = Decimal("0.0000"),
    note: str = "",
    actor=None,
) -> tuple[DealerLedgerEntry, bool]:
    """
    Idempotent OPS finance ledger posting for dealer settlements & adjustments:
    - PAYMENT_CREDIT: reduces Organization.used_credit_usd by amount_usd (stored as negative credit entry).
    - HAS_DELIVERY: reduces Organization.used_has_gram by has_gold_gram (stored as negative credit entry).
    - ORDER_REVERSAL / REFUND_CREDIT: delegates to reverse_organization_limits() when order debit exists,
      otherwise records an explicit credit entry and restores limits.
    Returns (entry, created).
    """
    from apps.audit.services import record_audit

    allowed_ops_types = {
        DealerLedgerEntry.EntryType.PAYMENT_CREDIT,
        DealerLedgerEntry.EntryType.HAS_DELIVERY,
        DealerLedgerEntry.EntryType.ORDER_REVERSAL,
        DealerLedgerEntry.EntryType.REFUND_CREDIT,
    }
    if entry_type not in allowed_ops_types:
        raise DomainError(
            "OPS üzerinden yalnızca PAYMENT_CREDIT, HAS_DELIVERY, ORDER_REVERSAL veya REFUND_CREDIT kaydı işlenebilir.",
            code="INVALID_LEDGER_ENTRY_TYPE",
            status_code=400,
        )

    ref = reference_no.strip()
    if not ref:
        raise DomainError("Referans numarası (referenceNo) zorunludur.", code="REFERENCE_REQUIRED", status_code=400)

    org = Organization.objects.select_for_update().filter(id=organization_id).first()
    if org is None:
        raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)

    existing = DealerLedgerEntry.objects.filter(
        organization=org,
        reference_no=ref,
        entry_type=entry_type,
    ).first()
    if existing is not None:
        return existing, False

    if entry_type in (
        DealerLedgerEntry.EntryType.ORDER_REVERSAL,
        DealerLedgerEntry.EntryType.REFUND_CREDIT,
    ):
        existing_reversal = DealerLedgerEntry.objects.filter(
            organization=org,
            reference_no=ref,
            entry_type__in=[
                DealerLedgerEntry.EntryType.ORDER_REVERSAL,
                DealerLedgerEntry.EntryType.REFUND_CREDIT,
            ],
        ).first()
        if existing_reversal is not None:
            return existing_reversal, False

        has_debit = DealerLedgerEntry.objects.filter(
            organization=org,
            reference_no=ref,
            entry_type=DealerLedgerEntry.EntryType.ORDER_DEBIT,
        ).exists()
        if has_debit:
            reverse_organization_limits(
                organization_id=org.id,
                reference_no=ref,
                entry_type=entry_type,
                note=note,
                actor=actor,
            )
            entry = DealerLedgerEntry.objects.get(
                organization=org, reference_no=ref, entry_type=entry_type
            )
            record_audit(
                action="DEALER_LEDGER_POSTED",
                entity_type="DealerLedgerEntry",
                entity_id=str(entry.id),
                actor=actor,
                organization=org,
                metadata={
                    "entry_type": entry_type,
                    "reference_no": ref,
                    "amount_usd": str(entry.amount_usd),
                    "has_gold_gram": str(entry.has_gold_gram),
                },
            )
            return entry, True

    abs_usd = abs(Decimal(str(amount_usd or "0.00")))
    abs_has = abs(Decimal(str(has_gold_gram or "0.0000")))

    if entry_type == DealerLedgerEntry.EntryType.PAYMENT_CREDIT and abs_usd <= 0:
        raise DomainError(
            "PAYMENT_CREDIT kaydı için pozitif bir amountUsd değeri girilmelidir.",
            code="INVALID_AMOUNT",
            status_code=400,
        )
    if entry_type == DealerLedgerEntry.EntryType.HAS_DELIVERY and abs_has <= 0:
        raise DomainError(
            "HAS_DELIVERY kaydı için pozitif bir hasGoldGram değeri girilmelidir.",
            code="INVALID_AMOUNT",
            status_code=400,
        )
    if abs_usd <= 0 and abs_has <= 0:
        raise DomainError(
            "En az bir tutar (amountUsd veya hasGoldGram) sıfırdan büyük olmalıdır.",
            code="INVALID_AMOUNT",
            status_code=400,
        )

    org.used_credit_usd = max(Decimal("0.00"), org.used_credit_usd - abs_usd)
    org.used_has_gram = max(Decimal("0.0000"), org.used_has_gram - abs_has)
    org.save(update_fields=["used_credit_usd", "used_has_gram", "updated_at"])

    entry = DealerLedgerEntry.objects.create(
        organization=org,
        entry_type=entry_type,
        reference_no=ref,
        amount_usd=-abs_usd if abs_usd > 0 else Decimal("0.00"),
        has_gold_gram=-abs_has if abs_has > 0 else Decimal("0.0000"),
        note=note.strip()[:240],
        created_by=actor,
    )
    record_audit(
        action="DEALER_LEDGER_POSTED",
        entity_type="DealerLedgerEntry",
        entity_id=str(entry.id),
        actor=actor,
        organization=org,
        metadata={
            "entry_type": entry_type,
            "reference_no": ref,
            "amount_usd": str(entry.amount_usd),
            "has_gold_gram": str(entry.has_gold_gram),
        },
    )
    return entry, True

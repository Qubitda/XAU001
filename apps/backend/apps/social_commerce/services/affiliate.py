from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction

from apps.integrations.models import IntegrationEvent

from ..models import AffiliateCode, AffiliateConversion


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def record_affiliate_conversion(
    *,
    code_str: str,
    order_no: str,
    gross_amount_try: Decimal,
    net_amount_try: Decimal,
    audience: str = "B2C",
) -> AffiliateConversion | None:
    if not code_str or not order_no:
        return None
    ac = AffiliateCode.objects.filter(code__iexact=code_str.strip(), is_active=True).first()
    if ac is None:
        return None
    existing = AffiliateConversion.objects.filter(affiliate_code=ac, order_no=order_no).first()
    if existing is not None:
        return existing
    net_clamped = _q2(max(Decimal("0.00"), Decimal(net_amount_try)))
    gross_clamped = _q2(max(Decimal("0.00"), Decimal(gross_amount_try)))
    commission = _q2(net_clamped * ac.commission_pct / Decimal("100.00"))
    try:
        return AffiliateConversion.objects.create(
            affiliate_code=ac,
            order_no=order_no,
            audience=audience,
            gross_amount_try=gross_clamped,
            net_amount_try=net_clamped,
            commission_amount_try=commission,
            status=AffiliateConversion.Status.APPROVED,
        )
    except IntegrityError:
        return AffiliateConversion.objects.filter(affiliate_code=ac, order_no=order_no).first()


@transaction.atomic
def adjust_affiliate_conversion_for_partial_refund(
    *,
    order_no: str,
    refunded_amount_try: Decimal,
    refund_reference: str = "",
) -> int:
    """
    Recalculate net_amount_try & commission on partial refund; cancel if net reaches 0.
    Idempotent when refund_reference is supplied (prevents duplicate deductions).
    """
    refund_amt = _q2(max(Decimal("0.00"), Decimal(refunded_amount_try)))
    if not order_no or refund_amt <= Decimal("0.00"):
        return 0
    ref_clean = (refund_reference or "").strip()
    if ref_clean:
        idem_key = f"social:aff_partial_refund:{order_no}:{ref_clean}"[:128]
        try:
            with transaction.atomic():
                IntegrationEvent.objects.create(
                    event_id=idem_key,
                    source_system=IntegrationEvent.SourceSystem.EXTERNAL,
                    event_type="social.affiliate.partial_refund",
                    idempotency_key=idem_key,
                    payload={"orderNo": order_no, "refundedAmountTry": str(refund_amt)},
                    status=IntegrationEvent.Status.PROCESSED,
                )
        except IntegrityError:
            return 0
    rows = (
        AffiliateConversion.objects.select_for_update()
        .select_related("affiliate_code")
        .filter(order_no=order_no)
        .exclude(status=AffiliateConversion.Status.CANCELLED_REFUNDED)
    )
    updated = 0
    for conv in rows:
        new_net = _q2(max(Decimal("0.00"), conv.net_amount_try - refund_amt))
        conv.net_amount_try = new_net
        if new_net <= Decimal("0.00"):
            conv.commission_amount_try = Decimal("0.00")
            conv.status = AffiliateConversion.Status.CANCELLED_REFUNDED
        else:
            conv.commission_amount_try = _q2(new_net * conv.affiliate_code.commission_pct / Decimal("100.00"))
        conv.save(update_fields=["net_amount_try", "commission_amount_try", "status", "updated_at"])
        updated += 1
    return updated


@transaction.atomic
def mark_affiliate_conversion_refunded(order_no: str) -> int:
    return AffiliateConversion.objects.filter(order_no=order_no).update(
        net_amount_try=Decimal("0.00"),
        commission_amount_try=Decimal("0.00"),
        status=AffiliateConversion.Status.CANCELLED_REFUNDED,
    )

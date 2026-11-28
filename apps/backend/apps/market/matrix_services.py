"""Service layer for versioned central ExchangeMetalMatrix & ExchangeMetalRate."""

from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit.services import record_audit
from apps.common.units import TROY_OZ_TO_GRAM
from config.exceptions import DomainError
from .models import ExchangeMetalMatrix, ExchangeMetalRate
from .services import DEFAULT_FX_BASE_RATES, create_rate_snapshot, get_current_rate_snapshot

REQUIRED_MATRIX_CODES: tuple[str, ...] = (
    "TRY",
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "CNY",
    "AUD",
    "CAD",
    "CHF",
    "XAU",
    "XAG",
    "XPT",
    "XPD",
)
PRECIOUS_METAL_CODES: frozenset[str] = frozenset({"XAU", "XAG", "XPT", "XPD"})


def _normalize_rates_payload(rates_map: dict[str, Decimal | str | int | float]) -> dict[str, Decimal]:
    normalized: dict[str, Decimal] = {}
    for code in REQUIRED_MATRIX_CODES:
        if code == "TRY":
            normalized["TRY"] = Decimal("1.0000")
            continue
        raw = rates_map.get(code)
        if raw is None:
            raise DomainError(
                f"Eksik kur/metal referans değeri: {code}",
                code="MATRIX_MISSING_RATE",
                status_code=400,
            )
        val = Decimal(str(raw))
        if val <= 0:
            raise DomainError(
                f"{code} referans değeri sıfır veya negatif olamaz.",
                code="MATRIX_INVALID_RATE",
                status_code=400,
            )
        normalized[code] = val.quantize(Decimal("0.0001"))
    return normalized


@transaction.atomic
def get_or_create_active_matrix(*, organization=None, actor=None) -> ExchangeMetalMatrix:
    qs = ExchangeMetalMatrix.objects.prefetch_related("rates")
    if organization is not None:
        matrix = qs.filter(organization=organization, status=ExchangeMetalMatrix.Status.ACTIVE).first()
        if matrix is not None:
            return matrix
    matrix = qs.filter(organization__isnull=True, status=ExchangeMetalMatrix.Status.ACTIVE).first()
    if matrix is not None:
        return matrix

    snap = get_current_rate_snapshot()
    base_rates = {**DEFAULT_FX_BASE_RATES, **(snap.fx_base_rates or {})}
    normalized = _normalize_rates_payload(base_rates)
    matrix = ExchangeMetalMatrix.objects.create(
        organization=None,
        version=1,
        status=ExchangeMetalMatrix.Status.ACTIVE,
        effective_at=snap.created_at,
        created_by=actor,
        note="Otomatik başlangıç matrisi",
    )
    for code, val in normalized.items():
        ExchangeMetalRate.objects.create(
            matrix=matrix,
            currency_code=code,
            base_value_try=val,
            unit=(
                ExchangeMetalRate.Unit.TROY_OZ
                if code in PRECIOUS_METAL_CODES
                else ExchangeMetalRate.Unit.UNIT
            ),
            precision=4,
        )
    return ExchangeMetalMatrix.objects.prefetch_related("rates").get(id=matrix.id)


@transaction.atomic
def create_matrix_draft(
    rates_map: dict[str, Decimal | str | int | float],
    *,
    organization=None,
    actor=None,
    note: str = "",
) -> ExchangeMetalMatrix:
    normalized = _normalize_rates_payload(rates_map)
    scope_qs = (
        ExchangeMetalMatrix.objects.select_for_update().filter(organization=organization)
        if organization is not None
        else ExchangeMetalMatrix.objects.select_for_update().filter(organization__isnull=True)
    )
    max_ver = scope_qs.aggregate(m=Max("version")).get("m") or 0
    matrix = ExchangeMetalMatrix.objects.create(
        organization=organization,
        version=max_ver + 1,
        status=ExchangeMetalMatrix.Status.DRAFT,
        created_by=actor,
        note=(note or "").strip()[:240],
    )
    for code, val in normalized.items():
        ExchangeMetalRate.objects.create(
            matrix=matrix,
            currency_code=code,
            base_value_try=val,
            unit=(
                ExchangeMetalRate.Unit.TROY_OZ
                if code in PRECIOUS_METAL_CODES
                else ExchangeMetalRate.Unit.UNIT
            ),
            precision=4,
        )
    record_audit(
        action="EXCHANGE_METAL_MATRIX_DRAFT_CREATED",
        entity_type="ExchangeMetalMatrix",
        entity_id=str(matrix.id),
        actor=actor,
        organization=organization,
        metadata={"version": matrix.version},
    )
    return ExchangeMetalMatrix.objects.prefetch_related("rates").get(id=matrix.id)


@transaction.atomic
def publish_matrix_version(matrix_id: str, *, actor=None) -> tuple[ExchangeMetalMatrix, object]:
    matrix = (
        ExchangeMetalMatrix.objects.select_for_update()
        .prefetch_related("rates")
        .filter(id=matrix_id)
        .first()
    )
    if matrix is None:
        raise DomainError("Matris versiyonu bulunamadı.", code="NOT_FOUND", status_code=404)

    rate_rows = {r.currency_code: r.base_value_try for r in matrix.rates.all()}
    normalized = _normalize_rates_payload(rate_rows)

    scope_qs = (
        ExchangeMetalMatrix.objects.select_for_update().filter(organization=matrix.organization)
        if matrix.organization_id is not None
        else ExchangeMetalMatrix.objects.select_for_update().filter(organization__isnull=True)
    )
    scope_qs.filter(status=ExchangeMetalMatrix.Status.ACTIVE).exclude(id=matrix.id).update(
        status=ExchangeMetalMatrix.Status.ARCHIVED
    )
    now = timezone.now()
    matrix.status = ExchangeMetalMatrix.Status.ACTIVE
    matrix.effective_at = now
    matrix.save(update_fields=["status", "effective_at", "updated_at"])

    has_gold = (normalized["XAU"] / TROY_OZ_TO_GRAM).quantize(Decimal("0.01"))
    snap = create_rate_snapshot(
        fx_base_rates=normalized,
        source_mode="manual",
        live_has_gold_try_sell=has_gold,
        actor=actor,
    )
    record_audit(
        action="EXCHANGE_METAL_MATRIX_PUBLISHED",
        entity_type="ExchangeMetalMatrix",
        entity_id=str(matrix.id),
        actor=actor,
        organization=matrix.organization,
        metadata={"version": matrix.version, "snapshotCode": snap.snapshot_code},
    )
    return matrix, snap


def serialize_exchange_metal_matrix(matrix: ExchangeMetalMatrix) -> dict:
    rates_list = []
    fx_base_rates: dict[str, str] = {}
    for r in matrix.rates.all():
        fx_base_rates[r.currency_code] = str(r.base_value_try)
        rates_list.append(
            {
                "id": str(r.id),
                "currencyCode": r.currency_code,
                "baseValueTry": str(r.base_value_try),
                "unit": r.unit,
                "precision": r.precision,
            }
        )
    xau = Decimal(fx_base_rates.get("XAU", "168000.0000"))
    has_gold = (xau / TROY_OZ_TO_GRAM).quantize(Decimal("0.01"))
    return {
        "id": str(matrix.id),
        "organizationId": str(matrix.organization_id) if matrix.organization_id else None,
        "version": matrix.version,
        "status": matrix.status,
        "effectiveAt": matrix.effective_at.isoformat() if matrix.effective_at else None,
        "createdByEmail": matrix.created_by.email if matrix.created_by else None,
        "note": matrix.note,
        "liveHasGoldTrySell": str(has_gold),
        "fxBaseRates": fx_base_rates,
        "rates": rates_list,
        "createdAt": matrix.created_at.isoformat(),
        "updatedAt": matrix.updated_at.isoformat(),
    }

import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record_audit
from apps.common.units import TROY_OZ_TO_GRAM
from .models import RateSnapshot

DEFAULT_FX_BASE_RATES: dict[str, str] = {
    "TRY": "1",
    "USD": "42.00",
    "EUR": "48.50",
    "JPY": "0.28",
    "GBP": "56.00",
    "CNY": "5.80",
    "AUD": "27.30",
    "CAD": "30.40",
    "CHF": "52.00",
    "XAU": "168000.00",
    "XAG": "1470.00",
    "XPT": "42000.00",
    "XPD": "44100.00",
}


def get_current_rate_snapshot() -> RateSnapshot:
    snap = RateSnapshot.objects.filter(is_current=True).order_by("-created_at").first()
    if snap is not None:
        return snap
    return create_rate_snapshot(fx_base_rates=DEFAULT_FX_BASE_RATES, source_mode=RateSnapshot.SourceMode.AUTO)


@transaction.atomic
def create_rate_snapshot(
    *,
    fx_base_rates: dict[str, str | float | Decimal],
    source_mode: str = RateSnapshot.SourceMode.MANUAL,
    live_has_gold_try_sell: Decimal | None = None,
    actor=None,
) -> RateSnapshot:
    normalized = {k.upper(): str(Decimal(str(v))) for k, v in fx_base_rates.items()}
    normalized.setdefault("TRY", "1")

    usd = Decimal(normalized.get("USD", "42.00"))
    eur = Decimal(normalized.get("EUR", "48.50"))
    if live_has_gold_try_sell is not None:
        has_gold = Decimal(str(live_has_gold_try_sell))
        normalized["XAU"] = str((has_gold * TROY_OZ_TO_GRAM).quantize(Decimal("0.01")))
    else:
        xau = Decimal(normalized.get("XAU", "168000.00"))
        has_gold = (xau / TROY_OZ_TO_GRAM).quantize(Decimal("0.01"))

    RateSnapshot.objects.filter(is_current=True).update(is_current=False)
    code = f"SNP-{timezone.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    snap = RateSnapshot.objects.create(
        snapshot_code=code,
        source_mode=source_mode,
        live_usd_sell=usd,
        live_eur_sell=eur,
        live_has_gold_try_sell=has_gold,
        fx_base_rates=normalized,
        is_current=True,
    )
    record_audit(
        action="MARKET_RATE_SNAPSHOT_CREATED",
        entity_type="RateSnapshot",
        entity_id=snap.snapshot_code,
        actor=actor,
        metadata={"source_mode": source_mode, "has_gold_try": str(has_gold), "usd": str(usd)},
    )
    return snap

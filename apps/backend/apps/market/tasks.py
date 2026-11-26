import logging

from celery import shared_task
from django.conf import settings

from .models import RateSnapshot
from .services import create_rate_snapshot, get_current_rate_snapshot

logger = logging.getLogger(__name__)


def _fetch_external_fx_rates(feed_url: str) -> dict[str, str] | None:
    """
    Optional JSON feed:
      {"USD": "42.10", "EUR": "48.80", "XAU": "168500.00", ...}
    or {"rates": {...}}
    """
    from urllib import request as urlrequest
    import json

    try:
        with urlrequest.urlopen(feed_url, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.exception("Market rates feed fetch failed: %s", feed_url)
        return None

    if isinstance(payload, dict) and isinstance(payload.get("rates"), dict):
        payload = payload["rates"]
    if not isinstance(payload, dict):
        return None
    return {str(k).upper(): str(v) for k, v in payload.items()}


@shared_task(
    name="market.refresh_rates_snapshot",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def refresh_market_rates_snapshot(self) -> str:
    """
    Periodic FX/bullion refresh.
    - If MARKET_RATES_FEED_URL is set → fetch and create a new AUTO snapshot.
    - Else if MARKET_RATES_REFRESH_CLONE=1 → clone current rates into a fresh snapshot.
    - Else → no-op (schedule still owned; waits for feed configuration).
    """
    try:
        feed_url = (getattr(settings, "MARKET_RATES_FEED_URL", "") or "").strip()
        if feed_url:
            rates = _fetch_external_fx_rates(feed_url)
            if not rates:
                raise RuntimeError("Market rates feed returned no usable payload")
            snap = create_rate_snapshot(
                fx_base_rates=rates, source_mode=RateSnapshot.SourceMode.AUTO
            )
            logger.info("Created market snapshot from feed: %s", snap.snapshot_code)
            return snap.snapshot_code

        if getattr(settings, "MARKET_RATES_REFRESH_CLONE", False):
            current = get_current_rate_snapshot()
            snap = create_rate_snapshot(
                fx_base_rates=current.get_decimal_rates(),
                source_mode=RateSnapshot.SourceMode.AUTO,
                live_has_gold_try_sell=current.live_has_gold_try_sell,
            )
            logger.info("Cloned market snapshot: %s", snap.snapshot_code)
            return snap.snapshot_code

        current = get_current_rate_snapshot()
        logger.info(
            "market.refresh_rates_snapshot idle (no MARKET_RATES_FEED_URL); current=%s",
            current.snapshot_code,
        )
        return current.snapshot_code
    except Exception:
        logger.exception("refresh_market_rates_snapshot failed (attempt %s)", self.request.retries + 1)
        raise

import logging
from celery import shared_task
from django.utils import timezone
from .models import PriceLock

logger = logging.getLogger(__name__)


@shared_task(
    name="pricing.cleanup_expired_price_locks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def cleanup_expired_price_locks(self) -> int:
    try:
        return PriceLock.objects.filter(is_active=True, expires_at__lte=timezone.now()).update(
            is_active=False
        )
    except Exception:
        logger.exception("cleanup_expired_price_locks failed (attempt %s)", self.request.retries + 1)
        raise

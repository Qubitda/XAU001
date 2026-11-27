from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import SocialCatalog, SocialPostChannel
from .services import publish_post_to_channel, refresh_post_publish_status, sync_social_catalog

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="social_commerce.sync_catalog",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def sync_social_catalog_task(self, catalog_id: str) -> dict:
    catalog = (
        SocialCatalog.objects.select_related("channel", "channel__connection")
        .filter(id=catalog_id, is_active=True)
        .first()
    )
    if catalog is None:
        return {"ok": False, "error": "CATALOG_NOT_FOUND"}
    try:
        return sync_social_catalog(catalog)
    except Exception as exc:
        logger.exception("sync_social_catalog_task failed catalog=%s", catalog_id)
        raise exc


@shared_task(
    bind=True,
    name="social_commerce.publish_due_posts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def publish_due_social_posts_task(self) -> dict:
    now = timezone.now()
    due = SocialPostChannel.objects.select_related("post", "channel", "channel__connection").filter(
        publish_status=SocialPostChannel.PublishStatus.SCHEDULED,
        scheduled_at__lte=now,
    )[:50]
    processed = 0
    failed = 0
    last_exc: Exception | None = None
    for target in due:
        try:
            publish_post_to_channel(target)
            processed += 1
        except Exception as exc:
            failed += 1
            last_exc = exc
            logger.exception("publish_due_social_posts_task failed target=%s", target.id)
    if last_exc is not None:
        raise last_exc
    return {"processed": processed, "failed": failed}


@shared_task(
    bind=True,
    name="social_commerce.poll_publishing_posts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def poll_publishing_social_posts_task(self) -> dict:
    """Poll async PUBLISHING targets (e.g. TikTok) and promote to PUBLISHED/FAILED."""
    targets = SocialPostChannel.objects.select_related("post", "channel", "channel__connection").filter(
        publish_status=SocialPostChannel.PublishStatus.PUBLISHING,
    )[:50]
    polled = 0
    last_exc: Exception | None = None
    for target in targets:
        try:
            refresh_post_publish_status(target)
            polled += 1
        except Exception as exc:
            last_exc = exc
            logger.exception("poll_publishing_social_posts_task failed target=%s", target.id)
    if last_exc is not None:
        raise last_exc
    return {"polled": polled}

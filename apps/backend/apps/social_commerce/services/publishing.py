from __future__ import annotations

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit

from ..adapters import get_adapter
from ..models import SocialPostChannel
from .oauth import SocialCommerceError, decrypt_connection_token

PUBLISH_LOCK_TTL = 120


def publish_post_to_channel(target: SocialPostChannel, *, actor=None) -> SocialPostChannel:
    """
    Publish a SocialPostChannel safely:
    - Uses cache lock to prevent concurrent duplicate publishes.
    - Executes external HTTP call OUTSIDE any database transaction.
    - Uses short transaction.atomic() only for persisting the result.
    """
    lock_key = f"soc_post_pub_lock:{target.id}"
    if not cache.add(lock_key, "1", timeout=PUBLISH_LOCK_TTL):
        raise SocialCommerceError(
            "Bu gönderi için yayınlama zaten devam ediyor.",
            code="PUBLISH_IN_PROGRESS",
            status_code=409,
        )

    try:
        channel = target.channel
        post = target.post
        adapter = get_adapter(channel.platform)
        conn = getattr(channel, "connection", None)
        token = decrypt_connection_token(conn)

        caption = post.caption
        if post.hashtags:
            tags = " ".join(h if str(h).startswith("#") else f"#{h}" for h in post.hashtags)
            caption = f"{caption}\n\n{tags}".strip()

        # External HTTP call outside DB transaction
        res = adapter.publish_post(
            access_token=token,
            external_account_id=channel.external_account_id,
            post_type=post.post_type,
            caption=caption,
            media_urls=list(post.media_urls or []),
            target_url=post.target_url,
        )

        with transaction.atomic():
            if res.ok and res.status == "PUBLISHING":
                target.publish_status = SocialPostChannel.PublishStatus.PUBLISHING
                target.external_post_id = res.external_id
                target.error_message = ""
            elif res.ok:
                target.publish_status = SocialPostChannel.PublishStatus.PUBLISHED
                target.published_at = timezone.now()
                target.external_post_id = res.external_id
                target.external_url = res.external_url
                target.error_message = ""
            elif res.status in ("MANUAL_REQUIRED", "NOT_CONFIGURED"):
                target.publish_status = SocialPostChannel.PublishStatus.MANUAL_REQUIRED
                target.error_message = res.error
            else:
                target.publish_status = SocialPostChannel.PublishStatus.FAILED
                target.retry_count += 1
                target.error_message = res.error
            target.save()

            record_audit(
                actor=actor,
                action="social.post.publish_attempted",
                entity_type="SocialPostChannel",
                entity_id=str(target.id),
                metadata={"platform": channel.platform, "status": target.publish_status},
            )
        return target
    finally:
        cache.delete(lock_key)


def refresh_post_publish_status(target: SocialPostChannel) -> SocialPostChannel:
    """Verify async publish completion outside DB transaction, then persist."""
    if target.publish_status != SocialPostChannel.PublishStatus.PUBLISHING:
        return target
    adapter = get_adapter(target.channel.platform)
    checker = getattr(adapter, "check_publish_status", None)
    if checker is None:
        return target
    token = decrypt_connection_token(getattr(target.channel, "connection", None))
    res = checker(access_token=token, publish_id=target.external_post_id)

    with transaction.atomic():
        if res.ok and res.status == "PUBLISHED":
            target.publish_status = SocialPostChannel.PublishStatus.PUBLISHED
            target.published_at = timezone.now()
            target.error_message = ""
        elif not res.ok and res.status == "ERROR":
            target.publish_status = SocialPostChannel.PublishStatus.FAILED
            target.retry_count += 1
            target.error_message = res.error
        target.save()
    return target

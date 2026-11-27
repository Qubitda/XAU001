from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel

from .channels import SocialChannel


class SocialMediaAsset(TimestampedModel):
    """Social-format media assets derived from verified product media."""

    class FormatKind(models.TextChoices):
        IG_FEED_4_5 = "IG_FEED_4_5", "Instagram Feed (4:5)"
        IG_STORY_9_16 = "IG_STORY_9_16", "Instagram Story/Reels (9:16)"
        TIKTOK_9_16 = "TIKTOK_9_16", "TikTok Video (9:16)"
        PINTEREST_PIN_2_3 = "PINTEREST_PIN_2_3", "Pinterest Pin (2:3)"
        WEB_PRODUCT = "WEB_PRODUCT", "Web Ürün Görseli"

    product = models.ForeignKey(
        "catalog.ProductModel",
        on_delete=models.CASCADE,
        related_name="social_media_assets",
    )
    format_kind = models.CharField(max_length=32, choices=FormatKind.choices)
    source_url = models.URLField(max_length=512)
    output_url = models.URLField(max_length=512, blank=True, default="")
    caption_draft = models.TextField(blank=True, default="")
    hashtags = models.JSONField(default=list, blank=True)
    is_approved = models.BooleanField(default=True)

    class Meta:
        db_table = "social_media_asset"
        ordering = ["-created_at"]


class SocialPost(TimestampedModel):
    """Content studio post linked to a verified catalog product."""

    class PostType(models.TextChoices):
        POST = "POST", "Gönderi"
        REELS = "REELS", "Reels"
        STORY = "STORY", "Hikâye"
        TIKTOK_VIDEO = "TIKTOK_VIDEO", "TikTok Videosu"
        PINTEREST_PIN = "PINTEREST_PIN", "Pinterest Pin"

    product = models.ForeignKey(
        "catalog.ProductModel",
        on_delete=models.SET_NULL,
        related_name="social_posts",
        null=True,
        blank=True,
    )
    post_type = models.CharField(max_length=24, choices=PostType.choices, default=PostType.POST)
    title = models.CharField(max_length=200)
    caption = models.TextField(blank=True, default="")
    hashtags = models.JSONField(default=list, blank=True)
    media_urls = models.JSONField(default=list, blank=True)
    target_url = models.URLField(max_length=512, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_social_posts",
    )

    class Meta:
        db_table = "social_post"
        ordering = ["-created_at"]


class SocialPostChannel(TimestampedModel):
    """Per-channel publishing state & schedule for a SocialPost."""

    class PublishStatus(models.TextChoices):
        DRAFT = "DRAFT", "Taslak"
        SCHEDULED = "SCHEDULED", "Planlandı"
        PUBLISHING = "PUBLISHING", "Yayınlanıyor"
        PUBLISHED = "PUBLISHED", "Yayınlandı"
        MANUAL_REQUIRED = "MANUAL_REQUIRED", "Manuel Yayın Gerekli"
        FAILED = "FAILED", "Hata"

    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="channel_targets",
    )
    channel = models.ForeignKey(
        SocialChannel,
        on_delete=models.CASCADE,
        related_name="post_targets",
    )
    publish_status = models.CharField(
        max_length=24, choices=PublishStatus.choices, default=PublishStatus.DRAFT, db_index=True
    )
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    external_post_id = models.CharField(max_length=128, blank=True, default="")
    external_url = models.URLField(max_length=512, blank=True, default="")
    retry_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "social_post_channel"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["post", "channel"], name="soc_post_ch_uniq")
        ]

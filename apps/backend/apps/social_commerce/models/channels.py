from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedModel
from apps.organizations.models import Organization


class SocialPlatform(models.TextChoices):
    INSTAGRAM = "INSTAGRAM", "Instagram"
    TIKTOK = "TIKTOK", "TikTok"
    PINTEREST = "PINTEREST", "Pinterest"
    WHATSAPP = "WHATSAPP", "WhatsApp"


class SocialChannel(TimestampedModel):
    """Connected or configured social commerce channel account."""

    platform = models.CharField(max_length=24, choices=SocialPlatform.choices, db_index=True)
    name = models.CharField(max_length=120)
    account_handle = models.CharField(max_length=120, blank=True, default="")
    external_account_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="social_channels",
        null=True,
        blank=True,
        help_text="Null = platform B2C channel; set = B2B dealer-isolated channel.",
    )
    country_code = models.CharField(max_length=8, default="TR")
    supports_catalog_feed = models.BooleanField(default=True)
    supports_direct_publish = models.BooleanField(default=False)
    supports_inbox_api = models.BooleanField(default=False)
    supports_in_app_shop = models.BooleanField(
        default=False,
        help_text="Explicitly false for TR where IG/TikTok in-app checkout is unavailable.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "social_channel"
        ordering = ["platform", "name"]
        indexes = [
            models.Index(fields=["platform", "is_active"], name="soc_ch_plat_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.platform} · {self.name}"


class SocialConnection(TimestampedModel):
    """Encrypted OAuth / API credentials for a SocialChannel (never exposed in APIs)."""

    class Status(models.TextChoices):
        PENDING_SETUP = "PENDING_SETUP", "Kurulum Bekliyor"
        CONNECTED = "CONNECTED", "Bağlı"
        EXPIRED = "EXPIRED", "Süresi Doldu"
        REVOKED = "REVOKED", "İptal Edildi"
        ERROR = "ERROR", "Hata"

    channel = models.OneToOneField(
        SocialChannel,
        on_delete=models.CASCADE,
        related_name="connection",
    )
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING_SETUP, db_index=True
    )
    access_token_encrypted = models.TextField(blank=True, default="")
    refresh_token_encrypted = models.TextField(blank=True, default="")
    webhook_secret_encrypted = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "social_connection"

    def __str__(self) -> str:
        return f"{self.channel} · {self.status}"

from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedModel

from .channels import SocialChannel


class SocialCatalog(TimestampedModel):
    """Channel product catalog configuration (fed strictly from central catalog/pricing)."""

    class SyncStatus(models.TextChoices):
        IDLE = "IDLE", "Bekliyor"
        SYNCING = "SYNCING", "Senkronize Ediliyor"
        SYNCED = "SYNCED", "Senkronize"
        PARTIAL = "PARTIAL", "Kısmi Hata"
        FAILED = "FAILED", "Hata"

    channel = models.ForeignKey(
        SocialChannel,
        on_delete=models.CASCADE,
        related_name="catalogs",
    )
    name = models.CharField(max_length=120)
    external_catalog_id = models.CharField(max_length=128, blank=True, default="")
    audience = models.CharField(max_length=16, default="B2C")
    sync_status = models.CharField(
        max_length=24, choices=SyncStatus.choices, default=SyncStatus.IDLE
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "social_catalog"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.channel.platform} · {self.name}"


class SocialProductMapping(TimestampedModel):
    """Maps central catalog ProductModel to a channel catalog item."""

    class SyncStatus(models.TextChoices):
        PENDING = "PENDING", "Bekliyor"
        SYNCED = "SYNCED", "Senkronize"
        REJECTED = "REJECTED", "Reddedildi"
        ERROR = "ERROR", "Hata"
        UNPUBLISHED = "UNPUBLISHED", "Yayından Kaldırıldı"

    catalog = models.ForeignKey(
        SocialCatalog,
        on_delete=models.CASCADE,
        related_name="product_mappings",
    )
    product = models.ForeignKey(
        "catalog.ProductModel",
        on_delete=models.CASCADE,
        related_name="social_mappings",
    )
    external_product_id = models.CharField(max_length=128, blank=True, default="")
    sync_status = models.CharField(
        max_length=24, choices=SyncStatus.choices, default=SyncStatus.PENDING, db_index=True
    )
    rejection_reason = models.TextField(blank=True, default="")
    last_synced_price_try = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    last_synced_stock_qty = models.PositiveIntegerField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "social_product_mapping"
        constraints = [
            models.UniqueConstraint(
                fields=["catalog", "product"], name="soc_map_catalog_product_uniq"
            )
        ]

    def __str__(self) -> str:
        return f"{self.catalog_id} · {self.product.parent_sku} · {self.sync_status}"

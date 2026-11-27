from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.common.models import TimestampedModel
from apps.organizations.models import Organization


class SocialCampaign(TimestampedModel):
    """Multi-channel social commerce campaign."""

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=48, unique=True, db_index=True)
    audience = models.CharField(max_length=16, default="B2C", db_index=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="social_campaigns",
        help_text="Null = platform campaign; set = B2B organization-isolated campaign.",
    )
    channels = models.JSONField(default=list, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    budget_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    target_revenue_try = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "social_campaign"
        ordering = ["-created_at"]


class SocialCampaignProduct(TimestampedModel):
    """Products attached to a SocialCampaign."""

    campaign = models.ForeignKey(
        SocialCampaign,
        on_delete=models.CASCADE,
        related_name="campaign_products",
    )
    product = models.ForeignKey(
        "catalog.ProductModel",
        on_delete=models.CASCADE,
        related_name="social_campaigns",
    )

    class Meta:
        db_table = "social_campaign_product"
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "product"], name="soc_camp_product_uniq"
            )
        ]

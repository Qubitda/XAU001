from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.common.models import TimestampedModel

from .campaigns import SocialCampaign
from .channels import SocialPlatform


class SocialInfluencer(TimestampedModel):
    """Influencer / creator profile for affiliate tracking."""

    full_name = models.CharField(max_length=160)
    handle = models.CharField(max_length=120, blank=True, default="")
    platform = models.CharField(
        max_length=24, choices=SocialPlatform.choices, default=SocialPlatform.INSTAGRAM
    )
    profile_url = models.URLField(max_length=512, blank=True, default="")
    follower_count = models.PositiveIntegerField(default=0)
    engagement_rate_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    default_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00")
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "social_influencer"
        ordering = ["full_name"]


class AffiliateCode(TimestampedModel):
    """Promo / tracking code assigned to an influencer or dealer."""

    influencer = models.ForeignKey(
        SocialInfluencer,
        on_delete=models.CASCADE,
        related_name="affiliate_codes",
    )
    campaign = models.ForeignKey(
        SocialCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affiliate_codes",
    )
    code = models.CharField(max_length=40, unique=True, db_index=True)
    commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00")
    )
    discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "social_affiliate_code"


class AffiliateConversion(TimestampedModel):
    """Order conversion attributed to an AffiliateCode (refunded orders excluded from net)."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Bekliyor"
        APPROVED = "APPROVED", "Onaylandı"
        CANCELLED_REFUNDED = "CANCELLED_REFUNDED", "İptal / İade"
        PAID = "PAID", "Ödendi"

    affiliate_code = models.ForeignKey(
        AffiliateCode,
        on_delete=models.CASCADE,
        related_name="conversions",
    )
    order_no = models.CharField(max_length=40, db_index=True)
    audience = models.CharField(max_length=16, default="B2C")
    gross_amount_try = models.DecimalField(max_digits=14, decimal_places=2)
    net_amount_try = models.DecimalField(max_digits=14, decimal_places=2)
    commission_amount_try = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    class Meta:
        db_table = "social_affiliate_conversion"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["affiliate_code", "order_no"],
                name="soc_aff_conv_code_order_uniq",
            )
        ]

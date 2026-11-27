from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.common.models import TimestampedModel
from apps.customers.models import Customer

from .campaigns import SocialCampaign
from .channels import SocialPlatform
from .content import SocialPost


class SocialAttribution(TimestampedModel):
    """First-touch / last-touch / assisted social traffic & order attribution."""

    class TouchRole(models.TextChoices):
        FIRST_TOUCH = "FIRST_TOUCH", "İlk Temas"
        LAST_TOUCH = "LAST_TOUCH", "Son Temas"
        ASSISTED = "ASSISTED", "Destekleyen Temas"

    platform = models.CharField(max_length=24, choices=SocialPlatform.choices, db_index=True)
    touch_role = models.CharField(
        max_length=20, choices=TouchRole.choices, default=TouchRole.LAST_TOUCH
    )
    utm_source = models.CharField(max_length=80, blank=True, default="", db_index=True)
    utm_medium = models.CharField(max_length=80, blank=True, default="")
    utm_campaign = models.CharField(max_length=120, blank=True, default="")
    utm_content = models.CharField(max_length=120, blank=True, default="")
    product = models.ForeignKey(
        "catalog.ProductModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    campaign = models.ForeignKey(
        SocialCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    post = models.ForeignKey(
        SocialPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    event_type = models.CharField(max_length=32, default="CLICK", db_index=True)
    order_no = models.CharField(max_length=40, blank=True, default="", db_index=True)
    revenue_try = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    audience = models.CharField(max_length=16, default="B2C", db_index=True)

    class Meta:
        db_table = "social_attribution"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "order_no"],
                condition=models.Q(event_type="ORDER", order_no__gt=""),
                name="soc_attr_order_event_uniq",
            )
        ]

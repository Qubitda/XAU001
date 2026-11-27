from __future__ import annotations

from django.db import models

from apps.common.models import TimestampedModel

from .channels import SocialPlatform


class SocialAutomationRule(TimestampedModel):
    """Consent-aware social automation rules."""

    class TriggerEvent(models.TextChoices):
        NEW_IG_LEAD = "NEW_IG_LEAD", "Yeni Instagram Müşterisi"
        ABANDONED_CART = "ABANDONED_CART", "Sepet Terk Edildi"
        BACK_IN_STOCK = "BACK_IN_STOCK", "Ürün Tekrar Stokta"
        INFLUENCER_CONVERSION = "INFLUENCER_CONVERSION", "Influencer Kodu Kullanıldı"

    name = models.CharField(max_length=160)
    trigger_event = models.CharField(max_length=32, choices=TriggerEvent.choices, db_index=True)
    channel = models.CharField(
        max_length=24, choices=SocialPlatform.choices, default=SocialPlatform.WHATSAPP
    )
    requires_consent = models.BooleanField(default=True)
    template_key = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "social_automation_rule"
        ordering = ["name"]

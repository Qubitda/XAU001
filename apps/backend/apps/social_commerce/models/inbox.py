from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel
from apps.customers.models import Customer

from .channels import SocialChannel, SocialPlatform


class SocialInboxConversation(TimestampedModel):
    """Unified DM / comment / WhatsApp conversation linked to CRM Customer."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Açık"
        WAITING = "WAITING", "Müşteri Bekleniyor"
        CONVERTED = "CONVERTED", "Siparişe Dönüştü"
        CLOSED = "CLOSED", "Kapatıldı"

    channel = models.ForeignKey(
        SocialChannel,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    platform = models.CharField(max_length=24, choices=SocialPlatform.choices, db_index=True)
    external_thread_id = models.CharField(max_length=128, db_index=True)
    external_sender_id = models.CharField(max_length=128, blank=True, default="")
    sender_display_name = models.CharField(max_length=160, blank=True, default="")
    sender_phone = models.CharField(max_length=32, blank=True, default="")
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_conversations",
    )
    product = models.ForeignKey(
        "catalog.ProductModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_conversations",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_social_conversations",
    )
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_inbound_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Tracks 24-hour WhatsApp customer service window.",
    )

    class Meta:
        db_table = "social_inbox_conversation"
        ordering = ["-last_message_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "external_thread_id"], name="soc_conv_ch_thread_uniq"
            )
        ]


class SocialInboxMessage(TimestampedModel):
    """Idempotent inbound/outbound message inside a SocialInboxConversation."""

    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "Gelen"
        OUTBOUND = "OUTBOUND", "Giden"

    conversation = models.ForeignKey(
        SocialInboxConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=16, choices=Direction.choices)
    external_message_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    body = models.TextField()
    attached_product = models.ForeignKey(
        "catalog.ProductModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    delivery_status = models.CharField(max_length=32, default="RECEIVED")
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "social_inbox_message"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "external_message_id"],
                condition=models.Q(external_message_id__gt=""),
                name="soc_msg_conv_ext_id_uniq",
            )
        ]


class SocialWhatsAppTemplate(TimestampedModel):
    """Registered WhatsApp Business template with explicit Meta category (never inferred from name)."""

    class Category(models.TextChoices):
        MARKETING = "MARKETING", "Pazarlama"
        UTILITY = "UTILITY", "Bilgilendirme / İşlem"
        AUTHENTICATION = "AUTHENTICATION", "Doğrulama"

    class Status(models.TextChoices):
        APPROVED = "APPROVED", "Onaylı"
        PENDING = "PENDING", "Bekliyor"
        REJECTED = "REJECTED", "Reddedildi"

    channel = models.ForeignKey(
        SocialChannel,
        on_delete=models.CASCADE,
        related_name="whatsapp_templates",
    )
    name = models.CharField(max_length=128)
    language_code = models.CharField(max_length=16, default="tr")
    category = models.CharField(
        max_length=24, choices=Category.choices, default=Category.UTILITY, db_index=True
    )
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    class Meta:
        db_table = "social_whatsapp_template"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "name", "language_code"],
                name="soc_wa_tpl_ch_name_lang_uniq",
            )
        ]

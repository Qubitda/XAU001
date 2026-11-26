from django.db import models

from apps.common.models import TimestampedModel


class ChannelOutboundLog(TimestampedModel):
    """Append-only outbound SMS/WhatsApp attempt log."""

    class Channel(models.TextChoices):
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Kuyrukta"
        SENT = "SENT", "Gönderildi"
        FAILED = "FAILED", "Hata"
        SKIPPED = "SKIPPED", "Atlandı"

    channel = models.CharField(max_length=16, choices=Channel.choices, db_index=True)
    recipient = models.CharField(max_length=64, db_index=True)
    template_key = models.CharField(max_length=80, blank=True, default="")
    body = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=32, blank=True, default="console")
    provider_ref = models.CharField(max_length=128, blank=True, default="")
    skip_reason = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    context_snapshot = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    class Meta:
        db_table = "messaging_channel_outbound_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "-created_at"], name="msg_ch_created_idx"),
            models.Index(fields=["status", "-created_at"], name="msg_status_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.channel} · {self.recipient} · {self.status}"

from django.db import models

from apps.common.models import TimestampedModel


class IntegrationEvent(TimestampedModel):
    class SourceSystem(models.TextChoices):
        B2C_STOREFRONT = "B2C_STOREFRONT", "B2C Storefront"
        B2B_PORTAL = "B2B_PORTAL", "B2B Portal"
        EXTERNAL = "EXTERNAL", "External"

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Alındı"
        PROCESSED = "PROCESSED", "İşlendi"
        FAILED = "FAILED", "Hata"
        DUPLICATE = "DUPLICATE", "Mükerrer"

    event_id = models.CharField(max_length=128, unique=True, db_index=True)
    source_system = models.CharField(
        max_length=32, choices=SourceSystem.choices, default=SourceSystem.B2C_STOREFRONT
    )
    event_type = models.CharField(max_length=64, db_index=True)
    schema_version = models.CharField(max_length=16, default="1.0")
    occurred_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(max_length=128, unique=True, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.RECEIVED, db_index=True
    )
    error_message = models.TextField(blank=True, default="")
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "integrations_event"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["event_type", "-received_at"], name="integ_type_recv_idx"),
            models.Index(fields=["status", "-received_at"], name="integ_status_recv_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} · {self.event_id} · {self.status}"

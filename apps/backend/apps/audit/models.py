from django.conf import settings
from django.db import models
from apps.common.models import TimestampedModel
from apps.organizations.models import Organization


class AuditLog(TimestampedModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=80, db_index=True)
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=128, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} · {self.entity_type}:{self.entity_id}"

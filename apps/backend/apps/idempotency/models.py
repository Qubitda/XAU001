from django.db import models

from apps.common.models import TimestampedModel


class IdempotencyRecord(TimestampedModel):
    key = models.CharField(max_length=128, db_index=True)
    scope = models.CharField(max_length=256, db_index=True)
    request_hash = models.CharField(max_length=64, blank=True, default="")
    response_status = models.PositiveSmallIntegerField()
    response_body = models.JSONField()
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "idempotency_record"
        constraints = [
            models.UniqueConstraint(fields=["scope", "key"], name="uniq_idempotency_scope_key"),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.key}"
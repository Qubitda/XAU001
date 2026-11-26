from django.conf import settings
from django.db import models
from apps.common.models import TimestampedModel
from apps.organizations.models import Organization

from .constants import DEFAULT_SCOPES


class ApiKey(TimestampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=16, db_index=True)
    key_hash = models.CharField(max_length=64)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_api_keys",
    )

    class Meta:
        db_table = "api_keys_apikey"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}…)"

    def save(self, *args, **kwargs):
        if not self.scopes:
            self.scopes = list(DEFAULT_SCOPES)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        from django.utils import timezone

        return timezone.now() >= self.expires_at
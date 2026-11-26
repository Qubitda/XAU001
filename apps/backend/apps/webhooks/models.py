from django.db import models

from apps.common.models import TimestampedModel
from apps.organizations.models import Organization

WEBHOOK_EVENTS: tuple[str, ...] = (
    "b2c.order.created",
    "b2b.order.created",
    "b2b.order.status",
)

# Platform-scoped (B2C) vs organization-scoped (B2B dealer) event sets.
PLATFORM_WEBHOOK_EVENTS: frozenset[str] = frozenset({"b2c.order.created"})
ORGANIZATION_WEBHOOK_EVENTS: frozenset[str] = frozenset({"b2b.order.created", "b2b.order.status"})


class WebhookEndpoint(TimestampedModel):
    """
    Delivery target for signed webhook POSTs.

    - Organization endpoints (is_platform=False): only B2B events for that org.
    - Platform endpoints (is_platform=True): only B2C / platform events; no org fan-out.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
        null=True,
        blank=True,
    )
    is_platform = models.BooleanField(
        default=False,
        help_text="True → platform (B2C) events only; must not bind a dealer organization.",
    )
    url = models.URLField(max_length=512)
    secret = models.CharField(max_length=128)
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "webhook_endpoint"
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["is_platform", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(is_platform=True, organization__isnull=True)
                    | models.Q(is_platform=False, organization__isnull=False)
                ),
                name="webhook_platform_xor_organization",
            ),
        ]

    def __str__(self) -> str:
        if self.is_platform:
            return f"platform → {self.url}"
        return f"{self.organization.code} → {self.url}"

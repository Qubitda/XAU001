from django.db import models

from apps.common.models import TimestampedModel
from apps.organizations.models import Organization


class SmtpSetting(TimestampedModel):
    """
    Platform SMTP when organization is null; B2B org override when set.
    Password is AES-256-GCM ciphertext (see apps.mail.crypto).
    """

    class Encryption(models.TextChoices):
        TLS = "TLS", "STARTTLS (587)"
        SSL = "SSL", "SSL/TLS (465)"
        NONE = "NONE", "No encryption (dev only)"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="smtp_settings",
        help_text="Null = platform (B2C / system default) SMTP.",
    )
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=587)
    encryption = models.CharField(
        max_length=8, choices=Encryption.choices, default=Encryption.TLS
    )
    username = models.CharField(max_length=255, blank=True, default="")
    password_ciphertext = models.TextField(blank=True, default="")
    from_name = models.CharField(max_length=160, blank=True, default="Tara Gold")
    from_email = models.EmailField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "mail_smtp_settings"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
        ]

    def __str__(self) -> str:
        scope = self.organization.code if self.organization_id else "PLATFORM"
        return f"{scope} · {self.host}:{self.port}"


class EmailTemplate(TimestampedModel):
    """DB override for filesystem defaults under apps/mail/templates/mail/."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="email_templates",
        help_text="Null = platform default override.",
    )
    template_key = models.CharField(max_length=64, db_index=True)
    subject = models.CharField(max_length=255)
    body_html = models.TextField(
        help_text="Inner HTML content; wrapped by BaseLayout. Supports {{ variable }}."
    )
    primary_color = models.CharField(max_length=16, blank=True, default="#4A101C")
    logo_url = models.URLField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "mail_email_templates"
        ordering = ["template_key", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "template_key"],
                name="uniq_mail_template_org_key",
            ),
        ]

    def __str__(self) -> str:
        scope = self.organization.code if self.organization_id else "PLATFORM"
        return f"{scope} · {self.template_key}"


class MailLog(TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Kuyrukta"
        SENT = "SENT", "Gönderildi"
        FAILED = "FAILED", "Başarısız"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mail_logs",
    )
    recipient = models.EmailField(db_index=True)
    template_key = models.CharField(max_length=64, db_index=True)
    subject = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    error_message = models.TextField(blank=True, default="")
    provider_message_id = models.CharField(max_length=128, blank=True, default="")
    context_snapshot = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mail_mail_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["template_key", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.template_key} → {self.recipient} ({self.status})"

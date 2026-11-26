from django.db import models

from apps.common.models import TimestampedModel
from apps.customers.models import Customer


class ConsentPurpose(models.TextChoices):
    KVKK_NOTICE = "KVKK_NOTICE", "KVKK Aydınlatma"
    EXPLICIT_CONSENT = "EXPLICIT_CONSENT", "Açık Rıza"
    COMMERCIAL_EMAIL = "COMMERCIAL_EMAIL", "Ticari E-posta"
    COMMERCIAL_SMS = "COMMERCIAL_SMS", "Ticari SMS"
    COMMERCIAL_WHATSAPP = "COMMERCIAL_WHATSAPP", "Ticari WhatsApp"
    COMMERCIAL_CALL = "COMMERCIAL_CALL", "Ticari Arama"


class ConsentChannel(models.TextChoices):
    EMAIL = "EMAIL", "E-posta"
    SMS = "SMS", "SMS"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    CALL = "CALL", "Arama"
    WEB = "WEB", "Web"


class ConsentStatus(models.TextChoices):
    GRANTED = "GRANTED", "Verildi"
    WITHDRAWN = "WITHDRAWN", "Geri Çekildi"
    DENIED = "DENIED", "Reddedildi"


class ConsentSource(models.TextChoices):
    CHECKOUT = "CHECKOUT", "Ödeme"
    REGISTER = "REGISTER", "Kayıt"
    FOOTER = "FOOTER", "Footer"
    IYS = "IYS", "İYS"
    OPS = "OPS", "OPS"
    IMPORT = "IMPORT", "İçe Aktarım"
    INTEGRATION = "INTEGRATION", "Entegrasyon"


class ConsentLog(TimestampedModel):
    """
    Append-only consent evidence. Never update or soft-delete rows.
    Active consent = latest GRANTED with no later WITHDRAWN for same purpose+channel.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consent_logs",
    )
    guest_email = models.EmailField(blank=True, default="")
    purpose = models.CharField(max_length=32, choices=ConsentPurpose.choices, db_index=True)
    channel = models.CharField(max_length=16, choices=ConsentChannel.choices, db_index=True)
    status = models.CharField(max_length=16, choices=ConsentStatus.choices, db_index=True)
    source = models.CharField(
        max_length=16, choices=ConsentSource.choices, default=ConsentSource.INTEGRATION
    )
    granted_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    document_version = models.CharField(max_length=32, blank=True, default="")
    document_hash = models.CharField(max_length=64, blank=True, default="")
    legal_document = models.ForeignKey(
        "contracts.LegalDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consent_logs",
    )
    iys_reference = models.CharField(max_length=128, blank=True, default="")
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent_hash = models.CharField(max_length=64, blank=True, default="")
    correlation_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "consent_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["customer", "purpose", "channel", "-created_at"],
                name="consent_cust_purp_ch_idx",
            ),
            models.Index(
                fields=["guest_email", "purpose", "channel", "-created_at"],
                name="consent_guest_purp_ch_idx",
            ),
        ]

    def __str__(self) -> str:
        who = self.customer_id or self.guest_email or "?"
        return f"{who} · {self.purpose}/{self.channel} · {self.status}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("ConsentLog is append-only; updates are forbidden.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ConsentLog is append-only; deletes are forbidden.")

import hashlib

from django.db import models

from apps.common.models import TimestampedModel
from apps.customers.models import Customer


class LegalDocument(TimestampedModel):
    class Code(models.TextChoices):
        KVKK = "KVKK", "KVKK Aydınlatma"
        PRIVACY = "PRIVACY", "Gizlilik İlkeleri"
        COOKIE = "COOKIE", "Çerez Politikası"
        DISTANCE_SALES = "DISTANCE_SALES", "Mesafeli Satış Sözleşmesi"
        PRE_INFO = "PRE_INFO", "Ön Bilgilendirme"
        MEMBERSHIP = "MEMBERSHIP", "Üyelik Sözleşmesi"

    class Audience(models.TextChoices):
        B2C = "B2C", "B2C"
        B2B = "B2B", "B2B"
        ALL = "ALL", "Tümü"

    code = models.CharField(max_length=32, choices=Code.choices, db_index=True)
    version = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    body_html = models.TextField(blank=True, default="")
    body_md = models.TextField(blank=True, default="")
    content_hash = models.CharField(max_length=64, blank=True, default="")
    effective_from = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    audience = models.CharField(
        max_length=8, choices=Audience.choices, default=Audience.ALL
    )

    class Meta:
        db_table = "contracts_legal_document"
        ordering = ["code", "-effective_from", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"],
                name="uniq_legal_document_code_version",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} v{self.version}"

    def compute_content_hash(self) -> str:
        material = f"{self.title}\n{self.body_html}\n{self.body_md}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def save(self, *args, **kwargs):
        if not self.content_hash:
            self.content_hash = self.compute_content_hash()
        return super().save(*args, **kwargs)


class ContractAcceptance(TimestampedModel):
    """Immutable acceptance tied to an order — cart alone is never acceptance."""

    class Source(models.TextChoices):
        CHECKOUT = "CHECKOUT", "Ödeme"
        INTEGRATION = "INTEGRATION", "Entegrasyon"
        OPS = "OPS", "OPS"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="contract_acceptances",
    )
    order = models.ForeignKey(
        "commerce.B2cOrder",
        on_delete=models.PROTECT,
        related_name="contract_acceptances",
    )
    document = models.ForeignKey(
        LegalDocument,
        on_delete=models.PROTECT,
        related_name="acceptances",
    )
    document_code = models.CharField(max_length=32, db_index=True)
    document_version = models.CharField(max_length=32)
    content_hash = models.CharField(max_length=64)
    accepted_at = models.DateTimeField()
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.CHECKOUT)
    evidence = models.JSONField(default=dict, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent_hash = models.CharField(max_length=64, blank=True, default="")
    correlation_id = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "contracts_acceptance"
        ordering = ["-accepted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "document_code"],
                name="uniq_contract_acceptance_order_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_id} · {self.document_code} v{self.document_version}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("ContractAcceptance is immutable; updates are forbidden.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ContractAcceptance is immutable; deletes are forbidden.")

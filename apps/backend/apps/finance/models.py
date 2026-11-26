from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.common.models import TimestampedModel
from apps.organizations.models import Organization


class DealerLedgerEntry(TimestampedModel):
    class EntryType(models.TextChoices):
        ORDER_DEBIT = "ORDER_DEBIT", "Sipariş Borçlandırma"
        ORDER_REVERSAL = "ORDER_REVERSAL", "Sipariş İptal Ters Kayıt"
        REFUND_CREDIT = "REFUND_CREDIT", "İade Alacak Kaydı"
        PAYMENT_CREDIT = "PAYMENT_CREDIT", "Tahsilat / Alacak"
        HAS_DELIVERY = "HAS_DELIVERY", "Has Altın Teslimi"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    entry_type = models.CharField(max_length=24, choices=EntryType.choices)
    reference_no = models.CharField(max_length=64, db_index=True)
    amount_usd = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    has_gold_gram = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))
    note = models.CharField(max_length=240, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "finance_dealer_ledger_entry"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference_no", "entry_type"],
                name="uniq_dealer_ledger_idempotency",
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization.code} · {self.entry_type} · {self.reference_no}"

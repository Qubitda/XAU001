from decimal import Decimal

from django.db import models

from apps.common.models import TimestampedModel
from apps.commerce.models import B2cOrder
from apps.organizations.models import Organization


class PaymentBankAccount(TimestampedModel):
    """
    Platform (B2C) or tenant (B2B) bank accounts for Havale/EFT.
    organization=null → Super Admin / site-owner accounts shown to B2C customers.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payment_bank_accounts",
    )
    bank_name = models.CharField(max_length=120)
    account_holder = models.CharField(max_length=160)
    iban = models.CharField(max_length=34)
    branch_code = models.CharField(max_length=32, blank=True, default="")
    account_number = models.CharField(max_length=64, blank=True, default="")
    currency = models.CharField(max_length=8, default="TRY")
    logo_url = models.URLField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "payments_bank_account"
        ordering = ["sort_order", "bank_name"]

    def __str__(self) -> str:
        scope = self.organization.code if self.organization_id else "PLATFORM"
        return f"{scope} · {self.bank_name}"


class PaymentProviderSetting(TimestampedModel):
    """
    Platform (or optional org) iyzico credentials. Secrets stored AES-256-GCM.
    Null organization = Super Admin / site-owner settings.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payment_provider_settings",
    )
    provider = models.CharField(max_length=16, default="IYZICO", db_index=True)
    api_key_ciphertext = models.TextField(blank=True, default="")
    secret_key_ciphertext = models.TextField(blank=True, default="")
    base_url = models.CharField(max_length=255, default="sandbox-api.iyzipay.com")
    callback_base_url = models.URLField(max_length=500, blank=True, default="")
    is_sandbox = models.BooleanField(default=True)
    pass_installment_fee_to_customer = models.BooleanField(
        default=True,
        help_text="Taksit vade farkını müşteriye yansıt",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "payments_provider_setting"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        scope = self.organization.code if self.organization_id else "PLATFORM"
        return f"{scope} · {self.provider} ({'sandbox' if self.is_sandbox else 'live'})"


class PaymentTransaction(TimestampedModel):
    class Provider(models.TextChoices):
        IYZICO = "IYZICO", "iyzico"
        BANK_TRANSFER = "BANK_TRANSFER", "Havale / EFT"

    class Status(models.TextChoices):
        INIT = "INIT", "Initialized"
        REDIRECTED = "REDIRECTED", "Redirected to CF"
        PENDING = "PENDING", "Pending / Havale Bekliyor"
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Fully Refunded"
        PARTIAL_REFUNDED = "PARTIAL_REFUNDED", "Partially Refunded"
        RECEIPT_UPLOADED = "RECEIPT_UPLOADED", "Dekont Yüklendi"
        REJECTED = "REJECTED", "Havale Reddedildi"

    class ReceiptStatus(models.TextChoices):
        NONE = "NONE", "Yok"
        UPLOADED = "UPLOADED", "Yüklendi"
        APPROVED = "APPROVED", "Onaylandı"
        REJECTED = "REJECTED", "Reddedildi"

    order = models.ForeignKey(
        B2cOrder,
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )
    provider = models.CharField(
        max_length=16, choices=Provider.choices, default=Provider.IYZICO, db_index=True
    )
    conversation_id = models.CharField(max_length=64, unique=True, db_index=True)
    token = models.CharField(max_length=128, unique=True, null=True, blank=True, db_index=True)
    payment_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.INIT, db_index=True
    )
    price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    base_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Vade farkı hariç ana tutar",
    )
    paid_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    refunded_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="TRY")
    installment = models.PositiveSmallIntegerField(default=1)
    bin_number = models.CharField(max_length=8, blank=True, default="")
    last_four_digits = models.CharField(max_length=4, blank=True, default="")
    auth_code = models.CharField(max_length=32, blank=True, default="")
    card_type = models.CharField(max_length=32, blank=True, default="")
    card_association = models.CharField(max_length=32, blank=True, default="")
    card_family = models.CharField(max_length=64, blank=True, default="")
    item_transactions = models.JSONField(default=list, blank=True)
    payment_page_url = models.URLField(max_length=500, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    # Havale / EFT
    transfer_reference = models.CharField(max_length=64, blank=True, default="", db_index=True)
    bank_account = models.ForeignKey(
        PaymentBankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    bank_name_snapshot = models.CharField(max_length=120, blank=True, default="")
    iban_snapshot = models.CharField(max_length=34, blank=True, default="")
    account_holder_snapshot = models.CharField(max_length=160, blank=True, default="")
    receipt_file = models.FileField(upload_to="payment_receipts/%Y/%m/", blank=True, null=True)
    receipt_status = models.CharField(
        max_length=16, choices=ReceiptStatus.choices, default=ReceiptStatus.NONE, db_index=True
    )
    receipt_uploaded_at = models.DateTimeField(null=True, blank=True)
    receipt_reviewed_at = models.DateTimeField(null=True, blank=True)
    receipt_reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # Manuel havale iadesi
    refund_iban = models.CharField(max_length=34, blank=True, default="")
    refund_account_holder = models.CharField(max_length=160, blank=True, default="")
    manual_refund_receipt = models.FileField(
        upload_to="payment_refund_receipts/%Y/%m/", blank=True, null=True
    )
    raw_initialize_response = models.JSONField(default=dict, blank=True)
    raw_retrieve_response = models.JSONField(default=dict, blank=True)
    raw_callback_payload = models.JSONField(default=dict, blank=True)
    raw_webhook_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payments_payment_transaction"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.provider}:{self.conversation_id} ({self.status})"

    @property
    def refundable_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.paid_price - self.refunded_amount)


class RefundRequest(TimestampedModel):
    """B2C customer-initiated cancel/refund request (OPS approves → iyzico / manual IBAN)."""

    class Kind(models.TextChoices):
        CANCEL = "CANCEL", "İptal"
        REFUND = "REFUND", "İade"

    class Status(models.TextChoices):
        PENDING = "PENDING", "İnceleniyor"
        APPROVED = "APPROVED", "Onaylandı"
        REJECTED = "REJECTED", "Reddedildi"
        COMPLETED = "COMPLETED", "İade/İptal Tamamlandı"

    order = models.ForeignKey(B2cOrder, on_delete=models.CASCADE, related_name="refund_requests")
    payment = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_requests",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.REFUND)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    requested_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    admin_note = models.TextField(blank=True, default="")
    refund_iban = models.CharField(max_length=34, blank=True, default="")
    refund_account_holder = models.CharField(max_length=160, blank=True, default="")
    requested_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments_refund_request"
        ordering = ["-created_at"]


class RefundLog(TimestampedModel):
    """Audit of iyzico Cancel / Refund API calls or manual bank refunds."""

    class Action(models.TextChoices):
        CANCEL = "CANCEL", "Cancel"
        REFUND = "REFUND", "Refund"
        MANUAL_BANK_REFUND = "MANUAL_BANK_REFUND", "Manuel Havale İadesi"

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"

    payment = models.ForeignKey(
        PaymentTransaction, on_delete=models.CASCADE, related_name="refund_logs"
    )
    refund_request = models.ForeignKey(
        RefundRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    action = models.CharField(max_length=24, choices=Action.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    payment_transaction_id = models.CharField(max_length=64, blank=True, default="")
    iyzico_payment_id = models.CharField(max_length=64, blank=True, default="")
    raw_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "payments_refund_log"
        ordering = ["-created_at"]

from django.contrib import admin

from apps.common.admin import ImmutableAdminMixin, NoDeleteAdminMixin, OpsRestrictedAdminMixin

from .models import (
    PaymentBankAccount,
    PaymentProviderSetting,
    PaymentTransaction,
    RefundLog,
    RefundRequest,
)


@admin.register(PaymentBankAccount)
class PaymentBankAccountAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "account_holder", "iban", "organization", "is_active", "sort_order")
    list_filter = ("is_active", "currency")
    search_fields = ("bank_name", "iban", "account_holder")


@admin.register(PaymentProviderSetting)
class PaymentProviderSettingAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("provider", "organization", "base_url", "is_sandbox", "is_active", "updated_at")
    list_filter = ("provider", "is_sandbox", "is_active")
    search_fields = ("provider", "organization__code")
    exclude = ("api_key_ciphertext", "secret_key_ciphertext")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "conversation_id",
        "provider",
        "status",
        "payment_id",
        "transfer_reference",
        "paid_price",
        "refunded_amount",
        "currency",
        "created_at",
    )
    list_filter = ("provider", "status", "receipt_status", "currency")
    search_fields = ("conversation_id", "payment_id", "transfer_reference", "order__order_no")
    exclude = ("token",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "raw_initialize_response",
        "raw_retrieve_response",
        "raw_callback_payload",
        "raw_webhook_payload",
        "item_transactions",
    )
    raw_id_fields = ("order", "bank_account")


@admin.register(RefundRequest)
class RefundRequestAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("order", "kind", "status", "requested_amount", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("order__order_no", "refund_account_holder")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("order", "payment", "requested_by", "reviewed_by")


@admin.register(RefundLog)
class RefundLogAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("payment", "action", "status", "amount", "created_at")
    list_filter = ("action", "status")
    search_fields = ("payment__conversation_id", "payment__order__order_no")
    readonly_fields = tuple(f.name for f in RefundLog._meta.fields)
    raw_id_fields = ("payment", "refund_request", "actor")

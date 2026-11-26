from django.contrib import admin
from apps.common.admin import ImmutableAdminMixin
from .models import DealerLedgerEntry


@admin.register(DealerLedgerEntry)
class DealerLedgerEntryAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "created_at",
        "organization",
        "entry_type",
        "reference_no",
        "amount_usd",
        "has_gold_gram",
        "created_by",
    )
    list_filter = ("entry_type", "organization", "created_at")
    search_fields = ("reference_no", "organization__code", "organization__name", "note", "created_by__email")
    list_select_related = ("organization", "created_by")
    date_hierarchy = "created_at"
    readonly_fields = (
        "id",
        "organization",
        "entry_type",
        "reference_no",
        "amount_usd",
        "has_gold_gram",
        "note",
        "created_by",
        "created_at",
        "updated_at",
    )

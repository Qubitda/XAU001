from django.contrib import admin

from .models import ContractAcceptance, LegalDocument


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "title", "audience", "is_published", "effective_from")
    list_filter = ("code", "audience", "is_published")
    search_fields = ("title", "version")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ContractAcceptance)
class ContractAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("customer", "document", "order", "source", "accepted_at")
    list_filter = ("source", "accepted_at")
    search_fields = ("customer__full_name", "document__doc_type", "order__order_no")
    readonly_fields = ("id", "created_at", "updated_at")

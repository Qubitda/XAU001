from django.contrib import admin
from apps.common.admin import ImmutableAdminMixin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "action", "entity_type", "entity_id", "actor", "organization")
    list_filter = ("action", "entity_type", "organization", "created_at")
    search_fields = ("action", "entity_type", "entity_id", "actor__email", "organization__code")
    list_select_related = ("actor", "organization")
    date_hierarchy = "created_at"
    readonly_fields = (
        "id",
        "actor",
        "organization",
        "action",
        "entity_type",
        "entity_id",
        "metadata",
        "created_at",
        "updated_at",
    )

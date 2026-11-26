from django.contrib import admin

from .models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "organization", "is_active", "created_by", "last_used_at", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "prefix", "organization__code", "created_by__email")
    readonly_fields = ("prefix", "key_hash", "last_used_at", "created_at", "updated_at")
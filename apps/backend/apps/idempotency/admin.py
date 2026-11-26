from django.contrib import admin

from .models import IdempotencyRecord


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ("key", "scope", "response_status", "expires_at", "created_at")
    search_fields = ("key", "scope")
    readonly_fields = tuple(f.name for f in IdempotencyRecord._meta.fields)
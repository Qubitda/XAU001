from django.contrib import admin

from .models import IntegrationEvent


@admin.register(IntegrationEvent)
class IntegrationEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "source_system", "event_type", "status", "created_at")
    list_filter = ("source_system", "status")
    search_fields = ("event_id", "event_type", "idempotency_key")
    readonly_fields = ("id", "created_at", "updated_at")

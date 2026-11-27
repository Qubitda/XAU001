from django.contrib import admin

from .models import ChannelOutboundLog


@admin.register(ChannelOutboundLog)
class ChannelOutboundLogAdmin(admin.ModelAdmin):
    list_display = ("channel", "recipient", "template_key", "status", "provider", "created_at")
    list_filter = ("channel", "status", "provider")
    search_fields = ("recipient", "template_key", "provider_ref", "correlation_id")
    readonly_fields = ("id", "created_at", "updated_at")

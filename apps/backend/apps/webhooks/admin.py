from django.contrib import admin

from .models import WebhookEndpoint


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("organization", "url", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("url", "organization__code", "organization__name")
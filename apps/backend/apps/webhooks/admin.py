from django.contrib import admin

from apps.common.admin import OpsRestrictedAdminMixin

from .models import WebhookEndpoint


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("organization", "url", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("url", "organization__code", "organization__name")
    exclude = ("secret",)
    readonly_fields = ("id", "created_at", "updated_at")

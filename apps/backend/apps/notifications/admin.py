from django.contrib import admin
from apps.common.admin import OpsRestrictedAdminMixin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "recipient", "channel", "title", "is_read")
    list_filter = ("channel", "is_read", "created_at")
    search_fields = ("recipient__email", "recipient__full_name", "title", "body")
    autocomplete_fields = ("recipient",)
    list_select_related = ("recipient",)
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at")

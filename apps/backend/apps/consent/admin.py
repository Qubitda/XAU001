from django.contrib import admin

from .models import ConsentLog


@admin.register(ConsentLog)
class ConsentLogAdmin(admin.ModelAdmin):
    list_display = ("customer", "guest_email", "purpose", "channel", "status", "source", "created_at")
    list_filter = ("purpose", "channel", "status", "source")
    search_fields = ("customer__full_name", "customer__phone", "guest_email")
    readonly_fields = ("id", "created_at", "updated_at")

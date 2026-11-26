from django.contrib import admin
from apps.common.admin import OpsRestrictedAdminMixin
from .models import Customer, CustomerAddress


class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 0
    fields = (
        "address_type",
        "title",
        "city",
        "line",
        "contact_name",
        "phone",
        "is_default",
        "is_active",
    )


@admin.register(Customer)
class CustomerAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = (
        "full_name",
        "customer_type",
        "phone",
        "email",
        "city",
        "is_active",
        "organization",
        "user",
        "created_at",
    )
    list_filter = ("customer_type", "is_active", "city", "organization", "created_at")
    search_fields = ("full_name", "phone", "email", "identity_or_tax_no", "city")
    autocomplete_fields = ("user", "organization")
    list_select_related = ("user", "organization")
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [CustomerAddressInline]


@admin.register(CustomerAddress)
class CustomerAddressAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "customer", "address_type", "city", "is_default", "is_active", "created_at")
    list_filter = ("address_type", "is_active", "is_default")
    search_fields = ("title", "city", "customer__full_name", "phone")
    autocomplete_fields = ("customer",)
    list_select_related = ("customer",)

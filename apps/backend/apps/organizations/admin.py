from django.contrib import admin

from apps.common.admin import NoDeleteAdminMixin, OpsRestrictedAdminMixin

from .models import (
    Branch,
    Organization,
    OrganizationAddress,
    OrganizationBankAccount,
    OrganizationDocument,
    OrganizationMembership,
    SiteContactSettings,
)


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0
    fields = ("code", "name", "city", "is_default", "is_active")
    show_change_link = True


class AddressInline(admin.TabularInline):
    model = OrganizationAddress
    extra = 0
    fields = ("address_type", "title", "city", "is_default", "is_active")


@admin.register(Organization)
class OrganizationAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "org_type",
        "approval_status",
        "risk_level",
        "city",
        "credit_limit_usd",
        "used_credit_usd",
        "is_active",
    )
    list_filter = ("org_type", "approval_status", "risk_level", "is_active", "city")
    search_fields = ("code", "name", "legal_name", "tax_office_and_no", "tax_number", "contact_name", "city")
    date_hierarchy = "created_at"
    readonly_fields = (
        "id",
        "used_credit_usd",
        "used_has_gram",
        "remaining_credit_usd_display",
        "remaining_has_gram_display",
        "created_at",
        "updated_at",
    )
    inlines = (BranchInline, AddressInline)

    fieldsets = (
        (
            "Firma Kimliği",
            {
                "fields": (
                    "id",
                    "code",
                    "name",
                    "legal_name",
                    "org_type",
                    "partner_roles",
                    "approval_status",
                    "logo",
                    "is_active",
                )
            },
        ),
        (
            "Kurumsal / İletişim",
            {
                "fields": (
                    "tax_office",
                    "tax_number",
                    "tax_office_and_no",
                    "mersis_no",
                    "trade_registry_no",
                    "company_type",
                    "founded_on",
                    "contact_name",
                    "email",
                    "phone",
                    "fax",
                    "website",
                    "city",
                    "description",
                )
            },
        ),
        (
            "Ticari & Risk",
            {
                "fields": (
                    "default_consignment_days",
                    "payment_term_days",
                    "risk_level",
                    "risk_note",
                    "credit_review_note",
                    "credit_reviewed_at",
                    "credit_reviewed_by",
                    "commercial_notes",
                    "supplier_code",
                    "supplier_lead_time_days",
                    "supplier_notes",
                )
            },
        ),
        (
            "Finansal Limitler (Kullanım Bakiyeleri Cari Defterden Yönetilir)",
            {
                "fields": (
                    "credit_limit_usd",
                    "used_credit_usd",
                    "remaining_credit_usd_display",
                    "has_limit_gram",
                    "used_has_gram",
                    "remaining_has_gram_display",
                )
            },
        ),
        ("Zaman Damgaları", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Kalan Kredi (USD)")
    def remaining_credit_usd_display(self, obj: Organization):
        return obj.remaining_credit_usd

    @admin.display(description="Kalan Has (gr)")
    def remaining_has_gram_display(self, obj: Organization):
        return obj.remaining_has_gram


@admin.register(Branch)
class BranchAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "organization", "city", "is_default", "is_active", "created_at")
    list_filter = ("is_active", "is_default", "city", "organization")
    search_fields = ("code", "name", "city", "organization__code", "organization__name")
    autocomplete_fields = ("organization",)
    list_select_related = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = (
        "user",
        "organization",
        "role_key",
        "job_title",
        "default_branch",
        "is_active",
        "created_at",
    )
    list_filter = ("role_key", "is_active", "organization")
    search_fields = ("user__email", "user__full_name", "organization__code", "organization__name", "job_title")
    autocomplete_fields = ("user", "organization", "default_branch")
    filter_horizontal = ("branches",)
    list_select_related = ("user", "organization", "default_branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(OrganizationAddress)
class OrganizationAddressAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "organization", "address_type", "city", "is_default", "is_active")
    list_filter = ("address_type", "is_active", "is_default")
    search_fields = ("title", "city", "line", "organization__code")


@admin.register(OrganizationBankAccount)
class OrganizationBankAccountAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("bank_name", "organization", "currency", "is_default", "is_active")
    list_filter = ("currency", "is_active", "is_default")
    search_fields = ("bank_name", "iban", "organization__code")


@admin.register(OrganizationDocument)
class OrganizationDocumentAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "organization", "doc_type", "is_active", "created_at")
    list_filter = ("doc_type", "is_active")
    search_fields = ("name", "organization__code")


@admin.register(SiteContactSettings)
class SiteContactSettingsAdmin(admin.ModelAdmin):
    list_display = ("singleton_key", "company_name", "phone", "whatsapp", "email", "updated_at")
    search_fields = ("singleton_key", "company_name", "phone", "email")

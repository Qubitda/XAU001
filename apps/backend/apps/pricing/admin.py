from django.contrib import admin
from apps.common.admin import ImmutableAdminMixin, NoDeleteAdminMixin, OpsRestrictedAdminMixin
from .models import ChannelRule, CostLine, PriceLock, PriceQuote, PricingRecipe


class CostLineInline(admin.TabularInline):
    model = CostLine
    extra = 0
    fields = ("line_type", "fc_currency", "fc_price", "fc_price_manual", "rate_override")


class ChannelRuleInline(admin.TabularInline):
    model = ChannelRule
    extra = 0
    fields = (
        "channel",
        "profit_unit",
        "profit_value",
        "discount_unit",
        "discount_value",
        "servis_bedeli_unit",
        "servis_bedeli_value",
    )


@admin.register(PricingRecipe)
class PricingRecipeAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = (
        "product",
        "version",
        "status",
        "pricing_mode",
        "lc_currency",
        "cached_total_cost_lc",
        "cached_b2b_try",
        "cached_b2c_try",
        "last_snapshot",
        "updated_at",
    )
    list_filter = ("status", "pricing_mode", "lc_currency")
    search_fields = ("product__parent_sku", "product__title", "last_snapshot__snapshot_code")
    autocomplete_fields = ("product",)
    list_select_related = ("product", "last_snapshot")
    readonly_fields = (
        "id",
        "version",
        "last_snapshot",
        "cached_total_cost_lc",
        "cached_b2b_try",
        "cached_b2c_try",
        "cached_b2c_list_try",
        "created_at",
        "updated_at",
    )
    inlines = (CostLineInline, ChannelRuleInline)

    def get_readonly_fields(self, request, obj=None):
        base = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.status == PricingRecipe.Status.PUBLISHED:
            return base + [
                "product",
                "status",
                "pricing_mode",
                "lc_currency",
            ]
        return base

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status == PricingRecipe.Status.PUBLISHED:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.status == PricingRecipe.Status.PUBLISHED:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(CostLine)
class CostLineAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("recipe", "line_type", "fc_currency", "fc_price", "fc_price_manual", "rate_override", "updated_at")
    list_filter = ("line_type", "fc_currency")
    search_fields = ("recipe__product__parent_sku", "recipe__product__title")
    autocomplete_fields = ("recipe",)
    list_select_related = ("recipe", "recipe__product")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ChannelRule)
class ChannelRuleAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = (
        "recipe",
        "channel",
        "profit_unit",
        "profit_value",
        "discount_unit",
        "discount_value",
        "servis_bedeli_unit",
        "servis_bedeli_value",
    )
    list_filter = ("channel",)
    search_fields = ("recipe__product__parent_sku", "recipe__product__title")
    autocomplete_fields = ("recipe",)
    list_select_related = ("recipe", "recipe__product")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PriceQuote)
class PriceQuoteAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "created_at",
        "channel",
        "product",
        "variant",
        "organization",
        "lc_currency",
        "final_price_lc",
        "final_price_try",
        "rate_snapshot",
    )
    list_filter = ("channel", "lc_currency", "organization", "created_at")
    search_fields = (
        "product__parent_sku",
        "variant__sku",
        "rate_snapshot__snapshot_code",
        "organization__code",
    )
    list_select_related = ("product", "variant", "recipe", "rate_snapshot", "organization")
    date_hierarchy = "created_at"
    readonly_fields = (
        "id",
        "product",
        "variant",
        "recipe",
        "rate_snapshot",
        "organization",
        "channel",
        "lc_currency",
        "list_price_try",
        "final_price_lc",
        "final_price_try",
        "effective_discount_pct",
        "internal_audit_json",
        "created_at",
        "updated_at",
    )


@admin.register(PriceLock)
class PriceLockAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("user", "rate_snapshot", "is_active", "expires_at", "created_at")
    list_filter = ("is_active", "created_at", "expires_at")
    search_fields = ("user__email", "rate_snapshot__snapshot_code")
    autocomplete_fields = ("user",)
    list_select_related = ("user", "rate_snapshot")
    date_hierarchy = "created_at"
    readonly_fields = ("id", "user", "rate_snapshot", "expires_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

from django.contrib import admin
from apps.common.admin import ImmutableAdminMixin, NoDeleteAdminMixin, OpsRestrictedAdminMixin
from .models import (
    BuyRequest,
    BuyRequestLine,
    BuyRequestResponse,
    OrderAllocation,
    SellerOffer,
    Settlement,
    SupplierOrder,
    SupplierOrderLine,
)


class BuyRequestLineInline(admin.TabularInline):
    model = BuyRequestLine
    extra = 0
    fields = ("product", "variant", "description", "qty", "target_unit_price", "currency")
    autocomplete_fields = ("product", "variant")


class SupplierOrderLineInline(admin.TabularInline):
    model = SupplierOrderLine
    extra = 0
    fields = ("parent_line", "product", "variant", "sku", "qty", "unit_price", "currency")
    autocomplete_fields = ("product", "variant", "parent_line")


@admin.register(SellerOffer)
class SellerOfferAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "product",
        "variant",
        "seller_organization",
        "channel",
        "unit_price",
        "currency",
        "status",
        "valid_until",
        "created_at",
    )
    list_filter = ("status", "channel", "seller_organization")
    search_fields = ("product__parent_sku", "variant__sku", "seller_organization__code")
    autocomplete_fields = ("seller_organization", "product", "variant", "warehouse")
    list_select_related = ("seller_organization", "product", "variant")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BuyRequest)
class BuyRequestAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "buyer_organization", "status", "needed_by", "created_by", "created_at")
    list_filter = ("status", "buyer_organization")
    search_fields = ("title", "buyer_organization__code", "created_by__email")
    autocomplete_fields = ("buyer_organization", "created_by")
    inlines = (BuyRequestLineInline,)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BuyRequestResponse)
class BuyRequestResponseAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("request", "seller_organization", "unit_price", "currency", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("request__title", "seller_organization__code")
    autocomplete_fields = ("request", "seller_organization", "seller_offer")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SupplierOrder)
class SupplierOrderAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "order_no",
        "supplier_organization",
        "buyer_organization",
        "parent_b2b_order",
        "status",
        "total_amount",
        "currency",
        "created_at",
    )
    list_filter = ("status", "supplier_organization")
    search_fields = ("order_no", "supplier_organization__code", "buyer_organization__code")
    autocomplete_fields = ("parent_b2b_order", "supplier_organization", "buyer_organization")
    inlines = (SupplierOrderLineInline,)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SupplierOrderLine)
class SupplierOrderLineAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("supplier_order", "sku", "product", "variant", "qty", "unit_price", "currency")
    search_fields = ("sku", "product__parent_sku", "supplier_order__order_no")
    autocomplete_fields = ("supplier_order", "parent_line", "product", "variant")
    list_select_related = ("supplier_order", "product", "variant")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(OrderAllocation)
class OrderAllocationAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "b2b_order_line",
        "qty",
        "ownership_type",
        "supplier_order_line",
        "warehouse_stock",
        "seller_offer",
        "created_at",
    )
    list_filter = ("ownership_type",)
    autocomplete_fields = (
        "b2b_order_line",
        "supplier_order_line",
        "warehouse_stock",
        "seller_offer",
        "owner_organization",
        "controller_organization",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    search_fields = ("b2b_order_line__sku", "b2b_order_line__parent_sku")


@admin.register(Settlement)
class SettlementAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "settlement_type",
        "counterparty_organization",
        "amount",
        "currency",
        "status",
        "reference_no",
        "settled_at",
        "created_at",
    )
    list_filter = ("settlement_type", "status", "currency")
    search_fields = ("reference_no", "counterparty_organization__code")
    list_select_related = ("counterparty_organization", "b2b_order", "supplier_order")
    readonly_fields = (
        "id",
        "counterparty_organization",
        "b2b_order",
        "supplier_order",
        "settlement_type",
        "amount",
        "currency",
        "status",
        "reference_no",
        "notes",
        "settled_at",
        "created_at",
        "updated_at",
    )


@admin.register(BuyRequestLine)
class BuyRequestLineAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("request", "product", "variant", "qty", "target_unit_price", "currency")
    search_fields = ("request__title", "product__parent_sku", "variant__sku")

from django.contrib import admin
from apps.common.admin import ImmutableAdminMixin, NoDeleteAdminMixin, OpsRestrictedAdminMixin
from .models import StockMovement, Warehouse, WarehouseStock


@admin.register(Warehouse)
class WarehouseAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "branch", "is_active", "created_at")
    list_filter = ("is_active", "branch__organization")
    search_fields = ("code", "name", "branch__name", "branch__code")
    autocomplete_fields = ("branch",)
    list_select_related = ("branch", "branch__organization")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(WarehouseStock)
class WarehouseStockAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "warehouse",
        "variant",
        "quantity",
        "reserved_qty",
        "available_qty_display",
        "ownership_type",
        "owner_organization",
        "updated_at",
    )
    list_filter = ("warehouse", "ownership_type", "variant__purity_code", "variant__metal_color")
    search_fields = (
        "variant__sku",
        "variant__product__parent_sku",
        "warehouse__code",
        "warehouse__name",
        "certificate_number",
        "lot_or_serial",
    )
    autocomplete_fields = ("variant", "warehouse", "owner_organization", "controller_organization")
    list_select_related = ("warehouse", "variant", "variant__product", "owner_organization")
    # Balances are strictly ledger-driven via inventory.services & StockMovement
    readonly_fields = (
        "id",
        "variant",
        "warehouse",
        "quantity",
        "reserved_qty",
        "available_qty_display",
        "owner_organization",
        "controller_organization",
        "source_supplier_name",
        "ownership_type",
        "gross_weight_gram",
        "certificate_number",
        "lot_or_serial",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Satılabilir Stok")
    def available_qty_display(self, obj: WarehouseStock) -> int:
        return obj.available_qty


@admin.register(StockMovement)
class StockMovementAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "created_at",
        "movement_type",
        "quantity_delta",
        "reference_no",
        "warehouse",
        "variant",
        "product",
        "actor",
    )
    list_filter = ("movement_type", "warehouse", "created_at")
    search_fields = ("reference_no", "product__parent_sku", "variant__sku", "actor__email")
    list_select_related = ("product", "variant", "warehouse", "actor")
    date_hierarchy = "created_at"
    readonly_fields = (
        "id",
        "product",
        "variant",
        "warehouse",
        "movement_type",
        "quantity_delta",
        "reference_no",
        "gross_weight_gram",
        "purity_code",
        "certificate_number",
        "lot_or_serial",
        "actor",
        "created_at",
        "updated_at",
    )

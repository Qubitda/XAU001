from django.contrib import admin
from apps.common.admin import OpsRestrictedAdminMixin
from .models import (
    Favorite,
    FinishedDetail,
    LooseStoneDetail,
    MountingDetail,
    ProductMedia,
    ProductModel,
    ProductVariant,
    StoneLine,
)


class StoneLineInline(admin.TabularInline):
    model = StoneLine
    extra = 0
    fields = ("role", "stone_type", "measure_unit", "count", "carat", "clarity", "color_grade", "cut_shape")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = (
        "sku",
        "purity_code",
        "metal_color",
        "size",
        "center_stone_carat",
        "gross_weight_gram",
        "stock_qty",
        "is_default",
        "is_active",
    )
    readonly_fields = ("stock_qty",)
    show_change_link = True


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 0
    fields = ("metal_color", "role", "url", "sort_order")


@admin.register(ProductModel)
class ProductModelAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = (
        "parent_sku",
        "title",
        "product_kind",
        "catalog_status",
        "category",
        "collection",
        "purity_code",
        "metal_color",
        "gross_weight_gram",
        "stock_status",
        "stock_qty",
        "owner_organization",
        "created_at",
    )
    list_filter = (
        "product_kind",
        "catalog_status",
        "category",
        "collection",
        "purity_code",
        "metal_color",
        "stock_status",
        "ownership_type",
        "mount_structure",
        "owner_organization",
    )
    search_fields = (
        "parent_sku",
        "erp_code",
        "barcode",
        "title",
        "seo_slug",
        "supplier_name",
        "certificate_number",
    )
    autocomplete_fields = ("owner_organization", "created_by")
    list_select_related = ("owner_organization", "created_by")
    date_hierarchy = "created_at"
    # ProductModel.stock_qty is synchronized from WarehouseStock via inventory.services
    readonly_fields = ("id", "stock_qty", "created_at", "updated_at")
    inlines = (StoneLineInline, ProductVariantInline, ProductMediaInline)


@admin.register(ProductVariant)
class ProductVariantAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = (
        "sku",
        "product",
        "purity_code",
        "metal_color",
        "size",
        "center_stone_carat",
        "gross_weight_gram",
        "stock_qty",
        "is_default",
        "is_active",
    )
    list_filter = ("purity_code", "metal_color", "is_default", "is_active")
    search_fields = ("sku", "product__parent_sku", "product__title")
    autocomplete_fields = ("product",)
    list_select_related = ("product",)
    # ProductVariant.stock_qty is synchronized from WarehouseStock via inventory.services
    readonly_fields = ("id", "stock_qty", "created_at", "updated_at")


@admin.register(StoneLine)
class StoneLineAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("product", "role", "stone_type", "count", "carat", "measure_unit", "clarity", "color_grade", "cut_shape")
    list_filter = ("role", "stone_type", "measure_unit")
    search_fields = ("product__parent_sku", "product__title", "stone_type", "cut_shape")
    autocomplete_fields = ("product",)
    list_select_related = ("product",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ProductMedia)
class ProductMediaAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("product", "metal_color", "role", "sort_order", "url", "created_at")
    list_filter = ("role", "metal_color")
    search_fields = ("product__parent_sku", "product__title", "url")
    autocomplete_fields = ("product",)
    list_select_related = ("product",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(FinishedDetail)
class FinishedDetailAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("product", "metal_name", "purity_code", "base_weight_gr", "fineness", "fixed_stone_cost_usd")
    search_fields = ("product__parent_sku", "purity_code")
    autocomplete_fields = ("product",)


@admin.register(MountingDetail)
class MountingDetailAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("product", "metal_name", "purity_code", "net_weight_gr", "min_carat", "max_carat")
    search_fields = ("product__parent_sku", "purity_code")
    autocomplete_fields = ("product",)


@admin.register(LooseStoneDetail)
class LooseStoneDetailAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("product", "stone_category", "shape", "carat", "color", "clarity", "net_cost_usd")
    search_fields = ("product__parent_sku", "cert_number", "shape")
    autocomplete_fields = ("product",)


@admin.register(Favorite)
class FavoriteAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "product__parent_sku", "product__title")
    autocomplete_fields = ("user", "product")
    list_select_related = ("user", "product")
    readonly_fields = ("id", "created_at", "updated_at")

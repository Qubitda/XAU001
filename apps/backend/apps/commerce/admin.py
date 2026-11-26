from django.contrib import admin, messages
from apps.common.admin import (
    ImmutableAdminMixin,
    NoDeleteAdminMixin,
    OpsRestrictedAdminMixin,
    ReadOnlyInlineMixin,
)
from config.exceptions import DomainError
from .models import (
    B2bDraftLine,
    B2bOrder,
    B2bOrderLine,
    B2cCartItem,
    B2cOrder,
    B2cOrderItem,
)
from .services import transition_b2b_order_status, transition_b2c_order_status


class B2cOrderItemInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = B2cOrderItem
    fields = (
        "sku",
        "parent_sku",
        "title",
        "purity_code",
        "metal_color",
        "size",
        "qty",
        "gross_weight_gram",
        "unit_list_price_try",
        "unit_final_price_try",
        "snapshot_code",
    )
    readonly_fields = fields


class B2bOrderLineInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = B2bOrderLine
    fields = (
        "sku",
        "parent_sku",
        "title",
        "purity_code",
        "metal_color",
        "size",
        "qty",
        "supply_type",
        "unit_fire_included_fine_gram",
        "unit_wholesale_usd",
        "unit_wholesale_try",
        "snapshot_code",
    )
    readonly_fields = fields


@admin.register(B2cCartItem)
class B2cCartItemAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("user", "sku", "title", "size", "qty", "unit_final_price_try", "snapshot_code", "created_at")
    list_filter = ("purity_code", "metal_color", "stock_status", "created_at")
    search_fields = ("user__email", "sku", "parent_sku", "title", "snapshot_code")
    autocomplete_fields = ("user", "variant")
    list_select_related = ("user", "variant", "rate_snapshot")
    readonly_fields = (
        "id",
        "unit_list_price_try",
        "unit_final_price_try",
        "rate_snapshot",
        "price_quote",
        "snapshot_code",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(B2cOrder)
class B2cOrderAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "order_no",
        "customer",
        "status",
        "payment_method",
        "grand_total_try",
        "rate_snapshot",
        "created_at",
    )
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("order_no", "customer__full_name", "customer__email", "customer__phone", "rate_snapshot__snapshot_code")
    list_select_related = ("customer", "created_by", "rate_snapshot", "price_lock")
    date_hierarchy = "created_at"
    inlines = (B2cOrderItemInline,)
    # Historical order & financial totals are immutable; only status transitions via service
    readonly_fields = (
        "id",
        "order_no",
        "customer",
        "created_by",
        "rate_snapshot",
        "price_lock",
        "gold_rate_try_per_gram",
        "payment_method",
        "accepted_custom_policy",
        "subtotal_list_try",
        "campaign_discount_try",
        "transfer_discount_try",
        "insured_shipping_try",
        "vat_included_try",
        "grand_total_try",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj: B2cOrder, form, change: bool):
        if change and "status" in form.changed_data:
            try:
                transition_b2c_order_status(
                    order_no=obj.order_no,
                    next_status=obj.status,
                    actor=request.user,
                )
            except DomainError as exc:
                self.message_user(request, str(exc.detail), level=messages.ERROR)
            return
        # No other fields are editable on confirmed B2C orders


@admin.register(B2cOrderItem)
class B2cOrderItemAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("order", "sku", "title", "purity_code", "metal_color", "size", "qty", "unit_final_price_try")
    list_filter = ("purity_code", "metal_color", "category")
    search_fields = ("order__order_no", "sku", "parent_sku", "title")
    list_select_related = ("order", "variant", "rate_snapshot", "price_quote")
    readonly_fields = tuple(f.name for f in B2cOrderItem._meta.fields)


@admin.register(B2bDraftLine)
class B2bDraftLineAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = (
        "organization",
        "sku",
        "qty",
        "supply_type",
        "unit_wholesale_usd",
        "unit_wholesale_try",
        "snapshot_code",
        "created_at",
    )
    list_filter = ("supply_type", "organization", "purity_code", "created_at")
    search_fields = ("organization__code", "organization__name", "sku", "parent_sku", "title")
    autocomplete_fields = ("organization", "created_by", "variant")
    list_select_related = ("organization", "created_by", "variant", "rate_snapshot")
    readonly_fields = (
        "id",
        "unit_gross_gram",
        "unit_net_metal_gram",
        "unit_fire_included_fine_gram",
        "unit_labor_and_stone_usd",
        "unit_wholesale_usd",
        "unit_wholesale_try",
        "rate_snapshot",
        "price_quote",
        "snapshot_code",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(B2bOrder)
class B2bOrderAdmin(NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "order_no",
        "organization",
        "branch",
        "status",
        "settlement_method",
        "total_pieces",
        "total_has_gold_gram",
        "total_wholesale_usd",
        "total_wholesale_try",
        "created_at",
    )
    list_filter = ("status", "settlement_method", "rate_lock_mode", "delivery_method", "organization", "created_at")
    search_fields = ("order_no", "organization__code", "organization__name", "contact_person", "rate_snapshot__snapshot_code")
    list_select_related = ("organization", "branch", "created_by", "rate_snapshot")
    date_hierarchy = "created_at"
    inlines = (B2bOrderLineInline,)
    # Historical order & financial snapshots are immutable; status routes via commerce.services
    readonly_fields = (
        "id",
        "order_no",
        "organization",
        "branch",
        "created_by",
        "rate_snapshot",
        "usd_try_rate",
        "gold_rate_try_per_gram",
        "contact_person",
        "settlement_method",
        "rate_lock_mode",
        "consignment_days",
        "delivery_method",
        "accepted_weight_tolerance",
        "total_pieces",
        "total_gross_gram",
        "total_has_gold_gram",
        "total_labor_and_stone_usd",
        "total_wholesale_usd",
        "total_wholesale_try",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj: B2bOrder, form, change: bool):
        if change and "order_note" in form.changed_data:
            B2bOrder.objects.filter(pk=obj.pk).update(order_note=obj.order_note)
        if change and "status" in form.changed_data:
            try:
                transition_b2b_order_status(
                    order_no=obj.order_no,
                    next_status=obj.status,
                    actor=request.user,
                )
            except DomainError as exc:
                self.message_user(request, str(exc.detail), level=messages.ERROR)


@admin.register(B2bOrderLine)
class B2bOrderLineAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("order", "sku", "title", "qty", "supply_type", "unit_wholesale_usd", "unit_wholesale_try")
    list_filter = ("supply_type", "purity_code", "metal_color")
    search_fields = ("order__order_no", "sku", "parent_sku", "title")
    list_select_related = ("order", "variant", "rate_snapshot", "price_quote")
    readonly_fields = tuple(f.name for f in B2bOrderLine._meta.fields)

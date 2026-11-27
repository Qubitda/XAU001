from django.contrib import admin
from apps.common.admin import ImmutableAdminMixin, OpsRestrictedAdminMixin, ReadOnlyInlineMixin
from .models import ExchangeMetalMatrix, ExchangeMetalRate, RateSnapshot


@admin.register(RateSnapshot)
class RateSnapshotAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "snapshot_code",
        "source_mode",
        "is_current",
        "live_has_gold_try_sell",
        "live_usd_sell",
        "live_eur_sell",
        "created_at",
    )
    list_filter = ("source_mode", "is_current", "created_at")
    search_fields = ("snapshot_code",)
    date_hierarchy = "created_at"
    readonly_fields = (
        "id",
        "snapshot_code",
        "source_mode",
        "live_usd_sell",
        "live_eur_sell",
        "live_has_gold_try_sell",
        "fx_base_rates",
        "is_current",
        "created_at",
        "updated_at",
    )


class ExchangeMetalRateInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = ExchangeMetalRate
    fields = ("currency_code", "base_value_try", "unit", "precision")
    readonly_fields = fields


@admin.register(ExchangeMetalMatrix)
class ExchangeMetalMatrixAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("version", "organization", "status", "effective_at", "created_at")
    list_filter = ("status",)
    search_fields = ("note", "organization__code")
    inlines = (ExchangeMetalRateInline,)


@admin.register(ExchangeMetalRate)
class ExchangeMetalRateAdmin(OpsRestrictedAdminMixin, admin.ModelAdmin):
    list_display = ("matrix", "currency_code", "base_value_try", "unit", "precision")
    list_filter = ("unit",)
    search_fields = ("currency_code",)

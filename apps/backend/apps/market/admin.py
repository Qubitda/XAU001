from django.contrib import admin
from apps.common.admin import ImmutableAdminMixin
from .models import RateSnapshot


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

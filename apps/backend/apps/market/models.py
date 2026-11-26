from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.common.models import TimestampedModel


class ImmutableRateSnapshotQuerySet(models.QuerySet):
    """Prevents destructive updates or deletions on historical RateSnapshot rows."""

    def delete(self):
        raise ValidationError("RateSnapshot kayıtları silinemez (immutable).")

    def update(self, **kwargs):
        allowed_fields = {"is_current", "updated_at"}
        if not kwargs or not set(kwargs.keys()).issubset(allowed_fields) or kwargs.get("is_current") is not False:
            raise ValidationError(
                "RateSnapshot geçmiş kur değerleri değiştirilemez; yalnızca is_current=False olarak kapatılabilir."
            )
        return super().update(**kwargs)


class RateSnapshot(TimestampedModel):
    """
    Immutable snapshot of 13 TRY-pivoted currency & precious metal rates.
    Every PriceQuote, PriceLock, and confirmed Order references a RateSnapshot FK.
    """

    class SourceMode(models.TextChoices):
        AUTO = "auto", "Canlı Piyasa Akışı"
        MANUAL = "manual", "Manuel Operasyon Girişi"

    snapshot_code = models.CharField(max_length=40, unique=True, db_index=True)
    source_mode = models.CharField(max_length=12, choices=SourceMode.choices, default=SourceMode.AUTO)
    live_usd_sell = models.DecimalField(max_digits=14, decimal_places=4)
    live_eur_sell = models.DecimalField(max_digits=14, decimal_places=4)
    live_has_gold_try_sell = models.DecimalField(max_digits=14, decimal_places=4)
    # 13 TRY-pivoted rates stored as strings for exact Decimal reconstruction
    fx_base_rates = models.JSONField(default=dict)
    is_current = models.BooleanField(default=True, db_index=True)

    objects = ImmutableRateSnapshotQuerySet.as_manager()

    class Meta:
        db_table = "market_rate_snapshot"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            update_fields = kwargs.get("update_fields")
            if (
                update_fields is not None
                and set(update_fields).issubset({"is_current", "updated_at"})
                and self.is_current is False
            ):
                return super().save(*args, **kwargs)
            raise ValidationError("RateSnapshot kayıtları oluşturulduktan sonra değiştirilemez (immutable).")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("RateSnapshot kayıtları silinemez (immutable).")

    def get_decimal_rates(self) -> dict[str, Decimal]:
        return {k: Decimal(str(v)) for k, v in (self.fx_base_rates or {}).items()}

    def __str__(self) -> str:
        return f"{self.snapshot_code} (Has: {self.live_has_gold_try_sell} TL/gr)"

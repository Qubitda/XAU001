from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
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


class ExchangeMetalMatrix(TimestampedModel):
    """
    Central versioned exchange & precious metal reference matrix (13 TRY-pivoted rates).
    Independent from products and pricing recipes; recipes store their own snapshot.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Taslak"
        ACTIVE = "ACTIVE", "Aktif"
        ARCHIVED = "ARCHIVED", "Arşivlendi"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exchange_metal_matrices",
    )
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    effective_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        db_table = "market_exchange_metal_matrix"
        ordering = ["-version", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "version"],
                condition=Q(organization__isnull=False),
                name="uniq_org_exchange_metal_matrix_version",
            ),
            models.UniqueConstraint(
                fields=["version"],
                condition=Q(organization__isnull=True),
                name="uniq_global_exchange_metal_matrix_version",
            ),
        ]

    def __str__(self) -> str:
        scope = self.organization.code if self.organization_id else "GLOBAL"
        return f"{scope} Matris v{self.version} ({self.status})"


class ExchangeMetalRate(TimestampedModel):
    """Base TRY reference rate row belonging to an ExchangeMetalMatrix version."""

    class Unit(models.TextChoices):
        UNIT = "UNIT", "1 Birim / TRY"
        TROY_OZ = "TROY_OZ", "1 Troy Ons / TRY"

    matrix = models.ForeignKey(
        ExchangeMetalMatrix,
        on_delete=models.CASCADE,
        related_name="rates",
    )
    currency_code = models.CharField(max_length=8, db_index=True)
    base_value_try = models.DecimalField(max_digits=16, decimal_places=4)
    unit = models.CharField(max_length=16, choices=Unit.choices, default=Unit.UNIT)
    precision = models.PositiveSmallIntegerField(default=4)

    class Meta:
        db_table = "market_exchange_metal_rate"
        ordering = ["currency_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["matrix", "currency_code"],
                name="uniq_exchange_metal_rate_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.currency_code}={self.base_value_try} TRY (v{self.matrix.version})"

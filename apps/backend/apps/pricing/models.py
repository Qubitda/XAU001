# NOT: pricing modeli catalog.ProductModel'e FK ile bağlıdır; catalog da
# recipe durumunu kontrol etmek için pricing'e bakar. Bu domain'ler birbirinden
# bağımsız deploy edilemez. Bkz: ARCHITECTURE.md#catalog-pricing-coupling
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.catalog.models import ProductModel, ProductVariant
from apps.common.models import TimestampedModel
from apps.market.models import RateSnapshot
from apps.organizations.models import Organization


class PricingRecipe(TimestampedModel):
    """
    Authoritative pricing recipe (FiyatMotoruHesabi) linked to a ProductModel.
    OPS edits & publishes recipes; buyer quotes evaluate the published recipe
    against the latest RateSnapshot so prices stay live with bullion/FX moves.
    """

    class Status(models.TextChoices):
        DRAFT = "TASLAK", "Taslak"
        PUBLISHED = "YAYINLANDI", "Yayında"
        ARCHIVED = "PASIF", "Pasif"

    class PricingMode(models.TextChoices):
        DETAILED = "1", "Model 1 — Detaylı (Maden + İşçilik + Taş + Montür + Diğer)"
        SUPPLIER = "2", "Model 2 — Sade (Tedarikçi Hazır Fiyatı)"

    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name="pricing_recipes")
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    pricing_mode = models.CharField(max_length=2, choices=PricingMode.choices, default=PricingMode.DETAILED)
    lc_currency = models.CharField(max_length=8, default="TRY")
    last_snapshot = models.ForeignKey(RateSnapshot, on_delete=models.SET_NULL, null=True, blank=True)
    source_matrix = models.ForeignKey(
        "market.ExchangeMetalMatrix",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pricing_recipes",
    )
    source_matrix_version = models.PositiveIntegerField(null=True, blank=True)
    applied_rates_snapshot = models.JSONField(default=dict, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    override_metadata = models.JSONField(default=dict, blank=True)
    cached_total_cost_lc = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    cached_b2b_try = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    cached_b2c_try = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    cached_b2c_list_try = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "pricing_recipe"
        constraints = [
            models.UniqueConstraint(fields=["product", "version"], name="uniq_pricing_recipe_version")
        ]
        ordering = ["-version"]

    def __str__(self) -> str:
        return f"{self.product.parent_sku} v{self.version} ({self.status})"


class CostLine(TimestampedModel):
    class LineType(models.TextChoices):
        MADEN = "MADEN", "Maden Maliyeti"
        ISCILIK = "ISCILIK", "Toplam İşçilik Maliyeti"
        TAS = "TAS", "Taş Maliyeti"
        MONTUR = "MONTUR", "Montür Maliyeti"
        DIGER = "DIGER", "Diğer Maliyetler"
        TEDARIKCI = "TEDARIKCI", "Tedarikçi Hazır Fiyatı"

    recipe = models.ForeignKey(PricingRecipe, on_delete=models.CASCADE, related_name="cost_lines")
    line_type = models.CharField(max_length=16, choices=LineType.choices)
    fc_currency = models.CharField(max_length=8, default="USD")
    fc_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    # For MADEN: null = auto-calculated from live Has Gold; non-null = manual override
    fc_price_manual = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    rate_override = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)

    class Meta:
        db_table = "pricing_cost_line"
        constraints = [
            models.UniqueConstraint(fields=["recipe", "line_type"], name="uniq_cost_line_per_recipe")
        ]

    def __str__(self) -> str:
        return f"{self.recipe} · {self.line_type} ({self.fc_currency})"

    def save(self, *args, **kwargs):
        if self.recipe_id:
            status = (
                PricingRecipe.objects.filter(id=self.recipe_id).values_list("status", flat=True).first()
            )
            if status == PricingRecipe.Status.PUBLISHED:
                raise ValidationError(
                    "Yayınlanmış fiyat reçetesinin maliyet satırları değiştirilemez; yeni sürüm oluşturun."
                )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.recipe_id:
            status = (
                PricingRecipe.objects.filter(id=self.recipe_id).values_list("status", flat=True).first()
            )
            if status == PricingRecipe.Status.PUBLISHED:
                raise ValidationError(
                    "Yayınlanmış fiyat reçetesinin maliyet satırları silinemez; yeni sürüm oluşturun."
                )
        return super().delete(*args, **kwargs)


class ChannelRule(TimestampedModel):
    class Channel(models.TextChoices):
        B2B = "B2B", "B2B (Bayi Portalı)"
        B2B_API = "B2B_API", "B2B API"
        B2C_API = "B2C_API", "B2C API"

    recipe = models.ForeignKey(PricingRecipe, on_delete=models.CASCADE, related_name="channel_rules")
    channel = models.CharField(max_length=16, choices=Channel.choices)
    profit_unit = models.CharField(max_length=8, default="%")
    profit_value = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    discount_unit = models.CharField(max_length=8, default="%")
    discount_value = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    # Strictly "Servis Bedeli" per domain rule (never "commission")
    servis_bedeli_unit = models.CharField(max_length=8, default="%")
    servis_bedeli_value = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        db_table = "pricing_channel_rule"
        constraints = [
            models.UniqueConstraint(fields=["recipe", "channel"], name="uniq_channel_rule_per_recipe")
        ]

    def __str__(self) -> str:
        return f"{self.recipe} · {self.channel}"

    def save(self, *args, **kwargs):
        if self.recipe_id:
            status = (
                PricingRecipe.objects.filter(id=self.recipe_id).values_list("status", flat=True).first()
            )
            if status == PricingRecipe.Status.PUBLISHED:
                raise ValidationError(
                    "Yayınlanmış fiyat reçetesinin kanal kuralları değiştirilemez; yeni sürüm oluşturun."
                )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.recipe_id:
            status = (
                PricingRecipe.objects.filter(id=self.recipe_id).values_list("status", flat=True).first()
            )
            if status == PricingRecipe.Status.PUBLISHED:
                raise ValidationError(
                    "Yayınlanmış fiyat reçetesinin kanal kuralları silinemez; yeni sürüm oluşturun."
                )
        return super().delete(*args, **kwargs)


class ImmutablePriceQuoteQuerySet(models.QuerySet):
    """Prevents any mutation or deletion of historical PriceQuote records."""

    def update(self, **kwargs):
        raise ValidationError("PriceQuote kayıtları oluşturulduktan sonra değiştirilemez (immutable).")

    def delete(self):
        raise ValidationError("PriceQuote kayıtları silinemez (immutable).")


class PriceQuote(TimestampedModel):
    """
    Immutable blind-pool price quote generated from a published PricingRecipe + live RateSnapshot.
    Buyer APIs read ONLY final_price_lc / final_price_try / list_price_try — internal audit stays ops-only.
    """

    class Channel(models.TextChoices):
        B2B = "B2B", "B2B"
        B2B_API = "B2B_API", "B2B API"
        B2C_API = "B2C_API", "B2C API"

    product = models.ForeignKey(
        ProductModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes"
    )
    product_sku = models.CharField(max_length=32, blank=True, default="", db_index=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    recipe = models.ForeignKey(
        PricingRecipe, on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes"
    )
    rate_snapshot = models.ForeignKey(RateSnapshot, on_delete=models.PROTECT, related_name="quotes")
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.CharField(max_length=16, choices=Channel.choices)

    lc_currency = models.CharField(max_length=8, default="TRY")
    list_price_try = models.DecimalField(max_digits=14, decimal_places=2)
    final_price_lc = models.DecimalField(max_digits=14, decimal_places=2)
    final_price_try = models.DecimalField(max_digits=14, decimal_places=2)
    effective_discount_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    # Ops-only audit breakdown (stripped in all buyer serializers)
    internal_audit_json = models.JSONField(default=dict)

    objects = ImmutablePriceQuoteQuerySet.as_manager()

    class Meta:
        db_table = "pricing_quote"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("PriceQuote kayıtları oluşturulduktan sonra değiştirilemez (immutable).")
        if self.product_id and not self.product_sku:
            self.product_sku = self.product.parent_sku
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PriceQuote kayıtları silinemez (immutable).")

    def __str__(self) -> str:
        sku = self.product.parent_sku if self.product_id else (self.product_sku or "?")
        return f"{self.channel} {sku} · {self.final_price_try} TRY"


class PriceLock(TimestampedModel):
    """15-minute B2C cart price lock anchored to a RateSnapshot."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="price_locks")
    rate_snapshot = models.ForeignKey(RateSnapshot, on_delete=models.PROTECT)
    expires_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "pricing_lock"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} · {self.rate_snapshot.snapshot_code}"

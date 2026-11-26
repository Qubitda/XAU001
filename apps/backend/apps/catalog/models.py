from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.common.models import TimestampedModel


class ProductModel(TimestampedModel):
    """
    Catalog product card (kimlik): title, category, kind-details, SEO, sales policy.
    NOT physical inventory — stock SSOT is inventory.WarehouseStock via ProductVariant.
    stock_qty / supplier_name / warehouse_location are aggregate or OPS labels only.
    Type-specific physics live on FinishedDetail / MountingDetail / LooseStoneDetail (1:1).
    Pricing authoring: pricing.PricingRecipe (product-level); runtime evaluate per variant.

    Dual-write note: metal/stone/mount columns on this row remain for legacy UI/filters;
    canonical typed fields live on *Detail tables + ProductVariant axes. Buyer APIs must
    never expose fire/cost/owner/ERP/stockQty (see catalog.api serialize_* contracts).
    """

    class ProductKind(models.TextChoices):
        FINISHED = "FINISHED", "Bitmiş Ürün"
        MOUNTING = "MOUNTING", "Montür / Yarı Mamul"
        LOOSE_STONE = "LOOSE_STONE", "Serbest Taş"

    class MountStructure(models.TextChoices):
        FULL = "FULL", "Tek Parça (Full Montür)"
        HEAD_BAND = "HEAD_BAND", "İki Parça (Taç + Kol)"

    class StockStatus(models.TextChoices):
        IN_STOCK = "Stokta", "Stokta"
        MADE_TO_ORDER = "Siparişe Özel", "Siparişe Özel"
        OUT_OF_STOCK = "Tükendi", "Tükendi"

    class OwnershipType(models.TextChoices):
        OWNED = "Öz Mal", "Öz Mal"
        CONSIGNMENT = "Konsinye (Emanet)", "Konsinye (Emanet)"

    class CatalogStatus(models.TextChoices):
        DRAFT = "DRAFT", "Taslak"
        ACTIVE = "ACTIVE", "Yayında"
        ARCHIVED = "ARCHIVED", "Arşiv"

    class LaborCostType(models.TextChoices):
        PER_GRAM = "PER_GRAM", "Gram başı"
        FIXED = "FIXED", "Sabit"

    parent_sku = models.CharField(max_length=32, unique=True, db_index=True)
    erp_code = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    # Central platform catalog when NULL; organization-private catalog when set.
    owner_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="catalog_products",
    )
    barcode = models.CharField(max_length=48, blank=True, default="")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True, default="")
    visual_type = models.CharField(max_length=48, default="solitaire_ring")
    # Canonical kind for strategy pricing / detail routing
    product_kind = models.CharField(
        max_length=16,
        choices=ProductKind.choices,
        default=ProductKind.FINISHED,
        db_index=True,
    )
    # Legacy label (urun_tipi); kept during dual-write
    product_type = models.CharField(max_length=80, blank=True, default="Kuyum (Bitmiş Ürün)")

    collection = models.CharField(max_length=120, db_index=True)
    category = models.CharField(max_length=80, db_index=True)
    sub_category = models.CharField(max_length=120, blank=True, default="")
    style_technique = models.CharField(max_length=80, blank=True, default="Modern")
    occasion = models.CharField(max_length=80, blank=True, default="")
    # Tanım: yas_grubu
    age_group = models.CharField(max_length=48, blank=True, default="Yetişkin")

    # Internal-only operational metadata (NEVER exposed on B2C/B2B serializers)
    supplier_name = models.CharField(max_length=160, blank=True, default="")
    warehouse_location = models.CharField(max_length=80, blank=True, default="")
    ownership_type = models.CharField(
        max_length=32, choices=OwnershipType.choices, default=OwnershipType.OWNED
    )
    stock_status = models.CharField(
        max_length=24, choices=StockStatus.choices, default=StockStatus.IN_STOCK
    )
    stock_qty = models.PositiveIntegerField(default=1)
    # Catalog visibility — independent of pricing recipe publish status.
    catalog_status = models.CharField(
        max_length=16,
        choices=CatalogStatus.choices,
        default=CatalogStatus.ACTIVE,
        db_index=True,
    )
    lead_time_days = models.PositiveSmallIntegerField(default=2)
    # Hardcoded sales channels: B2B / B2B_API / B2C_API
    sales_channels = models.JSONField(default=list, blank=True)

    # Default metal & Montür specification
    metal_name = models.CharField(max_length=40, default="Altın")
    purity_code = models.CharField(max_length=16, default="14K")
    metal_color = models.CharField(max_length=64, default="Beyaz")
    available_colors = models.JSONField(default=list)
    gross_weight_gram = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("3.0000"))
    fire_rate_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("2.00"))

    # Montür FULL vs HEAD+BAND + allowed carat range
    mount_structure = models.CharField(
        max_length=16, choices=MountStructure.choices, default=MountStructure.FULL
    )
    allowed_carat_min = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.100"))
    allowed_carat_max = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("2.000"))
    head_code = models.CharField(max_length=48, blank=True, default="")
    band_code = models.CharField(max_length=48, blank=True, default="")
    head_weight_gram = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    band_weight_gram = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    # Certificate & physical dimensions
    stone_type = models.CharField(max_length=48, default="Pırlanta")
    stone_measure_unit = models.CharField(max_length=8, default="ct")
    stone_clarity = models.CharField(max_length=24, blank=True, default="VS1")
    stone_color_grade = models.CharField(max_length=24, blank=True, default="F")
    stone_cut_grade = models.CharField(max_length=32, blank=True, default="Excellent")
    stone_cut_shape = models.CharField(max_length=64, blank=True, default="Yuvarlak (Round)")
    stone_origin = models.CharField(max_length=48, blank=True, default="Doğal")
    setting_type = models.CharField(max_length=64, blank=True, default="6 Tırnak")
    certificate_agency = models.CharField(max_length=32, blank=True, default="GIA")
    certificate_number = models.CharField(max_length=64, blank=True, default="")

    variant_size = models.PositiveSmallIntegerField(default=14)
    available_sizes = models.JSONField(default=list)
    width_mm = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("2.00"))
    thickness_mm = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.60"))
    height_mm = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("5.20"))
    # Tanım: zincir_tipi / kopca_tipi
    chain_type = models.CharField(max_length=64, blank=True, default="")
    clasp_type = models.CharField(max_length=64, blank=True, default="")
    is_resizable = models.BooleanField(default=True)

    warranty_months = models.PositiveSmallIntegerField(default=24)
    insured_shipping_info = models.CharField(
        max_length=200, default="Tam sigortalı Brinks / Loomis özel kurye"
    )
    return_policy_text = models.TextField(
        default="Standart stok ürünlerinde 14 gün içinde koşulsuz iade; kişiye özel ölçü ve lazer yazı ürünlerinde iade istisnası uygulanır."
    )
    seo_slug = models.SlugField(max_length=240, unique=True)
    meta_title = models.CharField(max_length=240, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "catalog_product_model"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.parent_sku} · {self.title}"


class FinishedDetail(TimestampedModel):
    """1:1 detail for FINISHED (bitmiş kuyum) products."""

    product = models.OneToOneField(
        ProductModel, on_delete=models.CASCADE, related_name="finished_detail"
    )
    metal_name = models.CharField(max_length=40, default="Altın")
    purity_code = models.CharField(max_length=16, default="14K")
    metal_color = models.CharField(max_length=64, default="Beyaz")
    fineness = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("0.5850"))
    base_weight_gr = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("3.0000"))
    fire_rate_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("2.00"))
    labor_cost_type = models.CharField(
        max_length=15,
        choices=ProductModel.LaborCostType.choices,
        default=ProductModel.LaborCostType.FIXED,
    )
    labor_cost_value = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0"))
    stone_summary = models.JSONField(default=dict, blank=True)
    fixed_stone_cost_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    class Meta:
        db_table = "catalog_finished_detail"

    def __str__(self) -> str:
        return f"FinishedDetail({self.product_id})"


class MountingDetail(TimestampedModel):
    """1:1 detail for MOUNTING (montür) products. DYO fields ready for later."""

    product = models.OneToOneField(
        ProductModel, on_delete=models.CASCADE, related_name="mounting_detail"
    )
    metal_name = models.CharField(max_length=40, default="Altın")
    purity_code = models.CharField(max_length=16, default="14K")
    metal_color = models.CharField(max_length=64, default="Beyaz")
    fineness = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("0.5850"))
    net_weight_gr = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("3.0000"))
    labor_cost_type = models.CharField(
        max_length=15,
        choices=ProductModel.LaborCostType.choices,
        default=ProductModel.LaborCostType.FIXED,
    )
    labor_cost_value = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0"))
    mount_structure = models.CharField(
        max_length=16,
        choices=ProductModel.MountStructure.choices,
        default=ProductModel.MountStructure.FULL,
    )
    compatible_shapes = models.JSONField(default=list, blank=True)
    min_carat = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    max_carat = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    min_length_mm = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    max_length_mm = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    min_width_mm = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    max_width_mm = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    setting_labor_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    setting_type_code = models.CharField(max_length=64, blank=True, default="")
    head_code = models.CharField(max_length=48, blank=True, default="")
    band_code = models.CharField(max_length=48, blank=True, default="")
    head_weight_gram = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    band_weight_gram = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    class Meta:
        db_table = "catalog_mounting_detail"

    def __str__(self) -> str:
        return f"MountingDetail({self.product_id})"


class LooseStoneDetail(TimestampedModel):
    """1:1 detail for LOOSE_STONE (serbest taş) products."""

    product = models.OneToOneField(
        ProductModel, on_delete=models.CASCADE, related_name="loose_stone_detail"
    )
    stone_category = models.CharField(max_length=48, default="Pırlanta")
    shape = models.CharField(max_length=64, blank=True, default="")
    carat = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0"))
    color = models.CharField(max_length=24, blank=True, default="")
    clarity = models.CharField(max_length=24, blank=True, default="")
    cut_grade = models.CharField(max_length=32, blank=True, default="")
    cert_lab = models.CharField(max_length=32, blank=True, default="")
    cert_number = models.CharField(max_length=64, blank=True, default="")
    cert_url = models.URLField(max_length=500, blank=True, default="")
    measurements_mm = models.CharField(max_length=64, blank=True, default="")
    length_mm = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    width_mm = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    depth_mm = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    rapaport_price_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    net_cost_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    supplier_id = models.CharField(max_length=64, blank=True, default="INTERNAL")

    class Meta:
        db_table = "catalog_loose_stone_detail"
        indexes = [
            models.Index(
                fields=["shape", "carat", "color", "clarity"],
                name="idx_loose_stone_4c",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["cert_number"],
                condition=~models.Q(cert_number=""),
                name="uniq_loose_stone_cert_number_nonzero",
            ),
        ]

    def __str__(self) -> str:
        return f"LooseStoneDetail({self.product_id})"


class StoneLine(TimestampedModel):
    """Multiple stone lines per ProductModel (Center, Side, Pavé, Accent)."""

    class Role(models.TextChoices):
        MERKEZ = "MERKEZ", "Merkez Taş"
        YAN = "YAN", "Yan Taş"
        PAVE = "PAVE", "Pavé"
        AKSAN = "AKSAN", "Aksan"

    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name="stone_lines")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MERKEZ)
    stone_type = models.CharField(max_length=48, default="Pırlanta")
    measure_unit = models.CharField(max_length=8, default="ct")
    count = models.PositiveSmallIntegerField(default=1)
    carat = models.DecimalField(max_digits=8, decimal_places=4)
    clarity = models.CharField(max_length=24, blank=True, default="")
    color_grade = models.CharField(max_length=24, blank=True, default="")
    cut_shape = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "catalog_stone_line"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.product.parent_sku} · {self.role} {self.count}x{self.carat}{self.measure_unit} {self.stone_type}"


class ProductVariant(TimestampedModel):
    """
    Sellable configuration under a product card (renk/ayar/ölçü/karat axes).
    stock_qty is a synced aggregate from WarehouseStock — do not treat as SSOT.
    Prices are not stored here; PricingRecipe evaluates with this variant's params.
    """

    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64, unique=True, db_index=True)
    purity_code = models.CharField(max_length=16)
    metal_color = models.CharField(max_length=64)
    size = models.PositiveSmallIntegerField(default=14)
    center_stone_carat = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"))
    gross_weight_gram = models.DecimalField(max_digits=10, decimal_places=4)
    # Aggregate available stock synced from inventory.WarehouseStock (not SSOT)
    stock_qty = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "catalog_product_variant"
        ordering = ["-is_default", "purity_code", "metal_color", "size"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "purity_code", "metal_color", "size", "center_stone_carat"],
                name="uniq_variant_axes_per_product",
            )
        ]

    def __str__(self) -> str:
        return f"{self.sku} ({self.purity_code} {self.metal_color} #{self.size})"


class ProductMedia(TimestampedModel):
    class MediaRole(models.TextChoices):
        GALLERY_MAIN = "GALLERY_MAIN", "Ana Stüdyo"
        ON_HAND = "ON_HAND", "Elde / Model"
        MACRO = "MACRO", "Makro Detay"
        VIDEO_REELS = "VIDEO_REELS", "Video / Reels"
        SPIN_360 = "SPIN_360", "360 Derece"
        CERTIFICATE_PDF = "CERTIFICATE_PDF", "Sertifika"

    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name="media_items")
    metal_color = models.CharField(max_length=24, default="Beyaz")
    role = models.CharField(max_length=24, choices=MediaRole.choices, default=MediaRole.GALLERY_MAIN)
    url = models.URLField(max_length=500)
    sort_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "catalog_product_media"
        ordering = ["metal_color", "sort_order"]

    def __str__(self) -> str:
        return f"{self.product.parent_sku} · {self.metal_color} ({self.role})"


class Favorite(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name="favorited_by")

    class Meta:
        db_table = "catalog_favorite"
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="uniq_favorite_user_product")
        ]

    def __str__(self) -> str:
        return f"{self.user.email} ♥ {self.product.parent_sku}"

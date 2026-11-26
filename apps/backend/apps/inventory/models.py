from django.conf import settings
from django.db import models
from apps.catalog.models import ProductModel, ProductVariant
from apps.common.models import TimestampedModel
from apps.organizations.models import Branch, Organization


class Warehouse(TimestampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_warehouse"

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class WarehouseStock(TimestampedModel):
    """
    Physical inventory SSOT: Variant × Warehouse (quantity / reserved).
    Catalog Product/ProductVariant.stock_qty are synchronized aggregates only.
    Ownership / custody / lot attributes live on the stock row — not on ProductVariant.
    """

    class OwnershipType(models.TextChoices):
        OWNED = "OWNED", "Öz Mal"
        CONSIGNMENT = "CONSIGNMENT", "Konsinye"
        CUSTODY = "CUSTODY", "Emanet"

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="warehouse_stocks"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="variant_stocks"
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_qty = models.PositiveIntegerField(default=0)

    # Physical stock identity (marketplace / jewelry inventory)
    owner_organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_warehouse_stocks",
    )
    controller_organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="controlled_warehouse_stocks",
    )
    source_supplier_name = models.CharField(max_length=160, blank=True, default="")
    ownership_type = models.CharField(
        max_length=16, choices=OwnershipType.choices, default=OwnershipType.OWNED
    )
    gross_weight_gram = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    certificate_number = models.CharField(max_length=64, blank=True, default="")
    lot_or_serial = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "inventory_warehouse_stock"
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "warehouse"],
                name="uniq_warehouse_stock_variant_warehouse",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="chk_warehouse_stock_quantity_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_qty__gte=0),
                name="chk_warehouse_stock_reserved_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_qty__lte=models.F("quantity")),
                name="chk_warehouse_stock_reserved_lte_quantity",
            ),
        ]

    @property
    def available_qty(self) -> int:
        return max(0, self.quantity - self.reserved_qty)

    def __str__(self) -> str:
        return f"{self.warehouse.code} · {self.variant.sku} ({self.available_qty}/{self.quantity})"


class StockMovement(TimestampedModel):
    """
    Inventory ledger. New writes must set variant (product-only movements are deprecated).
    Idempotency: (variant, warehouse, reference_no, movement_type) is unique when both FKs set.
    """

    class MovementType(models.TextChoices):
        INBOUND = "INBOUND", "Stok Girişi"
        RESERVE = "RESERVE", "Sipariş Rezervasyonu"
        RELEASE = "RELEASE", "Rezervasyon İptali"
        SHIP = "SHIP", "Sevkiyat Çıkışı"

    product = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="stock_movements")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_movements"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_movements"
    )
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity_delta = models.IntegerField()
    reference_no = models.CharField(max_length=64, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    # Jewelry traceability (optional; complements quantity ledger)
    gross_weight_gram = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    purity_code = models.CharField(max_length=16, blank=True, default="")
    certificate_number = models.CharField(max_length=64, blank=True, default="")
    lot_or_serial = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "inventory_stock_movement"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "warehouse", "reference_no", "movement_type"],
                condition=models.Q(variant__isnull=False, warehouse__isnull=False),
                name="uniq_stock_movement_reference",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.quantity_delta:+d} · {self.reference_no}"

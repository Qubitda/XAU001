"""
Marketplace / sourcing domain for Direct Marketplace + Managed Trading.

Kept separate from commerce.B2bOrder so a parent buyer order can split into
supplier orders and allocations without bloating the B2B order aggregate.
"""

from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.catalog.models import ProductModel, ProductVariant
from apps.commerce.models import B2bOrder, B2bOrderLine
from apps.common.models import TimestampedModel
from apps.inventory.models import Warehouse, WarehouseStock
from apps.organizations.models import Organization


class SellerOffer(TimestampedModel):
    """Seller-published commercial offer for a product/variant (price & terms)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Taslak"
        ACTIVE = "ACTIVE", "Aktif"
        PAUSED = "PAUSED", "Duraklatıldı"
        EXPIRED = "EXPIRED", "Süresi Doldu"

    class Channel(models.TextChoices):
        B2B = "B2B", "B2B Portal"
        B2B_API = "B2B_API", "B2B API"
        B2C_API = "B2C_API", "B2C API"

    seller_organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="seller_offers"
    )
    product = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="seller_offers")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="seller_offers"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="seller_offers"
    )
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.B2B)
    currency = models.CharField(max_length=8, default="TRY")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    min_qty = models.PositiveIntegerField(default=1)
    max_qty = models.PositiveIntegerField(null=True, blank=True)
    lead_time_days = models.PositiveSmallIntegerField(default=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "marketplace_seller_offer"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller_organization", "status"], name="idx_offer_seller_status"),
            models.Index(fields=["product", "status"], name="idx_offer_product_status"),
        ]

    def __str__(self) -> str:
        return f"Offer {self.product.parent_sku} · {self.seller_organization.code} ({self.status})"


class BuyRequest(TimestampedModel):
    """Buyer RFQ / demand signal."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Açık"
        QUOTED = "QUOTED", "Teklif Alındı"
        AWARDED = "AWARDED", "Kazanan Seçildi"
        CANCELLED = "CANCELLED", "İptal"
        EXPIRED = "EXPIRED", "Süresi Doldu"

    buyer_organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="buy_requests"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="buy_requests"
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    needed_by = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "marketplace_buy_request"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"RFQ {self.title} · {self.buyer_organization.code}"


class BuyRequestLine(TimestampedModel):
    request = models.ForeignKey(BuyRequest, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(
        ProductModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    description = models.CharField(max_length=240, blank=True, default="")
    qty = models.PositiveIntegerField(default=1)
    target_unit_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default="TRY")

    class Meta:
        db_table = "marketplace_buy_request_line"

    def __str__(self) -> str:
        return f"{self.request_id} · qty={self.qty}"


class BuyRequestResponse(TimestampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Gönderildi"
        ACCEPTED = "ACCEPTED", "Kabul"
        REJECTED = "REJECTED", "Red"
        WITHDRAWN = "WITHDRAWN", "Geri Çekildi"

    request = models.ForeignKey(BuyRequest, on_delete=models.CASCADE, related_name="responses")
    seller_organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="buy_request_responses"
    )
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=8, default="TRY")
    lead_time_days = models.PositiveSmallIntegerField(default=2)
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED)
    seller_offer = models.ForeignKey(
        SellerOffer, on_delete=models.SET_NULL, null=True, blank=True, related_name="rfq_responses"
    )

    class Meta:
        db_table = "marketplace_buy_request_response"
        constraints = [
            models.UniqueConstraint(
                fields=["request", "seller_organization"],
                name="uniq_buy_request_response_per_seller",
            )
        ]

    def __str__(self) -> str:
        return f"Response {self.request_id} · {self.seller_organization.code}"


class SupplierOrder(TimestampedModel):
    """Split of a parent B2B order toward a concrete supplier / seller."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Taslak"
        CONFIRMED = "CONFIRMED", "Onaylandı"
        IN_PRODUCTION = "IN_PRODUCTION", "Üretimde"
        SHIPPED = "SHIPPED", "Sevk Edildi"
        RECEIVED = "RECEIVED", "Teslim Alındı"
        CANCELLED = "CANCELLED", "İptal"

    order_no = models.CharField(max_length=40, unique=True, db_index=True)
    parent_b2b_order = models.ForeignKey(
        B2bOrder, on_delete=models.PROTECT, null=True, blank=True, related_name="supplier_orders"
    )
    supplier_organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="supplier_orders"
    )
    buyer_organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="sourced_supplier_orders"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    currency = models.CharField(max_length=8, default="TRY")
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "marketplace_supplier_order"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_no} · {self.supplier_organization.code}"


class SupplierOrderLine(TimestampedModel):
    supplier_order = models.ForeignKey(SupplierOrder, on_delete=models.CASCADE, related_name="lines")
    parent_line = models.ForeignKey(
        B2bOrderLine, on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_lines"
    )
    product = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="+")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="TRY")
    sku = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "marketplace_supplier_order_line"

    def __str__(self) -> str:
        return f"{self.supplier_order.order_no} · {self.sku or self.product.parent_sku} x{self.qty}"


class OrderAllocation(TimestampedModel):
    """Which stock / supplier / offer fulfills which buyer order line qty."""

    class OwnershipType(models.TextChoices):
        OWNED = "OWNED", "Öz Mal"
        CONSIGNMENT = "CONSIGNMENT", "Konsinye"
        CUSTODY = "CUSTODY", "Emanet"

    b2b_order_line = models.ForeignKey(
        B2bOrderLine, on_delete=models.CASCADE, related_name="allocations"
    )
    supplier_order_line = models.ForeignKey(
        SupplierOrderLine, on_delete=models.SET_NULL, null=True, blank=True, related_name="allocations"
    )
    warehouse_stock = models.ForeignKey(
        WarehouseStock, on_delete=models.SET_NULL, null=True, blank=True, related_name="allocations"
    )
    seller_offer = models.ForeignKey(
        SellerOffer, on_delete=models.SET_NULL, null=True, blank=True, related_name="allocations"
    )
    qty = models.PositiveIntegerField(default=1)
    ownership_type = models.CharField(
        max_length=16, choices=OwnershipType.choices, default=OwnershipType.OWNED
    )
    owner_organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_allocations",
    )
    controller_organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="controlled_allocations",
    )

    class Meta:
        db_table = "marketplace_order_allocation"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Alloc {self.b2b_order_line_id} x{self.qty}"


class Settlement(TimestampedModel):
    """Financial settlement between buyer, seller, and platform."""

    class SettlementType(models.TextChoices):
        BUYER_CHARGE = "BUYER_CHARGE", "Alıcı Tahsilatı"
        SELLER_PAYOUT = "SELLER_PAYOUT", "Satıcı Ödemesi"
        PLATFORM_FEE = "PLATFORM_FEE", "Platform Servis Bedeli"
        ADJUSTMENT = "ADJUSTMENT", "Düzeltme"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Bekliyor"
        SETTLED = "SETTLED", "Tamamlandı"
        FAILED = "FAILED", "Başarısız"
        CANCELLED = "CANCELLED", "İptal"

    counterparty_organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="settlements"
    )
    b2b_order = models.ForeignKey(
        B2bOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="settlements"
    )
    supplier_order = models.ForeignKey(
        SupplierOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="settlements"
    )
    settlement_type = models.CharField(max_length=24, choices=SettlementType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=8, default="TRY")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    reference_no = models.CharField(max_length=64, blank=True, default="", db_index=True)
    notes = models.TextField(blank=True, default="")
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "marketplace_settlement"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.settlement_type} {self.amount} {self.currency} · {self.status}"

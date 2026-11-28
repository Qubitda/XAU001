"""Shared helper utilities and constants for commerce services."""
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from apps.catalog.models import ProductModel, ProductVariant
from apps.organizations.models import Organization
from apps.pricing.services import resolve_product_variant
from apps.production.models import WorkOrder
from config.exceptions import DomainError

from ..models import B2cOrder

MONEY_Q = Decimal("0.01")
GRAM_Q = Decimal("0.0001")
BANK_TRANSFER_DISCOUNT_RATE = Decimal("0.03")
VAT_DIVISOR = Decimal("1.20")



def _q2(val: Decimal) -> Decimal:
    return val.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def _q4(val: Decimal) -> Decimal:
    return val.quantize(GRAM_Q, rounding=ROUND_HALF_UP)


def _resolve_size_unit_label(category: str) -> str:
    if "Bileklik" in category or "Bilezik" in category:
        return "Bileklik Boyu"
    if "Kolye" in category:
        return "Zincir Boyu"
    if "Küpe" in category:
        return "Çap / Boy"
    return "Yüzük Ölçüsü"


def _build_line_sku(product: ProductModel, variant: ProductVariant | None, metal_color: str, size: int) -> str:
    if variant is not None:
        return variant.sku if size == variant.size else f"{variant.sku}-SZ{size}"
    color_code = {"Beyaz": "BYZ", "Sarı": "SRY", "Rose": "RSE"}.get(metal_color, "BYZ")
    return f"{product.parent_sku}-{product.purity_code}-{color_code}-{size}"


def _resolve_product_and_variant(
    payload: dict,
    *,
    organization: Organization | None = None,
    is_ops: bool = False,
) -> tuple[ProductModel, ProductVariant | None]:
    variant_id = payload.get("variantId")
    variant_sku = payload.get("variantSku")
    parent_sku = (payload.get("parentSku") or "").strip().upper()

    product: ProductModel | None = None
    variant: ProductVariant | None = None

    if variant_id:
        variant = (
            ProductVariant.objects.select_related("product")
            .filter(id=variant_id, is_active=True)
            .first()
        )
        if variant is None:
            raise DomainError(f"Varyant bulunamadı: {variant_id}", code="VARIANT_NOT_FOUND", status_code=404)
        product = variant.product
    elif variant_sku:
        variant = (
            ProductVariant.objects.select_related("product")
            .filter(sku__iexact=str(variant_sku).strip(), is_active=True)
            .first()
        )
        if variant is None:
            raise DomainError(f"Varyant SKU bulunamadı: {variant_sku}", code="VARIANT_NOT_FOUND", status_code=404)
        product = variant.product
    else:
        product = ProductModel.objects.filter(parent_sku=parent_sku).prefetch_related("stone_lines").first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        variant = resolve_product_variant(
            product,
            purity_code=payload.get("purityCode"),
            metal_color=payload.get("metalColor"),
            size=payload.get("size"),
        )

    # Enforce catalog ownership isolation
    if product.owner_organization_id is not None and not is_ops:
        if organization is None or product.owner_organization_id != organization.id:
            raise DomainError(f"Ürün bulunamadı: {product.parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)

    return product, variant


@transaction.atomic
def _b2c_order_needs_workshop(items) -> bool:
    return any(
        item.stock_status == "Siparişe Özel" or bool((item.engraving_text or "").strip())
        for item in items
    )


def _create_work_orders_for_b2c_order(order: B2cOrder) -> None:
    for idx, item in enumerate(order.items.all(), start=1):
        if item.stock_status == "Siparişe Özel" or (item.engraving_text or "").strip():
            WorkOrder.objects.get_or_create(
                work_order_no=f"WO-{order.order_no}-{idx}",
                defaults={
                    "source_order_no": order.order_no,
                    "sku": item.sku,
                    "size": item.size,
                    "quantity": item.qty,
                    "engraving_or_stamp_note": item.engraving_text,
                },
            )


"""Domain services for catalog publishing gates and variant synchronization."""
from __future__ import annotations

from decimal import Decimal

from apps.catalog.models import ProductMedia, ProductModel, StoneLine
from apps.pricing.models import PricingRecipe


def validate_publishable(product: ProductModel) -> list[str]:
    """
    Return a list of unmet publish conditions for transitioning a ProductModel to ACTIVE.
    Empty list means the product satisfies all publish gates.
    """
    missing: list[str] = []
    if not (product.title or "").strip() or len((product.title or "").strip()) < 4:
        missing.append("TITLE_REQUIRED")
    if not (product.category or "").strip():
        missing.append("CATEGORY_REQUIRED")
    if product.gross_weight_gram is None or product.gross_weight_gram < Decimal("0.01"):
        missing.append("GROSS_WEIGHT_REQUIRED")
    if not PricingRecipe.objects.filter(
        product=product, status=PricingRecipe.Status.PUBLISHED
    ).exists():
        missing.append("PUBLISHED_RECIPE_REQUIRED")
    if not product.variants.filter(is_active=True).exists():
        missing.append("ACTIVE_VARIANT_REQUIRED")
    if not (product.sales_channels or []):
        missing.append("SALES_CHANNEL_REQUIRED")
    if not product.media_items.filter(role=ProductMedia.MediaRole.GALLERY_MAIN).exists():
        missing.append("GALLERY_MAIN_MEDIA_REQUIRED")
    return missing


def sync_default_variant_center_carat(product: ProductModel) -> Decimal:
    """Recompute center_stone_carat from MERKEZ stone lines and sync default ProductVariant."""
    merkez_lines = list(product.stone_lines.filter(role=StoneLine.Role.MERKEZ))
    total = sum((line.carat * line.count for line in merkez_lines), Decimal("0.000"))
    default_v = product.variants.filter(is_default=True).first()
    if default_v is not None and default_v.center_stone_carat != total:
        default_v.center_stone_carat = total
        default_v.save(update_fields=["center_stone_carat", "updated_at"])
    return total

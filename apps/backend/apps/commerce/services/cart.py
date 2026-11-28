"""B2C cart and B2B draft line services."""
from decimal import Decimal

from django.db import transaction

from apps.catalog.models import ProductModel
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Organization
from apps.pricing.models import PriceLock
from apps.pricing.services import (
    compute_size_adjusted_gross_weight,
    create_live_quote,
    get_active_price_lock,
    get_or_refresh_price_lock,
    resolve_product_variant,
)
from config.exceptions import DomainError

from ..models import B2bDraftLine, B2cCartItem
from .helpers import (
    _build_line_sku,
    _q2,
    _q4,
    _resolve_product_and_variant,
    _resolve_size_unit_label,
)


@transaction.atomic
def refresh_b2c_cart_price_lock(*, user) -> PriceLock:
    """
    Creates a fresh 15-minute PriceLock on the current RateSnapshot and atomically
    re-prices every B2C cart item against that same snapshot & its exact ProductVariant.
    """
    lock = get_or_refresh_price_lock(user, force_refresh=True)
    snap = lock.rate_snapshot
    cart_items = list(
        B2cCartItem.objects.select_for_update(of=("self",)).select_related("variant").filter(user=user)
    )
    for item in cart_items:
        product = ProductModel.objects.filter(parent_sku=item.parent_sku).first()
        if product is None:
            raise DomainError(
                f"Sepetteki ürün artık mevcut değil: {item.parent_sku}",
                code="PRODUCT_NOT_FOUND",
                status_code=404,
            )
        variant = item.variant or resolve_product_variant(
            product,
            purity_code=item.purity_code,
            metal_color=item.metal_color,
            size=item.size,
        )
        quote, _ = create_live_quote(
            product=product,
            channel="B2C",
            variant=variant,
            snapshot=snap,
            size=item.size,
        )
        item.variant = quote.variant
        item.gross_weight_gram = compute_size_adjusted_gross_weight(
            product, item.size, variant=quote.variant
        )
        item.unit_list_price_try = _q2(quote.list_price_try)
        item.unit_final_price_try = _q2(quote.final_price_try)
        item.rate_snapshot = snap
        item.price_quote = quote
        item.snapshot_code = snap.snapshot_code
        item.save(
            update_fields=[
                "variant",
                "gross_weight_gram",
                "unit_list_price_try",
                "unit_final_price_try",
                "rate_snapshot",
                "price_quote",
                "snapshot_code",
                "updated_at",
            ]
        )
    return lock


@transaction.atomic
def add_b2c_cart_item(*, user, payload: dict) -> B2cCartItem:
    """
    Server-authoritative B2C cart addition anchored to a single active PriceLock
    and a concrete ProductVariant.
    """
    from ..recovery import touch_b2c_cart

    product, variant = _resolve_product_and_variant(payload)

    lock = get_active_price_lock(user)
    if lock is None:
        lock = refresh_b2c_cart_price_lock(user=user)
    snap = lock.rate_snapshot

    size = int(payload.get("size") or (variant.size if variant else product.variant_size))
    metal_color = variant.metal_color if variant else (payload.get("metalColor") or product.metal_color)
    purity_code = variant.purity_code if variant else product.purity_code
    qty = int(payload.get("qty", 1))
    engraving_text = payload.get("engravingText", "").strip()[:40]
    gift_wrap = bool(payload.get("giftWrap", False))
    gift_note = payload.get("giftNote", "").strip()[:200]

    quote, _ = create_live_quote(
        product=product,
        channel="B2C",
        variant=variant,
        snapshot=snap,
        size=size,
    )
    resolved_variant = quote.variant
    sku = _build_line_sku(product, resolved_variant, metal_color, size)
    gross_gram = compute_size_adjusted_gross_weight(product, size, variant=resolved_variant)

    variant_stock_status = product.stock_status
    if product.stock_status != ProductModel.StockStatus.MADE_TO_ORDER:
        available_qty = resolved_variant.stock_qty if resolved_variant is not None else product.stock_qty
        variant_stock_status = (
            ProductModel.StockStatus.IN_STOCK
            if available_qty > 0
            else ProductModel.StockStatus.OUT_OF_STOCK
        )

    if variant_stock_status == ProductModel.StockStatus.OUT_OF_STOCK:
        raise CommerceError(
            "Bu ürün veya seçilen ölçü şu anda stokta bulunmuyor.",
            status_code=400,
        )

    lead_time = (
        "1–2 iş günü sigortalı kurye teslimatı"
        if variant_stock_status == ProductModel.StockStatus.IN_STOCK and not engraving_text
        else f"{product.lead_time_days}–{product.lead_time_days + 2} iş günü atölye üretim + sigortalı teslimat"
    )

    existing = B2cCartItem.objects.select_for_update().filter(
        user=user,
        sku=sku,
        size=size,
        engraving_text__iexact=engraving_text,
        gift_wrap=gift_wrap,
    ).first()
    if existing is not None:
        existing.variant = resolved_variant
        existing.qty = min(10, existing.qty + qty)
        existing.gross_weight_gram = gross_gram
        existing.unit_list_price_try = _q2(quote.list_price_try)
        existing.unit_final_price_try = _q2(quote.final_price_try)
        existing.rate_snapshot = snap
        existing.price_quote = quote
        existing.snapshot_code = snap.snapshot_code
        existing.save(
            update_fields=[
                "variant",
                "qty",
                "gross_weight_gram",
                "unit_list_price_try",
                "unit_final_price_try",
                "rate_snapshot",
                "price_quote",
                "snapshot_code",
                "updated_at",
            ]
        )
        touch_b2c_cart(user=user)
        from ..cart_sync import sync_user_cart
        from ..models import CartEvent

        sync_user_cart(
            user=user,
            event_type=CartEvent.EventType.PRODUCT_ADDED,
            payload={"sku": existing.sku, "qty": existing.qty, "updated": True},
        )
        return existing

    loose = getattr(product, "loose_stone_detail", None) if hasattr(product, "loose_stone_detail") else None
    cert_agency = (loose.cert_lab if loose else "") or product.certificate_agency
    cert_number = (loose.cert_number if loose else "") or product.certificate_number
    cert_label = (
        f"{cert_agency} · {cert_number}"
        if cert_number
        else (f"{cert_agency} Sertifikalı" if cert_agency else "")
    )
    item = B2cCartItem.objects.create(
        user=user,
        variant=resolved_variant,
        sku=sku,
        parent_sku=product.parent_sku,
        title=product.title,
        category=product.category,
        metal_color=metal_color,
        purity_code=purity_code,
        size=size,
        size_unit_label=_resolve_size_unit_label(product.category),
        qty=qty,
        engraving_text=engraving_text,
        gift_wrap=gift_wrap,
        gift_note=gift_note,
        certificate_label=cert_label,
        stock_status=variant_stock_status,
        lead_time_text=lead_time,
        gross_weight_gram=gross_gram,
        unit_list_price_try=_q2(quote.list_price_try),
        unit_final_price_try=_q2(quote.final_price_try),
        rate_snapshot=snap,
        price_quote=quote,
        snapshot_code=snap.snapshot_code,
    )
    touch_b2c_cart(user=user)
    from ..cart_sync import sync_user_cart
    from ..models import CartEvent

    cart = sync_user_cart(
        user=user,
        event_type=CartEvent.EventType.PRODUCT_ADDED,
        payload={"sku": item.sku, "qty": item.qty},
    )
    if cart is not None and item.cart_id is None:
        item.cart = cart
        item.save(update_fields=["cart", "updated_at"])
    return item


@transaction.atomic
def add_b2b_draft_lines(
    *,
    user,
    organization: Organization,
    items: list[dict],
    is_ops: bool = False,
) -> list[B2bDraftLine]:
    """
    Server-authoritative B2B wholesale draft line creation anchored to concrete ProductVariant.
    """
    from ..recovery import touch_b2b_draft

    snap = get_current_rate_snapshot()
    usd_try = snap.live_usd_sell
    if usd_try <= 0:
        raise DomainError("Geçerli USD/TRY satış kuru bulunamadı.", code="INVALID_RATE", status_code=500)

    created: list[B2bDraftLine] = []
    for entry in items:
        product, variant = _resolve_product_and_variant(
            entry, organization=organization, is_ops=is_ops
        )

        size = int(entry.get("size") or (variant.size if variant else product.variant_size))
        metal_color = variant.metal_color if variant else (entry.get("metalColor") or product.metal_color)
        purity_code = variant.purity_code if variant else product.purity_code
        qty = int(entry.get("qty", 1))
        available_stock = variant.stock_qty if variant is not None else product.stock_qty
        supply_type = entry.get("supplyType") or (
            "STOCK"
            if available_stock >= qty and product.stock_status == ProductModel.StockStatus.IN_STOCK
            else "PRODUCTION"
        )
        dealer_stamp_note = entry.get("dealerStampNote", "").strip()[:80]

        quote, output = create_live_quote(
            product=product,
            channel="B2B",
            variant=variant,
            organization=organization,
            snapshot=snap,
            size=size,
        )
        resolved_variant = quote.variant

        gross_gram = compute_size_adjusted_gross_weight(product, size, variant=resolved_variant)
        net_metal_gram = _q4(output.net_metal_gram)
        fire_included_fine = _q4(output.fire_included_fine_metal_gram)

        wholesale_try = _q2(quote.final_price_try)
        wholesale_usd = _q2(wholesale_try / usd_try)
        metal_value_try = fire_included_fine * snap.live_has_gold_try_sell
        labor_and_stone_usd = _q2(max(Decimal("0.00"), (wholesale_try - metal_value_try) / usd_try))

        sku = _build_line_sku(product, resolved_variant, metal_color, size)

        existing = B2bDraftLine.objects.select_for_update().filter(
            organization=organization,
            sku=sku,
            size=size,
            supply_type=supply_type,
            dealer_stamp_note__iexact=dealer_stamp_note,
        ).first()
        if existing is not None:
            existing.variant = resolved_variant
            existing.qty = min(500, existing.qty + qty)
            existing.unit_gross_gram = gross_gram
            existing.unit_net_metal_gram = net_metal_gram
            existing.unit_fire_included_fine_gram = fire_included_fine
            existing.unit_labor_and_stone_usd = labor_and_stone_usd
            existing.unit_wholesale_usd = wholesale_usd
            existing.unit_wholesale_try = wholesale_try
            existing.rate_snapshot = snap
            existing.price_quote = quote
            existing.snapshot_code = snap.snapshot_code
            existing.save()
            created.append(existing)
            continue

        created.append(
            B2bDraftLine.objects.create(
                organization=organization,
                created_by=user,
                variant=resolved_variant,
                sku=sku,
                parent_sku=product.parent_sku,
                title=product.title,
                category=product.category,
                metal_color=metal_color,
                purity_code=purity_code,
                size=size,
                size_unit_label=_resolve_size_unit_label(product.category),
                qty=qty,
                supply_type=supply_type,
                dealer_stamp_note=dealer_stamp_note,
                unit_gross_gram=gross_gram,
                unit_net_metal_gram=net_metal_gram,
                unit_fire_included_fine_gram=fire_included_fine,
                unit_labor_and_stone_usd=labor_and_stone_usd,
                unit_wholesale_usd=wholesale_usd,
                unit_wholesale_try=wholesale_try,
                pricing_currency=output.lc_currency,
                rate_snapshot=snap,
                price_quote=quote,
                snapshot_code=snap.snapshot_code,
            )
        )
    touch_b2b_draft(user=user, organization=organization)
    return created

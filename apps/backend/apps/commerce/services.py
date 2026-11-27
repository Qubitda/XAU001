import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record_audit
from apps.catalog.models import ProductModel, ProductVariant
from apps.customers.models import Customer
from apps.finance.models import DealerLedgerEntry
from apps.finance.services import reserve_organization_limits, reverse_organization_limits
from apps.inventory.services import (
    release_variant_stock,
    reserve_product_stock,
    reserve_variant_stock,
)
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Branch, Organization
from apps.pricing.models import PriceLock
from apps.pricing.services import (
    compute_size_adjusted_gross_weight,
    create_live_quote,
    get_active_price_lock,
    get_or_refresh_price_lock,
    resolve_product_variant,
)
from apps.production.models import WorkOrder
from apps.webhooks.services import emit_webhook_event
from config.exceptions import DomainError
from .models import B2bDraftLine, B2bOrder, B2bOrderLine, B2cCartItem, B2cOrder, B2cOrderItem


def _schedule_b2c_order_created_webhook(order: B2cOrder) -> None:
    order_no = order.order_no
    status = order.status
    total = str(order.grand_total_try)

    def _emit() -> None:
        # Platform-only: never fan out to dealer organization endpoints.
        emit_webhook_event(
            "b2c.order.created",
            {"orderNo": order_no, "status": status, "grandTotalTry": total},
            platform=True,
        )

    transaction.on_commit(_emit)


def _emit_b2c_payment_success_mail(order: B2cOrder) -> None:
    """Event-driven payment receipt — MailLog in same TX; Celery enqueue on commit."""
    from django.conf import settings as dj_settings

    from apps.mail.events import emit_payment_success

    recipient = (order.shipping_email or getattr(order.customer, "email", "") or "").strip()
    if not recipient:
        return
    base = (getattr(dj_settings, "FRONTEND_STOREFRONT_URL", "") or "http://localhost:3000").rstrip("/")
    emit_payment_success(
        recipient=recipient,
        customer_name=order.shipping_full_name or getattr(order.customer, "full_name", "") or "",
        order_no=order.order_no,
        amount=str(order.grand_total_try),
        currency="TRY",
        date=timezone.localtime(order.updated_at).strftime("%d.%m.%Y %H:%M"),
        order_url=f"{base}/hesabim/siparisler/{order.order_no}",
    )


def _schedule_b2b_order_created_webhook(order: B2bOrder) -> None:
    order_no = order.order_no
    org_id = order.organization_id
    status = order.status
    total_usd = str(order.total_wholesale_usd)

    def _emit() -> None:
        emit_webhook_event(
            "b2b.order.created",
            {"orderNo": order_no, "status": status, "totalWholesaleUsd": total_usd},
            organization_id=org_id,
        )

    transaction.on_commit(_emit)


def _schedule_b2b_order_status_webhook(*, order: B2bOrder, previous: str, current: str) -> None:
    order_no = order.order_no
    org_id = order.organization_id

    def _emit() -> None:
        emit_webhook_event(
            "b2b.order.status",
            {"orderNo": order_no, "fromStatus": previous, "toStatus": current, "status": current},
            organization_id=org_id,
        )

    transaction.on_commit(_emit)


MONEY_Q = Decimal("0.01")
GRAM_Q = Decimal("0.0001")
BANK_TRANSFER_DISCOUNT_RATE = Decimal("0.03")
VAT_DIVISOR = Decimal("1.20")

# ── Centralized Order Status State Machines ──────────────────────────────
B2C_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    B2cOrder.Status.PENDING_PAYMENT: {
        B2cOrder.Status.CONFIRMED,
        B2cOrder.Status.WORKSHOP,
        B2cOrder.Status.CANCELLED,
    },
    B2cOrder.Status.CONFIRMED: {
        B2cOrder.Status.WORKSHOP,
        B2cOrder.Status.SHIPPED,
        B2cOrder.Status.CANCELLED,
    },
    B2cOrder.Status.WORKSHOP: {
        B2cOrder.Status.SHIPPED,
        B2cOrder.Status.CANCELLED,
    },
    B2cOrder.Status.SHIPPED: {
        B2cOrder.Status.REFUNDED,
    },
    B2cOrder.Status.CANCELLED: set(),
    B2cOrder.Status.REFUNDED: set(),
}

B2B_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    B2bOrder.Status.PROFORMA_CONFIRMED: {
        B2bOrder.Status.WORKSHOP_PLANNED,
        B2bOrder.Status.READY_FOR_DISPATCH,
        B2bOrder.Status.CANCELLED,
    },
    B2bOrder.Status.WORKSHOP_PLANNED: {
        B2bOrder.Status.READY_FOR_DISPATCH,
        B2bOrder.Status.CANCELLED,
    },
    B2bOrder.Status.READY_FOR_DISPATCH: {
        B2bOrder.Status.REFUNDED,
    },
    B2bOrder.Status.CANCELLED: set(),
    B2bOrder.Status.REFUNDED: set(),
}


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
    from .recovery import touch_b2c_cart

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
        from .cart_sync import sync_user_cart
        from .models import CartEvent

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
    from .cart_sync import sync_user_cart
    from .models import CartEvent

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
    from .recovery import touch_b2b_draft

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


@transaction.atomic
def submit_b2c_order(*, user, payload: dict, awaiting_payment: bool = False) -> B2cOrder:
    """
    Server-authoritative B2C checkout with strict PriceLock, RateSnapshot, and Variant Stock consistency.

    awaiting_payment=True (iyzico CF): creates ODEME_BEKLIYOR order, reserves stock, clears cart,
    but defers WorkOrders + order.created webhook until payment SUCCESS.
    """
    payment_method = payload["paymentMethod"]
    if not awaiting_payment and payment_method in ("CREDIT_CARD", "INSTALLMENT"):
        raise DomainError(
            "Kredi kartı ödemeleri iyzico Checkout Form üzerinden başlatılmalıdır.",
            code="USE_IYZICO_CHECKOUT",
            status_code=400,
        )
    if awaiting_payment and payment_method not in ("CREDIT_CARD", "INSTALLMENT", "BANK_TRANSFER"):
        raise DomainError(
            "Bekleyen ödeme başlatma CREDIT_CARD / INSTALLMENT / BANK_TRANSFER için geçerlidir.",
            code="INVALID_PAYMENT_METHOD",
            status_code=400,
        )
    # Direct BANK_TRANSFER checkout (without awaiting flag) must still wait for OPS dekont onayı.
    if not awaiting_payment and payment_method == "BANK_TRANSFER":
        awaiting_payment = True

    # of=("self",): Postgres forbids FOR UPDATE on nullable OUTER JOIN sides from select_related.
    cart_items = list(
        B2cCartItem.objects.select_for_update(of=("self",))
        .select_related("variant", "rate_snapshot", "price_quote", "bundle", "bundle__stone_product")
        .filter(user=user)
    )
    if not cart_items:
        raise DomainError("Sipariş oluşturmak için sepette en az bir ürün bulunmalıdır.", code="EMPTY_CART", status_code=400)

    now = timezone.now()
    # DYO soft-locks must still be active for stone lines
    from .dyo import extend_bundle_lock, release_expired_stone_locks
    from .models import CustomBundle, StoneSoftLock

    release_expired_stone_locks()
    dyo_bundle_ids = {item.bundle_id for item in cart_items if item.bundle_id}
    for bundle_id in dyo_bundle_ids:
        bundle = CustomBundle.objects.filter(id=bundle_id, user=user).first()
        if bundle is None:
            continue
        if bundle.status == CustomBundle.Status.EXPIRED or (
            bundle.expires_at and bundle.expires_at <= now
        ):
            raise DomainError(
                "DYO taş rezervasyonunun süresi doldu. Lütfen montür + taşı yeniden seçin.",
                code="DYO_LOCK_EXPIRED",
                status_code=409,
            )
        extend_bundle_lock(bundle=bundle)

    lock = (
        PriceLock.objects.select_for_update(of=("self",))
        .select_related("rate_snapshot")
        .filter(user=user, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if lock is None or lock.expires_at <= now:
        if lock is not None:
            lock.is_active = False
            lock.save(update_fields=["is_active", "updated_at"])
        raise DomainError(
            "Fiyat kilidinizin süresi doldu. Sipariş oluşturmadan önce sepet fiyatlarını güncel kurla yenileyin.",
            code="PRICE_LOCK_EXPIRED",
            status_code=409,
        )

    snap = lock.rate_snapshot
    for item in cart_items:
        if item.rate_snapshot_id != snap.id or item.snapshot_code != snap.snapshot_code:
            raise DomainError(
                "Sepetteki ürünlerin kur snapshot'ı aktif fiyat kilidiyle eşleşmiyor. Lütfen sepet fiyatlarını yenileyin.",
                code="CART_SNAPSHOT_MISMATCH",
                status_code=409,
            )
        if item.price_quote_id is not None:
            if (
                item.price_quote.rate_snapshot_id != snap.id
                or _q2(item.unit_final_price_try) != _q2(item.price_quote.final_price_try)
                or _q2(item.unit_list_price_try) != _q2(item.price_quote.list_price_try)
            ):
                raise DomainError(
                    "Sepet satır fiyatı bağlı fiyat teklifiyle tutarsız. Lütfen sepet fiyatlarını yenileyin.",
                    code="CART_QUOTE_MISMATCH",
                    status_code=409,
                )

    from apps.customers.services import get_or_update_customer_for_user

    customer = get_or_update_customer_for_user(
        user=user,
        full_name=payload["customerName"],
        phone=payload["customerPhone"],
        email=payload["customerEmail"],
        identity_or_tax_no=payload.get("identityNumber", ""),
        city=payload["shippingCity"],
        address=payload["shippingAddress"],
        segment=Customer.Segment.B2C,
    )

    subtotal_list = _q2(sum((item.unit_list_price_try * item.qty for item in cart_items), Decimal("0.00")))
    subtotal_final = _q2(sum((item.unit_final_price_try * item.qty for item in cart_items), Decimal("0.00")))
    campaign_discount = _q2(max(Decimal("0.00"), subtotal_list - subtotal_final))

    social_discount = Decimal("0.00")
    if payload.get("campaignCode") or payload.get("utmCampaign") or payload.get("affiliateCode"):
        from apps.social_commerce.services import resolve_social_checkout_discount

        social_disc = resolve_social_checkout_discount(
            subtotal_final_try=subtotal_final,
            campaign_code=str(payload.get("campaignCode") or payload.get("utmCampaign") or ""),
            affiliate_code=str(payload.get("affiliateCode") or ""),
            audience="B2C",
            now=now,
        )
        social_discount = _q2(social_disc["discountTry"])
        campaign_discount = _q2(campaign_discount + social_discount)

    discounted_subtotal = _q2(max(Decimal("0.00"), subtotal_final - social_discount))
    transfer_discount = (
        _q2(discounted_subtotal * BANK_TRANSFER_DISCOUNT_RATE) if payment_method == "BANK_TRANSFER" else Decimal("0.00")
    )
    insured_shipping = Decimal("0.00")
    grand_total = _q2(max(Decimal("0.00"), discounted_subtotal - transfer_discount + insured_shipping))
    vat_included = _q2(grand_total - (grand_total / VAT_DIVISOR))

    order_no = f"TG-B2C-{now.year}-{uuid.uuid4().hex[:6].upper()}"
    has_made_to_order = _b2c_order_needs_workshop(cart_items)

    ship_name = payload["customerName"].strip()
    ship_phone = payload["customerPhone"].strip()
    ship_email = payload["customerEmail"].strip()
    ship_city = payload["shippingCity"].strip()
    ship_address = payload["shippingAddress"].strip()
    identity = payload.get("identityNumber", "").strip()
    bill_name = (payload.get("billingName") or ship_name).strip()
    bill_city = (payload.get("billingCity") or ship_city).strip()
    bill_address = (payload.get("billingAddress") or ship_address).strip()
    bill_tax = (payload.get("billingIdentityOrTaxNo") or identity).strip()

    if awaiting_payment:
        initial_status = B2cOrder.Status.PENDING_PAYMENT
    else:
        initial_status = B2cOrder.Status.WORKSHOP if has_made_to_order else B2cOrder.Status.CONFIRMED

    order = B2cOrder.objects.create(
        order_no=order_no,
        customer=customer,
        created_by=user,
        rate_snapshot=snap,
        price_lock=lock,
        gold_rate_try_per_gram=snap.live_has_gold_try_sell,
        payment_method=payment_method,
        accepted_custom_policy=bool(payload.get("acceptedCustomPolicy", True)),
        shipping_full_name=ship_name,
        shipping_phone=ship_phone,
        shipping_email=ship_email,
        shipping_city=ship_city,
        shipping_address=ship_address,
        billing_full_name=bill_name,
        billing_identity_or_tax_no=bill_tax,
        billing_city=bill_city,
        billing_address=bill_address,
        subtotal_list_try=subtotal_list,
        campaign_discount_try=campaign_discount,
        transfer_discount_try=transfer_discount,
        insured_shipping_try=insured_shipping,
        vat_included_try=vat_included,
        grand_total_try=grand_total,
        status=initial_status,
    )

    for idx, item in enumerate(cart_items, start=1):
        resolved_variant = item.variant
        if resolved_variant is not None:
            reserve_variant_stock(variant=resolved_variant, qty=item.qty, reference_no=order_no, actor=user)
        else:
            mv = reserve_product_stock(parent_sku=item.parent_sku, qty=item.qty, reference_no=order_no, actor=user)
            if mv is not None and mv.variant is not None:
                resolved_variant = mv.variant

        B2cOrderItem.objects.create(
            order=order,
            variant=resolved_variant,
            bundle=item.bundle,
            bundle_role=item.bundle_role,
            sku=item.sku,
            parent_sku=item.parent_sku,
            title=item.title,
            category=item.category,
            metal_color=item.metal_color,
            purity_code=item.purity_code,
            size=item.size,
            size_unit_label=item.size_unit_label,
            qty=item.qty,
            engraving_text=item.engraving_text,
            gift_wrap=item.gift_wrap,
            gift_note=item.gift_note,
            certificate_label=item.certificate_label,
            stock_status=item.stock_status,
            lead_time_text=item.lead_time_text,
            gross_weight_gram=item.gross_weight_gram,
            unit_list_price_try=item.unit_list_price_try,
            unit_final_price_try=item.unit_final_price_try,
            rate_snapshot=snap,
            price_quote=item.price_quote,
            snapshot_code=snap.snapshot_code,
        )
        if not awaiting_payment and (
            item.stock_status == "Siparişe Özel" or item.engraving_text.strip()
        ):
            WorkOrder.objects.create(
                work_order_no=f"WO-{order_no}-{idx}",
                source_order_no=order_no,
                sku=item.sku,
                size=item.size,
                quantity=item.qty,
                engraving_or_stamp_note=item.engraving_text,
            )

    lock.is_active = False
    lock.save(update_fields=["is_active", "updated_at"])
    if dyo_bundle_ids:
        StoneSoftLock.objects.filter(
            bundle_id__in=dyo_bundle_ids, status=StoneSoftLock.Status.ACTIVE
        ).update(status=StoneSoftLock.Status.CONSUMED)
        CustomBundle.objects.filter(id__in=dyo_bundle_ids).update(
            status=CustomBundle.Status.CHECKED_OUT
        )
    B2cCartItem.objects.filter(user=user).delete()
    from .cart_sync import mark_cart_converted
    from .models import CartRecoverySession
    from .recovery import suppress_b2c_cart

    mark_cart_converted(user=user, order=order)
    suppress_b2c_cart(user=user, reason=CartRecoverySession.SuppressReason.CHECKOUT)

    if bool(payload.get("acceptedCustomPolicy", True)):
        from apps.contracts.services import record_order_acceptances

        record_order_acceptances(
            customer=customer,
            order=order,
            source="CHECKOUT",
            evidence={
                "acceptedCustomPolicy": True,
                "locale": payload.get("locale") or "tr-TR",
            },
            actor=user,
        )

    consents = payload.get("consents")
    if isinstance(consents, list):
        from apps.consent.models import ConsentChannel, ConsentSource, ConsentStatus
        from apps.consent.services import append_consent

        for raw in consents:
            if not isinstance(raw, dict):
                continue
            purpose = str(raw.get("purpose") or "").upper()
            channel = str(raw.get("channel") or ConsentChannel.EMAIL).upper()
            status = str(raw.get("status") or ConsentStatus.GRANTED).upper()
            if not purpose:
                continue
            append_consent(
                customer=customer,
                purpose=purpose,
                channel=channel,
                status=status,
                source=ConsentSource.CHECKOUT,
                document_version=str(raw.get("documentVersion") or ""),
                document_hash=str(raw.get("documentHash") or ""),
                actor=user,
            )

    record_audit(
        action="B2C_ORDER_PENDING_PAYMENT" if awaiting_payment else "B2C_ORDER_CREATED",
        entity_type="B2cOrder",
        entity_id=order_no,
        actor=user,
        metadata={
            "grand_total_try": str(order.grand_total_try),
            "snapshot": snap.snapshot_code,
            "price_lock_id": str(lock.id),
            "dyo_bundles": [str(x) for x in dyo_bundle_ids],
            "awaiting_payment": awaiting_payment,
            "customer_id": str(customer.id),
        },
    )
    if not awaiting_payment:
        _schedule_b2c_order_created_webhook(order)
        _record_social_commerce_order_hooks(order=order, payload=payload)
    return order


def _record_social_commerce_order_hooks(*, order: B2cOrder, payload: dict) -> None:
    """Non-blocking social attribution & affiliate conversion recording for confirmed B2C orders."""
    try:
        from apps.social_commerce.services import (
            record_affiliate_conversion,
            record_verified_order_attribution,
        )

        record_verified_order_attribution(
            order_no=order.order_no,
            revenue_try=order.grand_total_try,
            customer=order.customer,
            session_key=str(payload.get("sessionKey") or ""),
            platform=str(payload.get("utmPlatform") or payload.get("utmSource") or ""),
            utm_source=str(payload.get("utmSource") or ""),
            utm_medium=str(payload.get("utmMedium") or ""),
            utm_campaign=str(payload.get("utmCampaign") or ""),
            audience="B2C",
        )
        aff_code = str(payload.get("affiliateCode") or "").strip()
        if aff_code:
            record_affiliate_conversion(
                code_str=aff_code,
                order_no=order.order_no,
                gross_amount_try=order.subtotal_list_try,
                net_amount_try=order.grand_total_try,
                audience="B2C",
            )
    except Exception:
        logger.exception("social_commerce order hook failed order=%s", order.order_no)


@transaction.atomic
def finalize_b2c_order_after_payment(*, order: B2cOrder, actor=None) -> B2cOrder:
    """Promote ODEME_BEKLIYOR → CONFIRMED/WORKSHOP after iyzico SUCCESS; create deferred WorkOrders."""
    order = B2cOrder.objects.select_for_update().prefetch_related("items").get(pk=order.pk)
    if order.status != B2cOrder.Status.PENDING_PAYMENT:
        return order

    next_status = (
        B2cOrder.Status.WORKSHOP
        if _b2c_order_needs_workshop(order.items.all())
        else B2cOrder.Status.CONFIRMED
    )
    order.status = next_status
    order.save(update_fields=["status", "updated_at"])
    _create_work_orders_for_b2c_order(order)
    record_audit(
        action="B2C_ORDER_PAYMENT_CONFIRMED",
        entity_type="B2cOrder",
        entity_id=order.order_no,
        actor=actor,
        metadata={"status": next_status},
    )
    _schedule_b2c_order_created_webhook(order)
    _emit_b2c_payment_success_mail(order)
    _record_social_commerce_order_hooks(order=order, payload={})
    return order


@transaction.atomic
def fail_b2c_pending_payment_order(*, order: B2cOrder, actor=None) -> B2cOrder:
    """Cancel ODEME_BEKLIYOR and release reserved stock after iyzico FAILURE / abandon."""
    if order.status != B2cOrder.Status.PENDING_PAYMENT:
        return order
    return transition_b2c_order_status(
        order_no=order.order_no,
        next_status=B2cOrder.Status.CANCELLED,
        actor=actor,
    )


def _pick_org_address(organization: Organization, *, address_id=None, address_type: str | None = None):
    from apps.organizations.models import OrganizationAddress

    qs = OrganizationAddress.objects.filter(organization=organization, is_active=True)
    if address_id:
        return qs.filter(id=address_id).first()
    if address_type:
        preferred = qs.filter(address_type=address_type, is_default=True).first()
        if preferred:
            return preferred
        return qs.filter(address_type=address_type).first()
    return qs.filter(is_default=True).first() or qs.first()


def _resolve_b2b_address_snapshots(
    *,
    organization: Organization,
    branch: Branch | None,
    payload: dict,
    contact_person: str,
) -> tuple[dict, dict]:
    """Build immutable shipping/billing snapshots for a B2B order."""
    ship_addr = _pick_org_address(
        organization,
        address_id=payload.get("shippingAddressId"),
        address_type="SHIPPING",
    )
    bill_addr = _pick_org_address(
        organization,
        address_id=payload.get("billingAddressId"),
        address_type="BILLING",
    )
    if bill_addr is None:
        bill_addr = ship_addr

    branch_city = branch.city if branch else organization.city
    branch_line = (branch.address if branch and branch.address else "") or organization.city

    def pack(addr, *, title_key: str, city_key: str, line_key: str, fallback_title: str) -> dict:
        if addr is not None:
            return {
                "title": addr.title,
                "city": addr.city or branch_city or "",
                "line": addr.line,
                "contact": addr.contact_name or contact_person,
                "phone": addr.phone or organization.phone or "",
                "tax": organization.tax_office_and_no or "",
            }
        return {
            "title": (payload.get(title_key) or fallback_title).strip(),
            "city": payload.get(city_key) or branch_city or "",
            "line": payload.get(line_key) or branch_line or "",
            "contact": contact_person,
            "phone": organization.phone or "",
            "tax": organization.tax_office_and_no or "",
        }

    return (
        pack(
            ship_addr,
            title_key="shippingTitle",
            city_key="shippingCity",
            line_key="shippingAddress",
            fallback_title="Teslimat",
        ),
        pack(
            bill_addr,
            title_key="billingTitle",
            city_key="billingCity",
            line_key="billingAddress",
            fallback_title="Fatura",
        ),
    )


@transaction.atomic
def submit_b2b_order(
    *,
    user,
    organization: Organization,
    branch: Branch | None,
    payload: dict,
) -> B2bOrder:
    if branch is not None:
        if branch.organization_id != organization.id:
            raise DomainError(
                "Sipariş şubesi aktif firma kapsamında değil.",
                code="BRANCH_ORG_MISMATCH",
                status_code=400,
            )
        if not branch.is_active:
            raise DomainError(
                "Pasif şube ile sipariş oluşturulamaz.",
                code="BRANCH_INACTIVE",
                status_code=400,
            )

    draft_lines = list(
        B2bDraftLine.objects.select_for_update()
        .select_related("variant", "rate_snapshot", "price_quote")
        .filter(organization=organization)
    )
    if not draft_lines:
        raise DomainError("Sipariş fişi onaylamak için en az bir kalem eklemelisiniz.", code="EMPTY_B2B_ORDER", status_code=400)

    snap = get_current_rate_snapshot()
    usd_try = snap.live_usd_sell
    if usd_try <= 0:
        raise DomainError("Geçerli USD/TRY satış kuru bulunamadı.", code="INVALID_RATE", status_code=500)

    for line in draft_lines:
        if line.rate_snapshot_id != snap.id or line.price_quote_id is None:
            product = ProductModel.objects.filter(parent_sku=line.parent_sku).prefetch_related("stone_lines").first()
            if product is None:
                raise DomainError(f"Ürün bulunamadı: {line.parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
            variant = line.variant or resolve_product_variant(
                product,
                purity_code=line.purity_code,
                metal_color=line.metal_color,
                size=line.size,
            )
            quote, output = create_live_quote(
                product=product,
                channel="B2B",
                variant=variant,
                organization=organization,
                snapshot=snap,
                size=line.size,
            )
            resolved_variant = quote.variant
            gross_gram = compute_size_adjusted_gross_weight(product, line.size, variant=resolved_variant)
            wholesale_try = _q2(quote.final_price_try)
            wholesale_usd = _q2(wholesale_try / usd_try)
            fire_included_fine = _q4(output.fire_included_fine_metal_gram)
            metal_value_try = fire_included_fine * snap.live_has_gold_try_sell
            labor_and_stone_usd = _q2(max(Decimal("0.00"), (wholesale_try - metal_value_try) / usd_try))

            line.variant = resolved_variant
            line.unit_gross_gram = gross_gram
            line.unit_net_metal_gram = _q4(output.net_metal_gram)
            line.unit_fire_included_fine_gram = fire_included_fine
            line.unit_labor_and_stone_usd = labor_and_stone_usd
            line.unit_wholesale_usd = wholesale_usd
            line.unit_wholesale_try = wholesale_try
            line.pricing_currency = output.lc_currency
            line.rate_snapshot = snap
            line.price_quote = quote
            line.snapshot_code = snap.snapshot_code

    order_no = f"TG-B2B-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"

    total_pieces = sum(l.qty for l in draft_lines)
    total_gross = _q4(sum((l.unit_gross_gram * l.qty for l in draft_lines), Decimal("0")))
    total_has = _q4(sum((l.unit_fire_included_fine_gram * l.qty for l in draft_lines), Decimal("0")))
    total_labor_usd = _q2(sum((l.unit_labor_and_stone_usd * l.qty for l in draft_lines), Decimal("0")))
    total_wholesale_usd = _q2(sum((l.unit_wholesale_usd * l.qty for l in draft_lines), Decimal("0")))
    total_wholesale_try = _q2(sum((l.unit_wholesale_try * l.qty for l in draft_lines), Decimal("0")))

    # Concurrency-safe & idempotent credit & has-gold limit validation + reservation
    reserve_organization_limits(
        organization_id=organization.id,
        settlement_method=payload["settlementMethod"],
        total_has_gold_gram=total_has,
        total_labor_and_stone_usd=total_labor_usd,
        total_wholesale_usd=total_wholesale_usd,
        reference_no=order_no,
        actor=user,
    )

    has_production = any(l.supply_type == "PRODUCTION" for l in draft_lines)
    ship_snap, bill_snap = _resolve_b2b_address_snapshots(
        organization=organization,
        branch=branch,
        payload=payload,
        contact_person=payload["contactPerson"],
    )
    order = B2bOrder.objects.create(
        order_no=order_no,
        organization=organization,
        branch=branch,
        created_by=user,
        rate_snapshot=snap,
        usd_try_rate=snap.live_usd_sell,
        gold_rate_try_per_gram=snap.live_has_gold_try_sell,
        contact_person=payload["contactPerson"],
        settlement_method=payload["settlementMethod"],
        rate_lock_mode=payload["rateLockMode"],
        consignment_days=payload.get("consignmentDays"),
        delivery_method=payload["deliveryMethod"],
        order_note=payload.get("orderNote", ""),
        accepted_weight_tolerance=bool(payload.get("acceptedWeightTolerance", True)),
        shipping_title=ship_snap["title"],
        shipping_city=ship_snap["city"],
        shipping_address=ship_snap["line"],
        shipping_contact_name=ship_snap["contact"],
        shipping_phone=ship_snap["phone"],
        billing_title=bill_snap["title"],
        billing_city=bill_snap["city"],
        billing_address=bill_snap["line"],
        billing_contact_name=bill_snap["contact"],
        billing_phone=bill_snap["phone"],
        billing_tax_office_and_no=bill_snap["tax"],
        total_pieces=total_pieces,
        total_gross_gram=total_gross,
        total_has_gold_gram=total_has,
        total_labor_and_stone_usd=total_labor_usd,
        total_wholesale_usd=total_wholesale_usd,
        total_wholesale_try=total_wholesale_try,
        status=B2bOrder.Status.WORKSHOP_PLANNED if has_production else B2bOrder.Status.PROFORMA_CONFIRMED,
    )

    for idx, line in enumerate(draft_lines, start=1):
        resolved_variant = line.variant
        if line.supply_type == "STOCK":
            if resolved_variant is not None:
                reserve_variant_stock(variant=resolved_variant, qty=line.qty, reference_no=order_no, actor=user)
            else:
                mv = reserve_product_stock(parent_sku=line.parent_sku, qty=line.qty, reference_no=order_no, actor=user)
                if mv is not None and mv.variant is not None:
                    resolved_variant = mv.variant
        else:
            WorkOrder.objects.create(
                work_order_no=f"WO-{order_no}-{idx}",
                source_order_no=order_no,
                organization=organization,
                sku=line.sku,
                size=line.size,
                quantity=line.qty,
                engraving_or_stamp_note=line.dealer_stamp_note,
            )

        B2bOrderLine.objects.create(
            order=order,
            variant=resolved_variant,
            sku=line.sku,
            parent_sku=line.parent_sku,
            title=line.title,
            category=line.category,
            metal_color=line.metal_color,
            purity_code=line.purity_code,
            size=line.size,
            size_unit_label=line.size_unit_label,
            qty=line.qty,
            supply_type=line.supply_type,
            dealer_stamp_note=line.dealer_stamp_note,
            unit_gross_gram=line.unit_gross_gram,
            unit_net_metal_gram=line.unit_net_metal_gram,
            unit_fire_included_fine_gram=line.unit_fire_included_fine_gram,
            unit_labor_and_stone_usd=line.unit_labor_and_stone_usd,
            unit_wholesale_usd=line.unit_wholesale_usd,
            unit_wholesale_try=line.unit_wholesale_try,
            pricing_currency=line.pricing_currency,
            rate_snapshot=snap,
            price_quote=line.price_quote,
            snapshot_code=snap.snapshot_code,
        )

    B2bDraftLine.objects.filter(organization=organization).delete()
    from .models import CartRecoverySession
    from .recovery import suppress_b2b_draft

    suppress_b2b_draft(
        organization=organization, reason=CartRecoverySession.SuppressReason.CHECKOUT
    )
    record_audit(
        action="B2B_ORDER_CREATED",
        entity_type="B2bOrder",
        entity_id=order_no,
        actor=user,
        organization=organization,
        metadata={
            "total_wholesale_usd": str(order.total_wholesale_usd),
            "total_has_gram": str(order.total_has_gold_gram),
            "snapshot": snap.snapshot_code,
        },
    )
    _schedule_b2b_order_created_webhook(order)
    return order


@transaction.atomic
def transition_b2c_order_status(*, order_no: str, next_status: str, actor=None) -> B2cOrder:
    """
    Centralized B2C order status state machine.
    - Rejects invalid transitions with 409 INVALID_STATUS_TRANSITION.
    - Releases variant warehouse stock automatically on CANCELLED / REFUNDED.
    """
    if next_status not in B2cOrder.Status.values:
        raise DomainError("Geçersiz B2C sipariş durumu.", code="INVALID_STATUS", status_code=400)

    order = (
        B2cOrder.objects.select_for_update()
        .prefetch_related("items__variant")
        .filter(order_no=order_no)
        .first()
    )
    if order is None:
        raise DomainError("B2C sipariş bulunamadı.", code="ORDER_NOT_FOUND", status_code=404)

    if order.status == next_status:
        return order

    allowed = B2C_ALLOWED_TRANSITIONS.get(order.status, set())
    if next_status not in allowed:
        raise DomainError(
            f"B2C sipariş '{order.status}' durumundan '{next_status}' durumuna geçirilemez.",
            code="INVALID_STATUS_TRANSITION",
            status_code=409,
        )

    prev_status = order.status
    order.status = next_status
    order.save(update_fields=["status", "updated_at"])

    if next_status in (B2cOrder.Status.CANCELLED, B2cOrder.Status.REFUNDED):
        try:
            from apps.social_commerce.services import mark_affiliate_conversion_refunded

            mark_affiliate_conversion_refunded(order.order_no)
        except Exception:
            logger.exception("social_commerce refund hook failed order=%s", order.order_no)
        released_variant_ids: set = set()
        for item in order.items.all():
            if item.variant is not None:
                release_variant_stock(
                    variant=item.variant,
                    qty=item.qty,
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(item.variant_id)
        # Fallback for legacy items whose variant FK was null when reserved via parent_sku
        from apps.inventory.models import StockMovement

        for mv in StockMovement.objects.select_related("variant").filter(
            reference_no=order.order_no,
            movement_type=StockMovement.MovementType.RESERVE,
            variant__isnull=False,
        ):
            if mv.variant_id not in released_variant_ids:
                release_variant_stock(
                    variant=mv.variant,
                    qty=abs(mv.quantity_delta),
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(mv.variant_id)

    record_audit(
        action="B2C_ORDER_STATUS_UPDATED",
        entity_type="B2cOrder",
        entity_id=order.order_no,
        actor=actor,
        metadata={"from": prev_status, "to": next_status},
    )
    return order


@transaction.atomic
def transition_b2b_order_status(*, order_no: str, next_status: str, actor=None) -> B2bOrder:
    """
    Centralized B2B order status state machine.
    - Rejects invalid transitions with 409 INVALID_STATUS_TRANSITION.
    - On CANCELLED / REFUNDED: idempotently releases reserved variant stock AND reverses dealer finance ledger limits.
    """
    if next_status not in B2bOrder.Status.values:
        raise DomainError("Geçersiz B2B sipariş durumu.", code="INVALID_STATUS", status_code=400)

    order = (
        B2bOrder.objects.select_for_update()
        .select_related("organization")
        .prefetch_related("lines__variant")
        .filter(order_no=order_no)
        .first()
    )
    if order is None:
        raise DomainError("B2B sipariş bulunamadı.", code="ORDER_NOT_FOUND", status_code=404)

    if order.status == next_status:
        return order

    allowed = B2B_ALLOWED_TRANSITIONS.get(order.status, set())
    if next_status not in allowed:
        raise DomainError(
            f"B2B sipariş '{order.status}' durumundan '{next_status}' durumuna geçirilemez.",
            code="INVALID_STATUS_TRANSITION",
            status_code=409,
        )

    prev_status = order.status
    order.status = next_status
    order.save(update_fields=["status", "updated_at"])

    if next_status in (B2bOrder.Status.CANCELLED, B2bOrder.Status.REFUNDED):
        released_variant_ids: set = set()
        for line in order.lines.all():
            if line.supply_type == "STOCK" and line.variant is not None:
                release_variant_stock(
                    variant=line.variant,
                    qty=line.qty,
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(line.variant_id)
        from apps.inventory.models import StockMovement

        for mv in StockMovement.objects.select_related("variant").filter(
            reference_no=order.order_no,
            movement_type=StockMovement.MovementType.RESERVE,
            variant__isnull=False,
        ):
            if mv.variant_id not in released_variant_ids:
                release_variant_stock(
                    variant=mv.variant,
                    qty=abs(mv.quantity_delta),
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(mv.variant_id)
        reversal_type = (
            DealerLedgerEntry.EntryType.ORDER_REVERSAL
            if next_status == B2bOrder.Status.CANCELLED
            else DealerLedgerEntry.EntryType.REFUND_CREDIT
        )
        reverse_organization_limits(
            organization_id=order.organization_id,
            reference_no=order.order_no,
            entry_type=reversal_type,
            note=f"B2B sipariş {next_status} ters kaydı",
            actor=actor,
        )

    record_audit(
        action="B2B_ORDER_STATUS_UPDATED",
        entity_type="B2bOrder",
        entity_id=order.order_no,
        actor=actor,
        organization=order.organization,
        metadata={"from": prev_status, "to": next_status},
    )
    _schedule_b2b_order_status_webhook(order=order, previous=prev_status, current=next_status)
    return order


@transaction.atomic
def reorder_b2b_order(*, order_no: str, organization: Organization, user, is_ops: bool = False) -> list[B2bDraftLine]:
    order = B2bOrder.objects.filter(order_no=order_no).prefetch_related("lines").first()
    if order is None:
        raise DomainError(f"Sipariş bulunamadı: {order_no}", code="ORDER_NOT_FOUND", status_code=404)
    if not is_ops and order.organization_id != organization.id:
        raise DomainError("Başka firmaya ait sipariş kaydına erişilemez.", code="TENANT_ISOLATION_VIOLATION", status_code=403)

    items_payload = [
        {
            "parentSku": line.parent_sku,
            "variantId": str(line.variant_id) if line.variant_id else None,
            "purityCode": line.purity_code,
            "metalColor": line.metal_color,
            "size": line.size,
            "qty": line.qty,
            "supplyType": line.supply_type,
            "dealerStampNote": line.dealer_stamp_note,
        }
        for line in order.lines.all()
    ]
    return add_b2b_draft_lines(user=user, organization=organization, items=items_payload, is_ops=is_ops)

"""B2C checkout and payment finalization services."""
import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit
from apps.catalog.models import ProductModel
from apps.customers.models import Customer
from apps.inventory.services import reserve_product_stock, reserve_variant_stock
from apps.pricing.models import PriceLock
from config.exceptions import DomainError

from ..models import B2cCartItem, B2cOrder, B2cOrderItem
from .helpers import (
    BANK_TRANSFER_DISCOUNT_RATE,
    VAT_DIVISOR,
    _b2c_order_needs_workshop,
    _create_work_orders_for_b2c_order,
    _q2,
    _q4,
)
from .transitions import transition_b2c_order_status
from .webhooks import (
    _emit_b2c_order_created_mail,
    _emit_b2c_payment_success_mail,
    _record_social_commerce_order_hooks,
    _schedule_b2c_order_created_webhook,
)

logger = logging.getLogger(__name__)


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
    from ..dyo import extend_bundle_lock, release_expired_stone_locks
    from ..models import CustomBundle, StoneSoftLock

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
    from ..cart_sync import mark_cart_converted
    from ..models import CartRecoverySession
    from ..recovery import suppress_b2c_cart

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
        _emit_b2c_order_created_mail(order)
        _record_social_commerce_order_hooks(order=order, payload=payload)
    return order


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

"""B2cCart header sync + CartEvent append helpers."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers.models import Customer
from apps.customers.services import get_or_update_customer_for_user

from .models import B2cCart, B2cCartItem, CartEvent


def _q2(value: Decimal | float | int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


@transaction.atomic
def get_or_create_active_cart(*, user=None, guest_email: str = "", external_id: str | None = None) -> B2cCart:
    now = timezone.now()
    cart = None
    if external_id:
        cart = B2cCart.objects.select_for_update().filter(external_id=external_id).first()
        if cart is not None:
            if cart.status != B2cCart.Status.ACTIVE and cart.status != B2cCart.Status.CONVERTED:
                cart.status = B2cCart.Status.ACTIVE
                cart.last_activity_at = now
                cart.save(update_fields=["status", "last_activity_at", "updated_at"])
            return cart
        return B2cCart.objects.create(
            external_id=external_id,
            user=user,
            guest_email=(guest_email or "").strip().lower(),
            status=B2cCart.Status.ACTIVE,
            last_activity_at=now,
        )

    if user is not None:
        cart = (
            B2cCart.objects.select_for_update()
            .filter(user=user, status=B2cCart.Status.ACTIVE)
            .first()
        )
        if cart is None:
            cart = B2cCart.objects.create(
                user=user,
                status=B2cCart.Status.ACTIVE,
                last_activity_at=now,
                external_id=f"user-{user.id}-{uuid.uuid4().hex[:8]}",
            )
            append_cart_event(
                cart=cart,
                event_type=CartEvent.EventType.CART_CREATED,
                payload={"userId": str(user.id)},
                source="STOREFRONT",
            )
        return cart

    email = (guest_email or "").strip().lower()
    if email:
        cart = (
            B2cCart.objects.select_for_update()
            .filter(guest_email__iexact=email, user__isnull=True, status=B2cCart.Status.ACTIVE)
            .first()
        )
        if cart is None:
            cart = B2cCart.objects.create(
                guest_email=email,
                status=B2cCart.Status.ACTIVE,
                last_activity_at=now,
                external_id=f"guest-{uuid.uuid4().hex[:12]}",
            )
            append_cart_event(
                cart=cart,
                event_type=CartEvent.EventType.CART_CREATED,
                payload={"guestEmail": email},
                source="STOREFRONT",
            )
        return cart

    raise ValueError("user, guest_email veya external_id gerekli")


@transaction.atomic
def sync_cart_totals(cart: B2cCart) -> B2cCart:
    items = B2cCartItem.objects.filter(cart=cart)
    if not items.exists() and cart.user_id:
        B2cCartItem.objects.filter(user_id=cart.user_id, cart__isnull=True).update(cart=cart)
        items = B2cCartItem.objects.filter(cart=cart)

    total = Decimal("0.00")
    list_total = Decimal("0.00")
    count = 0
    for item in items:
        total += item.unit_final_price_try * item.qty
        list_total += item.unit_list_price_try * item.qty
        count += 1
    cart.line_count = count
    cart.subtotal_try = _q2(list_total)
    cart.discount_try = _q2(max(Decimal("0.00"), list_total - total))
    cart.total_try = _q2(total)
    cart.last_activity_at = timezone.now()
    if cart.user_id and not cart.customer_id:
        try:
            cart.customer = get_or_update_customer_for_user(
                user=cart.user,
                full_name=getattr(cart.user, "full_name", "") or "",
                email=getattr(cart.user, "email", "") or "",
                segment=Customer.Segment.B2C,
            )
        except Exception:
            pass
    cart.save(
        update_fields=[
            "line_count",
            "subtotal_try",
            "discount_try",
            "total_try",
            "last_activity_at",
            "customer",
            "updated_at",
        ]
    )
    return cart


def append_cart_event(
    *,
    cart: B2cCart,
    event_type: str,
    payload: dict[str, Any] | None = None,
    source: str = "STOREFRONT",
    idempotency_key: str | None = None,
    occurred_at=None,
) -> CartEvent | None:
    key = (idempotency_key or "").strip() or None
    if key and CartEvent.objects.filter(idempotency_key=key).exists():
        return CartEvent.objects.filter(idempotency_key=key).first()
    return CartEvent.objects.create(
        cart=cart,
        event_type=event_type,
        payload=payload or {},
        occurred_at=occurred_at or timezone.now(),
        source=source,
        idempotency_key=key,
    )


@transaction.atomic
def sync_user_cart(*, user, event_type: str | None = None, payload: dict | None = None) -> B2cCart | None:
    """Ensure active cart header exists, attach orphan lines, refresh totals, optional event."""
    if not B2cCartItem.objects.filter(user=user).exists():
        active = B2cCart.objects.filter(user=user, status=B2cCart.Status.ACTIVE).first()
        if active:
            active.status = B2cCart.Status.EXPIRED
            active.last_activity_at = timezone.now()
            active.save(update_fields=["status", "last_activity_at", "updated_at"])
        return None

    cart = get_or_create_active_cart(user=user)
    B2cCartItem.objects.filter(user=user, cart__isnull=True).update(cart=cart)
    sync_cart_totals(cart)
    if event_type:
        append_cart_event(cart=cart, event_type=event_type, payload=payload or {})
    return cart


@transaction.atomic
def mark_cart_converted(*, user, order) -> B2cCart | None:
    cart = B2cCart.objects.select_for_update().filter(user=user, status=B2cCart.Status.ACTIVE).first()
    if cart is None:
        return None
    cart.status = B2cCart.Status.CONVERTED
    cart.checkout_state = B2cCart.CheckoutState.COMPLETED
    cart.converted_order = order
    cart.last_activity_at = timezone.now()
    cart.save(
        update_fields=[
            "status",
            "checkout_state",
            "converted_order",
            "last_activity_at",
            "updated_at",
        ]
    )
    append_cart_event(
        cart=cart,
        event_type=CartEvent.EventType.ORDER_CREATED,
        payload={"orderNo": order.order_no, "orderId": str(order.id)},
        source="CHECKOUT",
    )
    return cart


@transaction.atomic
def mark_cart_abandoned(cart: B2cCart) -> B2cCart:
    if cart.status != B2cCart.Status.ACTIVE:
        return cart
    cart.status = B2cCart.Status.ABANDONED
    cart.last_activity_at = timezone.now()
    cart.save(update_fields=["status", "last_activity_at", "updated_at"])
    append_cart_event(
        cart=cart,
        event_type=CartEvent.EventType.CART_ABANDONED,
        payload={},
        source="RECOVERY",
    )
    return cart


def serialize_b2c_cart(cart: B2cCart, *, detail: bool = False) -> dict:
    payload = {
        "id": str(cart.id),
        "externalId": cart.external_id,
        "userId": str(cart.user_id) if cart.user_id else None,
        "userEmail": cart.user.email if cart.user_id else None,
        "customerId": str(cart.customer_id) if cart.customer_id else None,
        "guestEmail": cart.guest_email or None,
        "status": cart.status,
        "checkoutState": cart.checkout_state,
        "currency": cart.currency,
        "subtotalTry": str(cart.subtotal_try),
        "discountTry": str(cart.discount_try),
        "taxTry": str(cart.tax_try),
        "totalTry": str(cart.total_try),
        "lineCount": cart.line_count,
        "lastActivityAt": cart.last_activity_at.isoformat() if cart.last_activity_at else None,
        "convertedOrderId": str(cart.converted_order_id) if cart.converted_order_id else None,
        "convertedOrderNo": (
            cart.converted_order.order_no if cart.converted_order_id else None
        ),
        "createdAt": cart.created_at.isoformat(),
        "updatedAt": cart.updated_at.isoformat(),
    }
    if detail:
        items = list(cart.items.all().order_by("-updated_at")[:100])
        payload["items"] = [
            {
                "id": str(i.id),
                "sku": i.sku,
                "title": i.title,
                "qty": i.qty,
                "unitFinalPriceTry": str(i.unit_final_price_try),
                "metalColor": i.metal_color,
                "size": i.size,
            }
            for i in items
        ]
        events = list(cart.events.order_by("-occurred_at")[:50])
        payload["events"] = [
            {
                "id": str(e.id),
                "eventType": e.event_type,
                "occurredAt": e.occurred_at.isoformat(),
                "source": e.source,
                "payload": e.payload,
            }
            for e in events
        ]
    return payload


@transaction.atomic
def upsert_cart_from_external(payload: dict[str, Any]) -> dict[str, Any]:
    """Integration processor: upsert cart header + optional lines snapshot."""
    from apps.customers.services import upsert_customer_from_external

    external_id = str(payload.get("externalId") or payload.get("externalCartId") or "").strip()
    if not external_id:
        raise ValueError("externalId zorunlu")

    customer = None
    ext_cust = payload.get("externalCustomerId") or payload.get("customerExternalId")
    if ext_cust or payload.get("email"):
        customer, _ = upsert_customer_from_external(
            external_id=str(ext_cust or f"cart-{external_id}"),
            full_name=str(payload.get("fullName") or payload.get("email") or "Misafir"),
            email=str(payload.get("email") or ""),
            phone=str(payload.get("phone") or ""),
            segment=str(payload.get("segment") or Customer.Segment.B2C),
        )

    status = str(payload.get("status") or B2cCart.Status.ACTIVE).upper()
    if status not in B2cCart.Status.values:
        status = B2cCart.Status.ACTIVE

    cart = B2cCart.objects.select_for_update().filter(external_id=external_id).first()
    now = timezone.now()
    created = False
    if cart is None:
        cart = B2cCart.objects.create(
            external_id=external_id,
            customer=customer,
            guest_email=str(payload.get("email") or "").strip().lower(),
            status=status,
            checkout_state=str(payload.get("checkoutState") or B2cCart.CheckoutState.NONE).upper(),
            currency=str(payload.get("currency") or "TRY"),
            subtotal_try=_q2(payload.get("subtotal") or payload.get("subtotalTry") or 0),
            discount_try=_q2(payload.get("discount") or payload.get("discountTry") or 0),
            tax_try=_q2(payload.get("tax") or payload.get("taxTry") or 0),
            total_try=_q2(payload.get("total") or payload.get("totalTry") or 0),
            line_count=int(payload.get("lineCount") or len(payload.get("items") or [])),
            last_activity_at=now,
        )
        created = True
        append_cart_event(
            cart=cart,
            event_type=CartEvent.EventType.CART_CREATED,
            payload={"externalId": external_id},
            source="INTEGRATION",
            idempotency_key=payload.get("idempotencyKey"),
        )
    else:
        cart.customer = customer or cart.customer
        if payload.get("email"):
            cart.guest_email = str(payload["email"]).strip().lower()
        cart.status = status
        if payload.get("checkoutState"):
            cart.checkout_state = str(payload["checkoutState"]).upper()
        if payload.get("currency"):
            cart.currency = str(payload["currency"])
        for api, field in (
            ("subtotal", "subtotal_try"),
            ("subtotalTry", "subtotal_try"),
            ("discount", "discount_try"),
            ("discountTry", "discount_try"),
            ("tax", "tax_try"),
            ("taxTry", "tax_try"),
            ("total", "total_try"),
            ("totalTry", "total_try"),
        ):
            if api in payload and payload[api] is not None:
                setattr(cart, field, _q2(payload[api]))
        cart.line_count = int(payload.get("lineCount") or cart.line_count)
        cart.last_activity_at = now
        cart.save()
        append_cart_event(
            cart=cart,
            event_type=CartEvent.EventType.CART_UPDATED,
            payload={"externalId": external_id},
            source="INTEGRATION",
            idempotency_key=payload.get("idempotencyKey"),
        )

    return {"cartId": str(cart.id), "externalId": cart.external_id, "created": created, "status": cart.status}


@transaction.atomic
def ingest_cart_event(payload: dict[str, Any]) -> dict[str, Any]:
    external_id = str(payload.get("externalCartId") or payload.get("externalId") or "").strip()
    cart_id = payload.get("cartId")
    cart = None
    if cart_id:
        cart = B2cCart.objects.filter(id=cart_id).first()
    if cart is None and external_id:
        cart = B2cCart.objects.filter(external_id=external_id).first()
    if cart is None:
        result = upsert_cart_from_external({**payload, "externalId": external_id or f"evt-{uuid.uuid4().hex[:10]}"})
        cart = B2cCart.objects.get(id=result["cartId"])

    event_type = str(payload.get("eventType") or payload.get("type") or CartEvent.EventType.CART_UPDATED)
    # Normalize short names
    aliases = {
        "created": CartEvent.EventType.CART_CREATED,
        "product_added": CartEvent.EventType.PRODUCT_ADDED,
        "product_removed": CartEvent.EventType.PRODUCT_REMOVED,
        "updated": CartEvent.EventType.CART_UPDATED,
        "checkout_started": CartEvent.EventType.CHECKOUT_STARTED,
        "abandoned": CartEvent.EventType.CART_ABANDONED,
        "recovered": CartEvent.EventType.CART_RECOVERED,
        "order_created": CartEvent.EventType.ORDER_CREATED,
    }
    event_type = aliases.get(event_type.lower().replace("-", "_"), event_type)

    if event_type == CartEvent.EventType.CART_ABANDONED:
        mark_cart_abandoned(cart)
    elif event_type == CartEvent.EventType.CHECKOUT_STARTED:
        cart.checkout_state = B2cCart.CheckoutState.STARTED
        cart.save(update_fields=["checkout_state", "updated_at"])

    evt = append_cart_event(
        cart=cart,
        event_type=event_type if event_type in CartEvent.EventType.values else CartEvent.EventType.CART_UPDATED,
        payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else payload,
        source=str(payload.get("source") or "INTEGRATION"),
        idempotency_key=payload.get("idempotencyKey") or payload.get("eventId"),
    )
    return {"cartId": str(cart.id), "eventId": str(evt.id) if evt else None, "eventType": event_type}

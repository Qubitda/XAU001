"""Build iyzico Checkout Form initialize payloads from a B2cOrder + request IP."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings

from apps.commerce.models import B2cOrder

MONEY_Q = Decimal("0.01")
SANDBOX_IDENTITY = "11111111111"


def _money(value: Decimal | str | float | int) -> str:
    return str(Decimal(value).quantize(MONEY_Q, rounding=ROUND_HALF_UP))


def _split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split()
    if not parts:
        return "Musteri", "TaraGold"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _normalize_gsm(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("90") and len(digits) >= 12:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 11:
        return f"+90{digits[1:]}"
    if len(digits) == 10:
        return f"+90{digits}"
    return "+905350000000"


def _is_sandbox() -> bool:
    base = (getattr(settings, "IYZICO_BASE_URL", "") or "").lower()
    return "sandbox" in base


def build_checkout_form_request(*, order: B2cOrder, buyer_ip: str) -> dict[str, Any]:
    name, surname = _split_name(order.shipping_full_name or order.customer.full_name)
    identity = (order.billing_identity_or_tax_no or order.customer.identity_or_tax_no or "").strip()
    if not identity or (len(identity) != 11 and _is_sandbox()):
        identity = SANDBOX_IDENTITY if _is_sandbox() else (identity or SANDBOX_IDENTITY)

    city = order.shipping_city or "Istanbul"
    address = order.shipping_address or "Adres belirtilmedi"
    email = order.shipping_email or order.customer.email
    phone = _normalize_gsm(order.shipping_phone or order.customer.phone)

    bill_name = order.billing_full_name or order.shipping_full_name or f"{name} {surname}"
    bill_city = order.billing_city or city
    bill_address = order.billing_address or address

    items = list(order.items.all())
    basket_items: list[dict[str, Any]] = []
    for item in items:
        line_price = (item.unit_final_price_try * item.qty).quantize(MONEY_Q, rounding=ROUND_HALF_UP)
        basket_items.append(
            {
                "id": item.sku[:64],
                "name": (item.title or item.sku)[:64],
                "category1": (item.category or "Jewelry")[:64],
                "itemType": "PHYSICAL",
                "price": _money(line_price),
            }
        )
    if not basket_items:
        basket_items.append(
            {
                "id": order.order_no,
                "name": "Siparis",
                "category1": "Jewelry",
                "itemType": "PHYSICAL",
                "price": _money(order.grand_total_try),
            }
        )

    # iyzico requires sum(basketItems.price) == price
    items_sum = sum((Decimal(b["price"]) for b in basket_items), Decimal("0.00"))
    paid = order.grand_total_try.quantize(MONEY_Q, rounding=ROUND_HALF_UP)
    if items_sum != paid and basket_items:
        diff = paid - items_sum
        last = Decimal(basket_items[-1]["price"]) + diff
        basket_items[-1]["price"] = _money(max(Decimal("0.01"), last))

    callback_base = getattr(settings, "IYZICO_CALLBACK_BASE_URL", "").rstrip("/")
    callback_url = f"{callback_base}/api/v1/payments/iyzico/callback"

    buyer = {
        "id": str(order.customer_id)[:32],
        "name": name[:64],
        "surname": surname[:64],
        "gsmNumber": phone,
        "email": email,
        "identityNumber": identity,
        "registrationAddress": address[:255],
        "ip": buyer_ip or "127.0.0.1",
        "city": city[:64],
        "country": "Turkey",
    }
    shipping = {
        "contactName": (order.shipping_full_name or f"{name} {surname}")[:128],
        "city": city[:64],
        "country": "Turkey",
        "address": address[:255],
    }
    billing = {
        "contactName": bill_name[:128],
        "city": bill_city[:64],
        "country": "Turkey",
        "address": bill_address[:255],
    }

    return {
        "locale": "tr",
        "conversationId": order.order_no,
        "price": _money(paid),
        "paidPrice": _money(paid),
        "currency": "TRY",
        "basketId": order.order_no,
        "paymentGroup": "PRODUCT",
        "callbackUrl": callback_url,
        "enabledInstallments": [1, 2, 3, 6, 9],
        "buyer": buyer,
        "shippingAddress": shipping,
        "billingAddress": billing,
        "basketItems": basket_items,
    }

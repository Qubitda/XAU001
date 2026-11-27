"""Thin wrapper around official iyzipay SDK (Checkout Form + Cancel/Refund)."""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any

import iyzipay
from django.conf import settings

from apps.payments.models import PaymentProviderSetting


class IyzicoNotConfigured(RuntimeError):
    pass


def _is_placeholder(value: str) -> bool:
    v = (value or "").strip().lower()
    return (not v) or v.startswith("replace_") or v in {"changeme", "xxx", "todo"}


def _decrypt_provider_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    from apps.mail.crypto import decrypt_secret

    return decrypt_secret(ciphertext)


def resolve_iyzico_credentials(
    *, organization_id: str | None = None
) -> tuple[str, str, str]:
    """
    Resolve api_key, secret_key, base_url.
    Priority: active org PaymentProviderSetting → platform setting → env.
    """
    qs = PaymentProviderSetting.objects.filter(provider="IYZICO", is_active=True)
    setting = None
    if organization_id:
        setting = qs.filter(organization_id=organization_id).order_by("-updated_at").first()
    if setting is None:
        setting = qs.filter(organization__isnull=True).order_by("-updated_at").first()

    if setting and setting.api_key_ciphertext and setting.secret_key_ciphertext:
        api_key = _decrypt_provider_secret(setting.api_key_ciphertext)
        secret_key = _decrypt_provider_secret(setting.secret_key_ciphertext)
        base_url = (setting.base_url or "").strip() or "sandbox-api.iyzipay.com"
        if not _is_placeholder(api_key) and not _is_placeholder(secret_key):
            return api_key, secret_key, base_url

    api_key = (getattr(settings, "IYZICO_API_KEY", "") or "").strip()
    secret_key = (getattr(settings, "IYZICO_SECRET_KEY", "") or "").strip()
    base_url = (getattr(settings, "IYZICO_BASE_URL", "") or "sandbox-api.iyzipay.com").strip()
    return api_key, secret_key, base_url


def get_iyzico_options(*, organization_id: str | None = None) -> dict[str, str]:
    api_key, secret_key, base_url = resolve_iyzico_credentials(organization_id=organization_id)
    if _is_placeholder(api_key) or _is_placeholder(secret_key):
        raise IyzicoNotConfigured(
            "iyzico API Key / Secret Key tanımlı değil. "
            "OPS → Ayarlar → Ödeme Ayarları veya .env IYZICO_* değerlerini girin."
        )
    return {
        "api_key": api_key,
        "secret_key": secret_key,
        "base_url": base_url,
    }


def _parse_response(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        return json.loads(raw)
    read = getattr(raw, "read", None)
    if callable(read):
        body = read()
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8")
        return json.loads(body)
    raise TypeError(f"Unexpected iyzico response type: {type(raw)!r}")


def initialize_checkout_form(request: dict[str, Any], *, organization_id: str | None = None) -> dict[str, Any]:
    options = get_iyzico_options(organization_id=organization_id)
    raw = iyzipay.CheckoutFormInitialize().create(request, options)
    return _parse_response(raw)


def retrieve_checkout_form(token: str, *, organization_id: str | None = None) -> dict[str, Any]:
    options = get_iyzico_options(organization_id=organization_id)
    raw = iyzipay.CheckoutForm().retrieve({"locale": "tr", "token": token}, options)
    return _parse_response(raw)


def cancel_payment(
    *,
    payment_id: str,
    ip: str = "127.0.0.1",
    conversation_id: str = "",
    organization_id: str | None = None,
) -> dict[str, Any]:
    options = get_iyzico_options(organization_id=organization_id)
    payload: dict[str, Any] = {
        "locale": "tr",
        "paymentId": str(payment_id),
        "ip": ip or "127.0.0.1",
    }
    if conversation_id:
        payload["conversationId"] = conversation_id
    raw = iyzipay.Cancel().create(payload, options)
    return _parse_response(raw)


def fetch_installment_info(
    *,
    bin_number: str,
    price: str | Decimal,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """iyzico InstallmentInfo — BIN (6–8 digit) → card family + installment options."""
    options = get_iyzico_options(organization_id=organization_id)
    bin_clean = "".join(ch for ch in str(bin_number) if ch.isdigit())[:8]
    if len(bin_clean) < 6:
        raise ValueError("BIN en az 6 hane olmalıdır.")
    payload = {
        "locale": "tr",
        "binNumber": bin_clean,
        "price": str(price),
    }
    raw = iyzipay.InstallmentInfo().retrieve(payload, options)
    return _parse_response(raw)


def refund_payment_item(
    *,
    payment_transaction_id: str,
    price: Decimal | str,
    ip: str = "127.0.0.1",
    conversation_id: str = "",
    currency: str = "TRY",
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Item-level refund (requires paymentTransactionId from basket items)."""
    options = get_iyzico_options(organization_id=organization_id)
    payload: dict[str, Any] = {
        "locale": "tr",
        "paymentTransactionId": str(payment_transaction_id),
        "price": str(price),
        "currency": currency,
        "ip": ip or "127.0.0.1",
    }
    if conversation_id:
        payload["conversationId"] = conversation_id
    raw = iyzipay.Refund().create(payload, options)
    return _parse_response(raw)


def test_iyzico_connection(*, organization_id: str | None = None) -> dict[str, Any]:
    """
    Verify stored/env iyzico credentials with a lightweight signed InstallmentInfo call.
    Returns structured status: {connected, status, baseUrl, latencyMs, errorCode, message}.
    """
    started = time.monotonic()
    try:
        options = get_iyzico_options(organization_id=organization_id)
    except IyzicoNotConfigured as exc:
        return {
            "connected": False,
            "status": "disconnected",
            "baseUrl": "",
            "latencyMs": 0,
            "errorCode": "NOT_CONFIGURED",
            "message": str(exc),
        }

    base_url = options["base_url"]
    try:
        resp = fetch_installment_info(
            bin_number="554960",
            price="100",
            organization_id=organization_id,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        if str(resp.get("status", "")).lower() == "success":
            return {
                "connected": True,
                "status": "connected",
                "baseUrl": base_url,
                "latencyMs": latency_ms,
                "errorCode": "",
                "message": f"iyzico API bağlantısı başarılı ({base_url}, {latency_ms} ms).",
            }
        return {
            "connected": False,
            "status": "disconnected",
            "baseUrl": base_url,
            "latencyMs": latency_ms,
            "errorCode": str(resp.get("errorCode") or "AUTH_FAILED"),
            "message": str(
                resp.get("errorMessage")
                or "iyzico kimlik doğrulaması başarısız. API Key / Secret Key / Ortam (Sandbox-Prod) uyumunu kontrol edin."
            ),
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "connected": False,
            "status": "disconnected",
            "baseUrl": base_url,
            "latencyMs": latency_ms,
            "errorCode": "CONNECTION_ERROR",
            "message": f"iyzico sunucusuna bağlanılamadı: {exc}",
        }

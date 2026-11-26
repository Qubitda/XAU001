"""SMS / WhatsApp providers — console stub + optional webhook."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def sms_enabled() -> bool:
    return bool(getattr(settings, "MESSAGING_SMS_ENABLED", False))


def whatsapp_enabled() -> bool:
    return bool(getattr(settings, "MESSAGING_WHATSAPP_ENABLED", False))


def _provider_mode(channel: str) -> str:
    if channel == "SMS":
        return (getattr(settings, "MESSAGING_SMS_PROVIDER", None) or "console").strip().lower()
    return (getattr(settings, "MESSAGING_WHATSAPP_PROVIDER", None) or "console").strip().lower()


def _webhook_url(channel: str) -> str:
    if channel == "SMS":
        return (getattr(settings, "MESSAGING_SMS_WEBHOOK_URL", None) or "").strip()
    return (getattr(settings, "MESSAGING_WHATSAPP_WEBHOOK_URL", None) or "").strip()


def send_channel_message(
    *,
    channel: str,
    recipient: str,
    body: str,
    template_key: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Dispatch to configured provider.
    Returns {ok, provider, provider_ref, error}.
    """
    mode = _provider_mode(channel)
    to = (recipient or "").strip()
    if not to:
        return {"ok": False, "provider": mode, "provider_ref": "", "error": "EMPTY_RECIPIENT"}

    if mode == "console":
        ref = f"console-{uuid.uuid4().hex[:12]}"
        logger.info(
            "messaging.console channel=%s to=%s template=%s body=%s",
            channel,
            to,
            template_key,
            body[:200],
        )
        return {"ok": True, "provider": "console", "provider_ref": ref, "error": ""}

    if mode == "webhook":
        url = _webhook_url(channel)
        if not url:
            return {
                "ok": False,
                "provider": "webhook",
                "provider_ref": "",
                "error": "WEBHOOK_URL_MISSING",
            }
        try:
            resp = requests.post(
                url,
                json={
                    "channel": channel,
                    "to": to,
                    "body": body,
                    "templateKey": template_key,
                    "context": context or {},
                },
                timeout=float(getattr(settings, "MESSAGING_WEBHOOK_TIMEOUT", 8)),
            )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "provider": "webhook",
                    "provider_ref": "",
                    "error": f"HTTP_{resp.status_code}",
                }
            ref = ""
            try:
                data = resp.json()
                ref = str(data.get("id") or data.get("messageId") or "")[:128]
            except Exception:
                ref = f"webhook-{uuid.uuid4().hex[:10]}"
            return {"ok": True, "provider": "webhook", "provider_ref": ref or f"wh-{resp.status_code}", "error": ""}
        except Exception as exc:
            logger.exception("messaging webhook failed channel=%s", channel)
            return {"ok": False, "provider": "webhook", "provider_ref": "", "error": str(exc)[:500]}

    return {"ok": False, "provider": mode, "provider_ref": "", "error": "UNKNOWN_PROVIDER"}

"""Single canonical WhatsApp Business Cloud API transport client."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

META_GRAPH_BASE = "https://graph.facebook.com/v21.0"


@dataclass
class WhatsAppSendResult:
    ok: bool
    status: str
    external_id: str = ""
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def send_whatsapp_cloud_payload(
    *,
    access_token: str,
    phone_number_id: str,
    payload: dict[str, Any],
    timeout: float = 10.0,
) -> WhatsAppSendResult:
    """Single HTTP transport for WhatsApp Cloud API text and template messages."""
    if not access_token or not phone_number_id:
        return WhatsAppSendResult(
            ok=False,
            status="NOT_CONFIGURED",
            error="WhatsApp Cloud API access token veya phone_number_id eksik.",
        )
    try:
        resp = requests.post(
            f"{META_GRAPH_BASE}/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
            timeout=timeout,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            return WhatsAppSendResult(
                ok=False,
                status="ERROR",
                error=str(data.get("error", {}).get("message") or f"HTTP_{resp.status_code}"),
                raw=data,
            )
        msg_id = ""
        msgs = data.get("messages")
        if isinstance(msgs, list) and msgs:
            msg_id = str(msgs[0].get("id", ""))
        return WhatsAppSendResult(ok=True, status="SENT", external_id=msg_id, raw=data)
    except Exception as exc:
        logger.exception("WhatsApp Cloud API request failed")
        return WhatsAppSendResult(ok=False, status="ERROR", error=str(exc)[:400])


def send_whatsapp_text(
    *,
    access_token: str,
    phone_number_id: str,
    recipient_id: str,
    body: str,
) -> WhatsAppSendResult:
    return send_whatsapp_cloud_payload(
        access_token=access_token,
        phone_number_id=phone_number_id,
        payload={
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "type": "text",
            "text": {"body": body},
        },
    )


def send_whatsapp_template(
    *,
    access_token: str,
    phone_number_id: str,
    recipient_id: str,
    template_name: str,
    language_code: str = "tr",
    components: list[dict[str, Any]] | None = None,
) -> WhatsAppSendResult:
    if not template_name:
        return WhatsAppSendResult(ok=False, status="ERROR", error="Onaylı template_name zorunludur.")
    tpl_payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code or "tr"},
        },
    }
    if components:
        tpl_payload["template"]["components"] = components
    return send_whatsapp_cloud_payload(
        access_token=access_token,
        phone_number_id=phone_number_id,
        payload=tpl_payload,
    )

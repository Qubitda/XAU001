from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record_audit
from apps.catalog.models import ProductModel
from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent
from apps.customers.models import Customer
from apps.integrations.models import IntegrationEvent
from apps.mail.crypto import decrypt_secret
from apps.messaging.services import channel_consent_ok

from ..adapters import get_adapter, verify_hmac_sha256
from ..models import (
    SocialChannel,
    SocialInboxConversation,
    SocialInboxMessage,
    SocialWhatsAppTemplate,
)
from .catalog_sync import build_social_b2c_product_dto
from .oauth import SocialCommerceError, decrypt_connection_token

WHATSAPP_OPT_OUT_KEYWORDS = frozenset({"stop", "iptal", "i̇ptal", "ret", "dur", "unsubscribe"})


def _extract_external_account_id(payload: dict[str, Any]) -> str:
    for key in ("externalAccountId", "accountId", "phoneNumberId", "recipientId"):
        val = str(payload.get(key) or "").strip()
        if val:
            return val
    entries = payload.get("entry")
    if isinstance(entries, list) and entries and isinstance(entries[0], dict):
        entry_id = str(entries[0].get("id") or "").strip()
        if entry_id:
            return entry_id
        changes = entries[0].get("changes")
        if isinstance(changes, list) and changes and isinstance(changes[0], dict):
            meta = changes[0].get("value", {}).get("metadata", {})
            if isinstance(meta, dict) and meta.get("phone_number_id"):
                return str(meta["phone_number_id"]).strip()
    return ""


def _resolve_webhook_channel(platform: str, payload: dict[str, Any]) -> SocialChannel:
    ext_acc = _extract_external_account_id(payload)
    qs = SocialChannel.objects.select_related("connection").filter(platform=platform, is_active=True)
    if ext_acc:
        ch = qs.filter(external_account_id=ext_acc).first()
        if ch is not None:
            return ch
        # Meta template status updates carry WABA ID in entry[0].id while channel may store phone_number_id
        if isinstance(payload.get("templateStatusUpdate"), dict):
            channels = list(qs[:2])
            if len(channels) == 1:
                return channels[0]
        raise SocialCommerceError(
            f"{platform} için eşleşen kanal bulunamadı (account={ext_acc}).",
            code="CHANNEL_NOT_FOUND",
            status_code=404,
        )
    # Only allow fallback when unambiguously 1 active channel exists for the platform
    channels = list(qs[:2])
    if len(channels) == 1:
        return channels[0]
    if len(channels) > 1:
        raise SocialCommerceError(
            f"{platform} için birden fazla aktif hesap var; webhook payload'ında hesap kimliği zorunludur.",
            code="AMBIGUOUS_CHANNEL",
            status_code=400,
        )
    raise SocialCommerceError(f"Aktif {platform} kanalı bulunamadı.", code="CHANNEL_NOT_FOUND", status_code=404)


def _resolve_webhook_secret(channel: SocialChannel) -> str:
    conn = getattr(channel, "connection", None)
    if conn is not None and conn.webhook_secret_encrypted:
        try:
            return decrypt_secret(conn.webhook_secret_encrypted)
        except Exception:
            return ""
    return (getattr(settings, "SOCIAL_WEBHOOK_SECRET", "") or "").strip()


def _extract_webhook_events(platform: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract ALL events from official Meta (Instagram/Facebook), WhatsApp Cloud API,
    and TikTok webhook payloads (iterating over every entry, change, messaging, and message)
    while preserving already-flat single-event payloads.
    """
    if not isinstance(payload, dict):
        return []
    plat = platform.upper()
    events: list[dict[str, Any]] = []

    entries = payload.get("entry")
    if isinstance(entries, list) and entries:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_id = str(entry.get("id") or "").strip()

            # Instagram / Meta Messenger format: entry.messaging[]
            messaging_list = entry.get("messaging")
            if isinstance(messaging_list, list):
                for m in messaging_list:
                    if not isinstance(m, dict):
                        continue
                    sender = m.get("sender") if isinstance(m.get("sender"), dict) else {}
                    recipient = m.get("recipient") if isinstance(m.get("recipient"), dict) else {}
                    msg = m.get("message") if isinstance(m.get("message"), dict) else {}
                    events.append(
                        {
                            "externalAccountId": str(recipient.get("id") or entry_id).strip(),
                            "from": str(sender.get("id") or "").strip(),
                            "threadId": str(sender.get("id") or "").strip(),
                            "messageId": str(msg.get("mid") or "").strip(),
                            "text": str(msg.get("text") or "").strip(),
                        }
                    )

            changes = entry.get("changes")
            if isinstance(changes, list):
                for ch in changes:
                    if not isinstance(ch, dict):
                        continue
                    field = str(ch.get("field") or "").strip()
                    val = ch.get("value") if isinstance(ch.get("value"), dict) else {}

                    if field == "message_template_status_update":
                        events.append(
                            {
                                "externalAccountId": entry_id,
                                "templateStatusUpdate": {
                                    "event": str(val.get("event") or "").upper(),
                                    "name": str(val.get("message_template_name") or "").strip(),
                                    "language": str(val.get("message_template_language") or "").strip(),
                                },
                            }
                        )
                        continue

                    meta = val.get("metadata") if isinstance(val.get("metadata"), dict) else {}
                    ext_acc = str(meta.get("phone_number_id") or entry_id).strip()

                    if isinstance(val.get("statuses"), list) and val["statuses"]:
                        events.append({"externalAccountId": ext_acc, "statuses": val["statuses"]})

                    messages = val.get("messages")
                    contacts = val.get("contacts")
                    contact_names: dict[str, str] = {}
                    if isinstance(contacts, list):
                        for c in contacts:
                            if isinstance(c, dict):
                                wa_id = str(c.get("wa_id") or "").strip()
                                prof = c.get("profile") if isinstance(c.get("profile"), dict) else {}
                                if wa_id:
                                    contact_names[wa_id] = str(prof.get("name") or "").strip()

                    if isinstance(messages, list) and messages:
                        for wm in messages:
                            if not isinstance(wm, dict):
                                continue
                            wa_from = str(wm.get("from") or "").strip()
                            text_obj = wm.get("text") if isinstance(wm.get("text"), dict) else {}
                            btn_obj = wm.get("button") if isinstance(wm.get("button"), dict) else {}
                            body = str(text_obj.get("body") or btn_obj.get("text") or "").strip()
                            events.append(
                                {
                                    "externalAccountId": ext_acc,
                                    "messageId": str(wm.get("id") or "").strip(),
                                    "from": wa_from,
                                    "phone": f"+{wa_from}" if wa_from and not wa_from.startswith("+") else wa_from,
                                    "threadId": wa_from,
                                    "senderName": contact_names.get(wa_from, ""),
                                    "text": body,
                                }
                            )
                        continue

                    # Instagram comment webhook: entry.changes[].value
                    if val.get("text") and isinstance(val.get("from"), dict):
                        frm = val["from"]
                        events.append(
                            {
                                "externalAccountId": ext_acc,
                                "messageId": str(val.get("id") or "").strip(),
                                "from": str(frm.get("id") or "").strip(),
                                "senderName": str(frm.get("username") or "").strip(),
                                "threadId": str(frm.get("id") or val.get("id") or "").strip(),
                                "text": str(val.get("text") or "").strip(),
                            }
                        )
        if events:
            return events

    # TikTok multi/single webhook payload normalization
    if plat == "TIKTOK" and isinstance(payload.get("content"), dict):
        content = payload["content"]
        return [
            {
                "externalAccountId": str(payload.get("user_openid") or content.get("owner_openid") or "").strip(),
                "messageId": str(content.get("comment_id") or content.get("message_id") or "").strip(),
                "from": str(content.get("user_openid") or content.get("sender_openid") or "").strip(),
                "threadId": str(content.get("conversation_id") or content.get("user_openid") or "").strip(),
                "text": str(content.get("text") or "").strip(),
            }
        ]

    return [dict(payload)]


def _process_single_webhook_event(
    *,
    plat: str,
    channel: SocialChannel,
    norm: dict[str, Any],
    raw_body: bytes,
    full_payload: dict[str, Any],
) -> dict[str, Any]:
    # Handle Meta message_template_status_update webhook (filtered by name + language_code)
    tpl_update = norm.get("templateStatusUpdate")
    if isinstance(tpl_update, dict) and tpl_update.get("name"):
        ev = str(tpl_update.get("event") or "").upper()
        mapped_status = (
            SocialWhatsAppTemplate.Status.APPROVED
            if ev == "APPROVED"
            else (
                SocialWhatsAppTemplate.Status.REJECTED
                if ev in ("REJECTED", "DISABLED", "PAUSED")
                else None
            )
        )
        updated = 0
        if mapped_status:
            qs = SocialWhatsAppTemplate.objects.filter(channel=channel, name=tpl_update["name"])
            lang = str(tpl_update.get("language") or "").strip()
            if lang:
                qs = qs.filter(language_code=lang)
            updated = qs.update(status=mapped_status)
            record_audit(
                actor=None,
                action="social.whatsapp_template.webhook_status",
                entity_type="SocialChannel",
                entity_id=str(channel.id),
                metadata={"template": tpl_update["name"], "language": lang, "status": mapped_status, "updated": updated},
            )
        return {"duplicate": False, "templateStatusUpdates": updated}

    # Handle delivery status updates scoped to this channel's conversations
    statuses = norm.get("statuses")
    if isinstance(statuses, list) and statuses:
        updated = 0
        for st in statuses:
            if not isinstance(st, dict):
                continue
            mid = str(st.get("id") or "").strip()
            new_status = str(st.get("status") or "").upper()
            if mid and new_status:
                updated += SocialInboxMessage.objects.filter(
                    conversation__channel=channel,
                    external_message_id=mid,
                ).update(delivery_status=new_status[:32])
        return {"duplicate": False, "statusUpdates": updated}

    ext_msg_id = str(norm.get("messageId") or norm.get("id") or "").strip()
    thread_id = str(norm.get("threadId") or norm.get("from") or ext_msg_id or "default").strip()
    sender_id = str(norm.get("from") or norm.get("senderId") or "").strip()
    sender_name = str(norm.get("senderName") or "").strip()
    sender_phone = str(norm.get("phone") or "").strip()
    text_body = str(norm.get("text") or norm.get("body") or "").strip()
    product_sku = str(norm.get("productSku") or "").strip()

    body_digest = hashlib.sha256(raw_body).hexdigest()[:32]
    idem_key = f"social:{plat}:{channel.id}:{ext_msg_id}" if ext_msg_id else f"social:{plat}:{channel.id}:{body_digest}"
    if IntegrationEvent.objects.filter(idempotency_key=idem_key[:128]).exists():
        return {"duplicate": True, "threadId": thread_id}

    IntegrationEvent.objects.create(
        event_id=idem_key[:128],
        source_system=IntegrationEvent.SourceSystem.EXTERNAL,
        event_type=f"social.{plat.lower()}.inbound",
        idempotency_key=idem_key[:128],
        payload=full_payload,
        status=IntegrationEvent.Status.PROCESSED,
    )

    customer = None
    if sender_phone:
        customer = Customer.objects.filter(phone=sender_phone).first()
        if customer is None and sender_name:
            customer = Customer.objects.create(
                full_name=sender_name[:160],
                phone=sender_phone[:32],
                segment=Customer.Segment.B2C,
                notes=f"Sosyal kaynak: {plat}",
            )

    product = ProductModel.objects.filter(parent_sku=product_sku).first() if product_sku else None
    now = timezone.now()

    conv, _ = SocialInboxConversation.objects.get_or_create(
        channel=channel,
        external_thread_id=thread_id[:128],
        defaults={
            "platform": plat,
            "external_sender_id": sender_id[:128],
            "sender_display_name": sender_name[:160],
            "sender_phone": sender_phone[:32],
            "customer": customer,
            "product": product,
        },
    )
    conv.last_message_at = now
    conv.last_inbound_at = now
    if customer and not conv.customer_id:
        conv.customer = customer
    if product and not conv.product_id:
        conv.product = product
    conv.save(update_fields=["last_message_at", "last_inbound_at", "customer", "product", "updated_at"])

    if plat == "WHATSAPP" and customer is not None and text_body.lower() in WHATSAPP_OPT_OUT_KEYWORDS:
        append_consent(
            customer=customer,
            purpose=ConsentPurpose.COMMERCIAL_WHATSAPP,
            channel=ConsentChannel.WHATSAPP,
            status=ConsentStatus.WITHDRAWN,
            source=ConsentSource.INTEGRATION,
            evidence={"keyword": text_body, "threadId": thread_id},
        )

    if text_body:
        try:
            SocialInboxMessage.objects.create(
                conversation=conv,
                direction=SocialInboxMessage.Direction.INBOUND,
                external_message_id=ext_msg_id[:128],
                body=text_body,
                attached_product=product,
                delivery_status="RECEIVED",
                raw_payload=norm,
            )
        except IntegrityError:
            return {"duplicate": True, "conversationId": str(conv.id), "threadId": thread_id}

    return {"duplicate": False, "conversationId": str(conv.id), "threadId": thread_id}


@transaction.atomic
def ingest_social_webhook(
    *,
    platform: str,
    raw_body: bytes,
    signature_header: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Hardened multi-event webhook ingestion:
    - Platform-aware multi-event extraction (all Meta/IG, WhatsApp Cloud API, TikTok events).
    - Mandatory HMAC-SHA256 signature verification (never bypassed).
    - Exact channel matching by external_account_id.
    - Deterministic SHA-256 idempotency + DB unique constraint.
    - Handles Meta template status updates (name + language), delivery statuses, & opt-out.
    """
    plat = platform.upper()
    events = _extract_webhook_events(plat, payload)
    first_event = events[0] if events else payload
    channel = _resolve_webhook_channel(plat, first_event)
    secret = _resolve_webhook_secret(channel)
    if not secret:
        raise SocialCommerceError(
            "Webhook gizli anahtarı tanımlı değil; imzasız webhook kabul edilmez.",
            code="WEBHOOK_SECRET_MISSING",
            status_code=403,
        )
    if not verify_hmac_sha256(raw_body=raw_body, secret=secret, signature_header=signature_header):
        raise SocialCommerceError("Geçersiz webhook imzası.", code="INVALID_SIGNATURE", status_code=403)

    if len(events) == 1:
        return _process_single_webhook_event(
            plat=plat,
            channel=channel,
            norm=events[0],
            raw_body=raw_body,
            full_payload=payload,
        )

    results = []
    for ev in events:
        ev_channel = _resolve_webhook_channel(plat, ev) if ev.get("externalAccountId") else channel
        results.append(
            _process_single_webhook_event(
                plat=plat,
                channel=ev_channel,
                norm=ev,
                raw_body=raw_body,
                full_payload=payload,
            )
        )
    return {"duplicate": all(r.get("duplicate") for r in results), "processed": len(results), "events": results}


def _classify_outbound_as_marketing(
    *,
    conversation: SocialInboxConversation,
    template_name: str,
    language_code: str,
    attached_product_sku: str,
    in_24h_window: bool,
) -> bool:
    """
    Server-side classification of marketing vs transactional/support messages.
    Uses registered SocialWhatsAppTemplate.category (never infers from template name prefixes)
    and fails closed (treats unregistered templates as marketing) to protect KVKK consent.
    """
    tpl = (template_name or "").strip()
    if tpl:
        tpl_obj = (
            SocialWhatsAppTemplate.objects.filter(
                channel=conversation.channel,
                name=tpl,
                language_code=(language_code or "tr").strip(),
            ).first()
            or SocialWhatsAppTemplate.objects.filter(
                channel=conversation.channel,
                name=tpl,
            ).first()
        )
        if tpl_obj is not None:
            return tpl_obj.category == SocialWhatsAppTemplate.Category.MARKETING
        # Unregistered template fails closed for KVKK marketing consent safety
        return True
    if attached_product_sku and not in_24h_window:
        return True
    if conversation.platform == "WHATSAPP" and not in_24h_window:
        return True
    return False


def reply_to_inbox_conversation(
    *,
    conversation: SocialInboxConversation,
    body: str,
    attached_product_sku: str = "",
    template_name: str = "",
    language_code: str = "tr",
    actor=None,
) -> SocialInboxMessage:
    """
    Send an outbound reply:
    - Backend determines marketing intent and enforces KVKK consent.
    - Enforces WhatsApp 24-hour customer service window (requires template_name outside 24h).
    - Runs external HTTP call OUTSIDE database transaction; never logs failed sends as SENT.
    """
    in_24h_window = (
        conversation.last_inbound_at is not None
        and (timezone.now() - conversation.last_inbound_at) <= timedelta(hours=24)
    )
    is_marketing = _classify_outbound_as_marketing(
        conversation=conversation,
        template_name=template_name,
        language_code=language_code,
        attached_product_sku=attached_product_sku,
        in_24h_window=in_24h_window,
    )

    if conversation.platform == "WHATSAPP" and not in_24h_window and not template_name:
        raise SocialCommerceError(
            "WhatsApp 24 saatlik müşteri penceresi dışında serbest metin gönderilemez; onaylı template_name gereklidir.",
            code="WHATSAPP_TEMPLATE_REQUIRED",
            status_code=400,
        )

    if conversation.platform == "WHATSAPP" and template_name:
        tpl_obj = (
            SocialWhatsAppTemplate.objects.filter(
                channel=conversation.channel,
                name=template_name.strip(),
                language_code=(language_code or "tr").strip(),
            ).first()
            or SocialWhatsAppTemplate.objects.filter(
                channel=conversation.channel,
                name=template_name.strip(),
            ).first()
        )
        if tpl_obj is not None and tpl_obj.status != SocialWhatsAppTemplate.Status.APPROVED:
            raise SocialCommerceError(
                "WhatsApp şablonu henüz Meta tarafından onaylanmamış.",
                code="TEMPLATE_NOT_APPROVED",
                status_code=400,
            )

    if is_marketing and conversation.platform == "WHATSAPP":
        if not channel_consent_ok(channel="WHATSAPP", customer=conversation.customer):
            raise SocialCommerceError(
                "WhatsApp ticari ileti için aktif müşteri izni (KVKK) bulunmuyor.",
                code="CONSENT_REQUIRED",
                status_code=403,
            )

    product = (
        ProductModel.objects.filter(parent_sku=attached_product_sku, owner_organization__isnull=True).first()
        if attached_product_sku
        else None
    )
    text = body.strip()
    if product is not None:
        dto = build_social_b2c_product_dto(product)
        text = f"{text}\n\n{dto['title']} — {dto['price']}\n{dto['link']}".strip()

    adapter = get_adapter(conversation.platform)
    token = decrypt_connection_token(getattr(conversation.channel, "connection", None))
    recipient = conversation.external_sender_id or conversation.sender_phone or conversation.external_thread_id

    # External HTTP call outside DB transaction
    if conversation.platform == "WHATSAPP" and template_name:
        res = adapter.send_template(
            access_token=token,
            external_account_id=conversation.channel.external_account_id,
            recipient_id=recipient,
            template_name=template_name,
            language_code=language_code,
        )
    else:
        res = adapter.send_message(
            access_token=token,
            external_account_id=conversation.channel.external_account_id,
            recipient_id=recipient,
            body=text,
        )

    delivery_status = "SENT" if res.ok else "FAILED"
    with transaction.atomic():
        msg = SocialInboxMessage.objects.create(
            conversation=conversation,
            direction=SocialInboxMessage.Direction.OUTBOUND,
            external_message_id=res.external_id[:128],
            body=text or f"[template:{template_name}]",
            attached_product=product,
            sent_by=actor,
            delivery_status=delivery_status,
        )
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["last_message_at", "updated_at"])

    if not res.ok:
        raise SocialCommerceError(
            res.error or "Mesaj gönderilemedi.",
            code=res.status or "SEND_FAILED",
            status_code=502 if res.status == "ERROR" else 400,
        )
    return msg

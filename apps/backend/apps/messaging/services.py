"""Outbound SMS/WhatsApp with consent-aware helpers used by recovery."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.audit.services import record_audit
from apps.consent.models import ConsentChannel, ConsentPurpose
from apps.consent.services import has_active_consent
from apps.customers.models import Customer

from .models import ChannelOutboundLog
from .providers import send_channel_message, sms_enabled, whatsapp_enabled


PURPOSE_BY_CHANNEL = {
    ConsentChannel.EMAIL: ConsentPurpose.COMMERCIAL_EMAIL,
    ConsentChannel.SMS: ConsentPurpose.COMMERCIAL_SMS,
    ConsentChannel.WHATSAPP: ConsentPurpose.COMMERCIAL_WHATSAPP,
    "EMAIL": ConsentPurpose.COMMERCIAL_EMAIL,
    "SMS": ConsentPurpose.COMMERCIAL_SMS,
    "WHATSAPP": ConsentPurpose.COMMERCIAL_WHATSAPP,
}


def resolve_customer_phone(*, user=None, customer: Customer | None = None) -> str:
    if customer and (customer.phone or "").strip():
        return customer.phone.strip()
    if user is not None and (getattr(user, "phone", "") or "").strip():
        return str(user.phone).strip()
    return ""


def channel_consent_ok(
    *,
    channel: str,
    customer: Customer | None = None,
    guest_email: str = "",
) -> bool:
    purpose = PURPOSE_BY_CHANNEL.get(channel)
    if not purpose:
        return False
    consent_channel = channel if channel in ConsentChannel.values else channel
    return has_active_consent(
        customer=customer,
        guest_email=guest_email,
        purpose=purpose,
        channel=consent_channel,
    )


@transaction.atomic
def enqueue_channel_message(
    *,
    channel: str,
    recipient: str,
    body: str,
    template_key: str = "",
    context: dict[str, Any] | None = None,
    correlation_id: str = "",
    skip_reason: str = "",
    actor=None,
) -> ChannelOutboundLog:
    if skip_reason:
        log = ChannelOutboundLog.objects.create(
            channel=channel,
            recipient=(recipient or "")[:64],
            template_key=template_key,
            body=body,
            status=ChannelOutboundLog.Status.SKIPPED,
            skip_reason=skip_reason,
            context_snapshot=context or {},
            correlation_id=correlation_id or "",
        )
        return log

    result = send_channel_message(
        channel=channel,
        recipient=recipient,
        body=body,
        template_key=template_key,
        context=context,
    )
    status = (
        ChannelOutboundLog.Status.SENT
        if result.get("ok")
        else ChannelOutboundLog.Status.FAILED
    )
    log = ChannelOutboundLog.objects.create(
        channel=channel,
        recipient=(recipient or "")[:64],
        template_key=template_key,
        body=body,
        status=status,
        provider=str(result.get("provider") or ""),
        provider_ref=str(result.get("provider_ref") or "")[:128],
        error_message=str(result.get("error") or ""),
        context_snapshot=context or {},
        correlation_id=correlation_id or "",
    )
    record_audit(
        action="CHANNEL_MESSAGE_SENT" if status == ChannelOutboundLog.Status.SENT else "CHANNEL_MESSAGE_FAILED",
        entity_type="ChannelOutboundLog",
        entity_id=str(log.id),
        actor=actor,
        metadata={"channel": channel, "template_key": template_key, "status": status},
    )
    return log


def messaging_status() -> dict[str, Any]:
    from django.conf import settings

    return {
        "smsEnabled": sms_enabled(),
        "whatsappEnabled": whatsapp_enabled(),
        "smsProvider": getattr(settings, "MESSAGING_SMS_PROVIDER", "console"),
        "whatsappProvider": getattr(settings, "MESSAGING_WHATSAPP_PROVIDER", "console"),
        "smsWebhookConfigured": bool(getattr(settings, "MESSAGING_SMS_WEBHOOK_URL", "")),
        "whatsappWebhookConfigured": bool(
            getattr(settings, "MESSAGING_WHATSAPP_WEBHOOK_URL", "")
        ),
    }

"""Consent domain services — append-only grants/withdrawals + active check."""

from __future__ import annotations

import hashlib
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit
from apps.customers.models import Customer

from .models import ConsentChannel, ConsentLog, ConsentPurpose, ConsentSource, ConsentStatus


def _pepper() -> str:
    return getattr(settings, "CONSENT_HASH_PEPPER", None) or settings.SECRET_KEY


def hash_pii_value(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    material = f"{_pepper()}:{value}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _latest_log(
    *,
    customer: Customer | None = None,
    guest_email: str = "",
    purpose: str,
    channel: str,
) -> ConsentLog | None:
    qs = ConsentLog.objects.filter(purpose=purpose, channel=channel)
    if customer is not None:
        qs = qs.filter(customer=customer)
    elif guest_email:
        qs = qs.filter(guest_email__iexact=guest_email.strip().lower())
    else:
        return None
    return qs.order_by("-created_at").first()


def has_active_consent(
    *,
    customer: Customer | None = None,
    guest_email: str = "",
    purpose: str,
    channel: str,
) -> bool:
    latest = _latest_log(
        customer=customer, guest_email=guest_email, purpose=purpose, channel=channel
    )
    return latest is not None and latest.status == ConsentStatus.GRANTED


@transaction.atomic
def append_consent(
    *,
    customer: Customer | None = None,
    guest_email: str = "",
    purpose: str,
    channel: str,
    status: str,
    source: str = ConsentSource.INTEGRATION,
    document_version: str = "",
    document_hash: str = "",
    legal_document=None,
    iys_reference: str = "",
    ip_address: str = "",
    user_agent: str = "",
    correlation_id: str = "",
    evidence: dict[str, Any] | None = None,
    actor=None,
) -> ConsentLog:
    now = timezone.now()
    log = ConsentLog.objects.create(
        customer=customer,
        guest_email=(guest_email or "").strip().lower(),
        purpose=purpose,
        channel=channel,
        status=status,
        source=source,
        granted_at=now if status == ConsentStatus.GRANTED else None,
        withdrawn_at=now if status == ConsentStatus.WITHDRAWN else None,
        document_version=document_version or "",
        document_hash=document_hash or "",
        legal_document=legal_document,
        iys_reference=iys_reference or "",
        ip_hash=hash_pii_value(ip_address),
        user_agent_hash=hash_pii_value(user_agent),
        correlation_id=correlation_id or "",
        evidence=evidence or {},
    )

    record_audit(
        action="CONSENT_APPENDED",
        entity_type="ConsentLog",
        entity_id=str(log.id),
        actor=actor,
        metadata={
            "purpose": purpose,
            "channel": channel,
            "status": status,
            "customer_id": str(customer.id) if customer else None,
            "guest_email": guest_email or None,
        },
    )

    commercial = {
        (ConsentPurpose.COMMERCIAL_EMAIL, ConsentChannel.EMAIL),
        (ConsentPurpose.COMMERCIAL_SMS, ConsentChannel.SMS),
        (ConsentPurpose.COMMERCIAL_WHATSAPP, ConsentChannel.WHATSAPP),
    }
    if status == ConsentStatus.WITHDRAWN and (purpose, channel) in commercial:
        _suppress_recovery_for_withdraw(customer=customer, guest_email=guest_email, actor=actor)

    return log


def _suppress_recovery_for_withdraw(
    *, customer: Customer | None, guest_email: str, actor=None
) -> None:
    from apps.commerce.models import CartRecoverySession
    from apps.commerce.recovery import suppress_b2c_cart

    if customer and customer.user_id:
        suppress_b2c_cart(
            user=customer.user,
            reason=CartRecoverySession.SuppressReason.CONSENT_WITHDRAWN,
        )
    email = (guest_email or (customer.email if customer else "") or "").strip().lower()
    if email:
        CartRecoverySession.objects.filter(
            segment=CartRecoverySession.Segment.B2C,
            status=CartRecoverySession.Status.ACTIVE,
            guest_email__iexact=email,
            user__isnull=True,
        ).update(
            status=CartRecoverySession.Status.SUPPRESSED,
            suppress_reason=CartRecoverySession.SuppressReason.CONSENT_WITHDRAWN,
            updated_at=timezone.now(),
        )


def serialize_consent_log(log: ConsentLog) -> dict:
    return {
        "id": str(log.id),
        "customerId": str(log.customer_id) if log.customer_id else None,
        "guestEmail": log.guest_email or None,
        "purpose": log.purpose,
        "channel": log.channel,
        "status": log.status,
        "source": log.source,
        "grantedAt": log.granted_at.isoformat() if log.granted_at else None,
        "withdrawnAt": log.withdrawn_at.isoformat() if log.withdrawn_at else None,
        "documentVersion": log.document_version,
        "documentHash": log.document_hash,
        "legalDocumentId": str(log.legal_document_id) if log.legal_document_id else None,
        "iysReference": log.iys_reference or None,
        "correlationId": log.correlation_id or None,
        "createdAt": log.created_at.isoformat(),
    }

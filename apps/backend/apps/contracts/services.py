"""Contract acceptance — order-bound only."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit
from apps.consent.services import hash_pii_value
from apps.customers.models import Customer

from .models import ContractAcceptance, LegalDocument


def get_published_document(code: str, *, audience: str = LegalDocument.Audience.B2C) -> LegalDocument | None:
    qs = LegalDocument.objects.filter(code=code, is_published=True).order_by(
        "-effective_from", "-created_at"
    )
    doc = qs.filter(audience__in=[audience, LegalDocument.Audience.ALL]).first()
    return doc


@transaction.atomic
def record_order_acceptances(
    *,
    customer: Customer,
    order,
    document_codes: list[str] | None = None,
    source: str = ContractAcceptance.Source.CHECKOUT,
    ip_address: str = "",
    user_agent: str = "",
    correlation_id: str = "",
    evidence: dict[str, Any] | None = None,
    actor=None,
) -> list[ContractAcceptance]:
    """
    Create immutable ContractAcceptance rows for the given order.
    Only call when a purchase/order actually exists — never on cart create.
    """
    codes = document_codes or [
        LegalDocument.Code.DISTANCE_SALES,
        LegalDocument.Code.PRE_INFO,
    ]
    now = timezone.now()
    created: list[ContractAcceptance] = []
    for code in codes:
        if ContractAcceptance.objects.filter(order=order, document_code=code).exists():
            continue
        doc = get_published_document(code)
        if doc is None:
            continue
        acceptance = ContractAcceptance.objects.create(
            customer=customer,
            order=order,
            document=doc,
            document_code=code,
            document_version=doc.version,
            content_hash=doc.content_hash or doc.compute_content_hash(),
            accepted_at=now,
            source=source,
            evidence=evidence or {},
            ip_hash=hash_pii_value(ip_address),
            user_agent_hash=hash_pii_value(user_agent),
            correlation_id=correlation_id or "",
        )
        created.append(acceptance)
        record_audit(
            action="CONTRACT_ACCEPTED",
            entity_type="ContractAcceptance",
            entity_id=str(acceptance.id),
            actor=actor,
            metadata={
                "order_no": getattr(order, "order_no", None),
                "document_code": code,
                "document_version": doc.version,
                "content_hash": acceptance.content_hash,
            },
        )
    return created


def serialize_legal_document(doc: LegalDocument, *, include_body: bool = True) -> dict:
    payload = {
        "id": str(doc.id),
        "code": doc.code,
        "version": doc.version,
        "title": doc.title,
        "contentHash": doc.content_hash,
        "effectiveFrom": doc.effective_from.isoformat() if doc.effective_from else None,
        "isPublished": doc.is_published,
        "audience": doc.audience,
        "createdAt": doc.created_at.isoformat(),
        "updatedAt": doc.updated_at.isoformat(),
    }
    if include_body:
        payload["bodyHtml"] = doc.body_html
        payload["bodyMd"] = doc.body_md
    return payload


def serialize_contract_acceptance(row: ContractAcceptance) -> dict:
    return {
        "id": str(row.id),
        "customerId": str(row.customer_id),
        "orderId": str(row.order_id),
        "orderNo": getattr(row.order, "order_no", None),
        "documentId": str(row.document_id),
        "documentCode": row.document_code,
        "documentVersion": row.document_version,
        "contentHash": row.content_hash,
        "acceptedAt": row.accepted_at.isoformat(),
        "source": row.source,
        "correlationId": row.correlation_id or None,
        "createdAt": row.created_at.isoformat(),
    }

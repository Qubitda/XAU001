"""Typed processors for B2C inbound IntegrationEvent payloads."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent
from apps.contracts.models import ContractAcceptance, LegalDocument
from apps.contracts.services import record_order_acceptances
from apps.customers.models import Customer
from apps.customers.services import upsert_customer_from_external
from apps.commerce.models import B2cOrder

from .models import IntegrationEvent


class ProcessorError(Exception):
    def __init__(self, message: str, *, code: str = "PROCESSOR_ERROR"):
        super().__init__(message)
        self.code = code


def _require(payload: dict, *keys: str) -> None:
    missing = [k for k in keys if payload.get(k) in (None, "")]
    if missing:
        raise ProcessorError(f"Eksik alanlar: {', '.join(missing)}", code="VALIDATION_ERROR")


@transaction.atomic
def process_customer_upsert(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, "externalId", "fullName")
    customer, created = upsert_customer_from_external(
        external_id=str(payload["externalId"]),
        full_name=str(payload["fullName"]),
        email=str(payload.get("email") or ""),
        phone=str(payload.get("phone") or ""),
        segment=str(payload.get("segment") or Customer.Segment.B2C),
        email_verified=payload.get("emailVerified"),
        identity_or_tax_no=str(payload.get("identityOrTaxNo") or ""),
        city=str(payload.get("city") or ""),
        address=str(payload.get("address") or ""),
    )
    return {
        "customerId": str(customer.id),
        "externalId": customer.external_id,
        "created": created,
    }


@transaction.atomic
def process_consent_append(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, "purpose", "channel", "status")
    customer = None
    customer_id = payload.get("customerId") or payload.get("opsCustomerId")
    external_id = payload.get("externalCustomerId") or payload.get("externalId")
    if customer_id:
        customer = Customer.objects.filter(id=customer_id).first()
        if customer is None:
            raise ProcessorError("Müşteri bulunamadı.", code="CUSTOMER_NOT_FOUND")
    elif external_id:
        customer = Customer.objects.filter(external_id=str(external_id)).first()
        if customer is None and payload.get("email"):
            customer, _ = upsert_customer_from_external(
                external_id=str(external_id),
                full_name=str(payload.get("fullName") or payload.get("email")),
                email=str(payload.get("email") or ""),
                phone=str(payload.get("phone") or ""),
            )

    status = str(payload["status"]).upper()
    if status not in ConsentStatus.values:
        raise ProcessorError("Geçersiz izin durumu.", code="INVALID_STATUS")

    purpose = str(payload["purpose"]).upper()
    channel = str(payload["channel"]).upper()
    if purpose not in ConsentPurpose.values:
        raise ProcessorError("Geçersiz izin amacı.", code="INVALID_PURPOSE")
    if channel not in ConsentChannel.values:
        raise ProcessorError("Geçersiz kanal.", code="INVALID_CHANNEL")

    legal_doc = None
    doc_id = payload.get("legalDocumentId")
    if doc_id:
        legal_doc = LegalDocument.objects.filter(id=doc_id).first()

    log = append_consent(
        customer=customer,
        guest_email=str(payload.get("guestEmail") or payload.get("email") or ""),
        purpose=purpose,
        channel=channel,
        status=status,
        source=str(payload.get("source") or ConsentSource.INTEGRATION).upper(),
        document_version=str(payload.get("documentVersion") or ""),
        document_hash=str(payload.get("documentHash") or ""),
        legal_document=legal_doc,
        iys_reference=str(payload.get("iysReference") or ""),
        ip_address=str(payload.get("ipAddress") or ""),
        user_agent=str(payload.get("userAgent") or ""),
        correlation_id=str(payload.get("correlationId") or ""),
        evidence=payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {},
    )
    return {"consentLogId": str(log.id), "status": log.status}


@transaction.atomic
def process_contract_accept(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, "orderId")
    order = B2cOrder.objects.select_related("customer").filter(id=payload["orderId"]).first()
    if order is None:
        order_no = payload.get("orderNo")
        if order_no:
            order = B2cOrder.objects.select_related("customer").filter(order_no=order_no).first()
    if order is None:
        raise ProcessorError("Sipariş bulunamadı — sözleşme kabulü yalnızca sipariş ile.", code="ORDER_REQUIRED")

    customer = order.customer
    if customer is None:
        raise ProcessorError("Siparişte müşteri yok.", code="CUSTOMER_REQUIRED")

    codes = payload.get("documentCodes")
    if not isinstance(codes, list) or not codes:
        codes = [LegalDocument.Code.DISTANCE_SALES, LegalDocument.Code.PRE_INFO]

    rows = record_order_acceptances(
        customer=customer,
        order=order,
        document_codes=[str(c) for c in codes],
        source=ContractAcceptance.Source.INTEGRATION,
        ip_address=str(payload.get("ipAddress") or ""),
        user_agent=str(payload.get("userAgent") or ""),
        correlation_id=str(payload.get("correlationId") or ""),
        evidence=payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {},
    )
    return {
        "orderId": str(order.id),
        "acceptanceIds": [str(r.id) for r in rows],
        "count": len(rows),
    }


def process_cart_upsert(payload: dict[str, Any]) -> dict[str, Any]:
    from apps.commerce.cart_sync import upsert_cart_from_external

    try:
        return upsert_cart_from_external(payload)
    except ValueError as exc:
        raise ProcessorError(str(exc), code="CART_VALIDATION") from exc


def process_cart_event(payload: dict[str, Any]) -> dict[str, Any]:
    from apps.commerce.cart_sync import ingest_cart_event

    try:
        return ingest_cart_event(payload)
    except Exception as exc:
        raise ProcessorError(str(exc), code="CART_EVENT_ERROR") from exc


PROCESSORS: dict[str, Any] = {
    "customer.upsert": process_customer_upsert,
    "customer.created": process_customer_upsert,
    "customer.updated": process_customer_upsert,
    "consent.append": process_consent_append,
    "consent.granted": process_consent_append,
    "consent.withdrawn": process_consent_append,
    "contract.accept": process_contract_accept,
    "cart.upsert": process_cart_upsert,
    "cart.updated": process_cart_upsert,
    "cart.event": process_cart_event,
    "cart.abandoned": process_cart_event,
    "cart.recovered": process_cart_event,
}


@transaction.atomic
def process_integration_event(event: IntegrationEvent) -> IntegrationEvent:
    event = IntegrationEvent.objects.select_for_update().get(pk=event.pk)
    if event.status in (IntegrationEvent.Status.PROCESSED, IntegrationEvent.Status.DUPLICATE):
        return event

    processor = PROCESSORS.get(event.event_type)
    if processor is None:
        event.status = IntegrationEvent.Status.FAILED
        event.error_message = f"Bilinmeyen event_type: {event.event_type}"
        event.save(update_fields=["status", "error_message", "updated_at"])
        return event

    try:
        result = processor(event.payload if isinstance(event.payload, dict) else {})
        event.status = IntegrationEvent.Status.PROCESSED
        event.result = result or {}
        event.error_message = ""
        event.save(update_fields=["status", "result", "error_message", "updated_at"])
    except ProcessorError as exc:
        event.status = IntegrationEvent.Status.FAILED
        event.error_message = f"{exc.code}: {exc}"
        event.save(update_fields=["status", "error_message", "updated_at"])
    except Exception as exc:  # pragma: no cover
        event.status = IntegrationEvent.Status.FAILED
        event.error_message = str(exc)[:2000]
        event.save(update_fields=["status", "error_message", "updated_at"])
    return event


def parse_occurred_at(value: Any):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value
    if isinstance(value, str):
        return parse_datetime(value)
    return None

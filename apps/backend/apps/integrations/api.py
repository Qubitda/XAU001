"""B2C → OPS inbound integration API."""

from __future__ import annotations

import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.common.responses import envelope_response
from apps.idempotency.mixins import IdempotentCreateMixin
from config.exceptions import DomainError

from .models import IntegrationEvent
from .processors import PROCESSORS, parse_occurred_at, process_integration_event


class HasIntegrationsB2cWrite(BasePermission):
    """Require authenticated API key with integrations:b2c:write scope."""

    def has_permission(self, request, view) -> bool:
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return False
        return "integrations:b2c:write" in (api_key.scopes or [])


class B2cIntegrationEventSerializer(serializers.Serializer):
    eventId = serializers.CharField(max_length=128, required=False, allow_blank=True)
    eventType = serializers.CharField(max_length=64)
    sourceSystem = serializers.ChoiceField(
        choices=IntegrationEvent.SourceSystem.values,
        default=IntegrationEvent.SourceSystem.B2C_STOREFRONT,
        required=False,
    )
    schemaVersion = serializers.CharField(max_length=16, required=False, default="1.0")
    occurredAt = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    correlationId = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    idempotencyKey = serializers.CharField(max_length=128, required=False, allow_blank=True)
    payload = serializers.DictField(child=serializers.JSONField(), required=False)


def _serialize_event(event: IntegrationEvent, *, duplicate: bool = False) -> dict:
    return {
        "id": str(event.id),
        "eventId": event.event_id,
        "eventType": event.event_type,
        "sourceSystem": event.source_system,
        "schemaVersion": event.schema_version,
        "status": event.status,
        "duplicate": duplicate or event.status == IntegrationEvent.Status.DUPLICATE,
        "correlationId": event.correlation_id or None,
        "idempotencyKey": event.idempotency_key,
        "result": event.result or {},
        "errorMessage": event.error_message or None,
        "receivedAt": event.received_at.isoformat() if event.received_at else None,
        "occurredAt": event.occurred_at.isoformat() if event.occurred_at else None,
    }


def _ingest_event(*, data: dict, default_event_type: str | None = None) -> tuple[IntegrationEvent, bool]:
    event_type = (data.get("eventType") or default_event_type or "").strip()
    if not event_type:
        raise DomainError("eventType zorunludur.", code="EVENT_TYPE_REQUIRED", status_code=400)
    if event_type not in PROCESSORS and default_event_type is None:
        # Allow known processor keys only for primary events endpoint
        if event_type not in PROCESSORS:
            raise DomainError(
                f"Desteklenmeyen eventType: {event_type}",
                code="UNSUPPORTED_EVENT_TYPE",
                status_code=400,
            )

    event_id = (data.get("eventId") or "").strip() or f"auto-{uuid.uuid4().hex}"
    idem_key = (data.get("idempotencyKey") or "").strip() or event_id
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    # Shortcut endpoints may send resource fields at top level
    if not payload and default_event_type:
        payload = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "eventId",
                "eventType",
                "sourceSystem",
                "schemaVersion",
                "occurredAt",
                "correlationId",
                "idempotencyKey",
                "payload",
            }
        }

    existing = IntegrationEvent.objects.filter(idempotency_key=idem_key).first()
    if existing is None:
        existing = IntegrationEvent.objects.filter(event_id=event_id).first()
    if existing is not None:
        if existing.status == IntegrationEvent.Status.RECEIVED:
            process_integration_event(existing)
            existing.refresh_from_db()
        return existing, True

    try:
        with transaction.atomic():
            event = IntegrationEvent.objects.create(
                event_id=event_id,
                source_system=data.get("sourceSystem")
                or IntegrationEvent.SourceSystem.B2C_STOREFRONT,
                event_type=event_type,
                schema_version=data.get("schemaVersion") or "1.0",
                occurred_at=parse_occurred_at(data.get("occurredAt")) or timezone.now(),
                correlation_id=(data.get("correlationId") or "").strip(),
                idempotency_key=idem_key,
                payload=payload,
                status=IntegrationEvent.Status.RECEIVED,
            )
    except IntegrityError:
        existing = (
            IntegrationEvent.objects.filter(idempotency_key=idem_key).first()
            or IntegrationEvent.objects.filter(event_id=event_id).first()
        )
        if existing is None:
            raise
        return existing, True

    process_integration_event(event)
    event.refresh_from_db()
    return event, False


class B2cIntegrationEventsView(IdempotentCreateMixin, APIView):
    permission_classes = [HasIntegrationsB2cWrite]
    api_key_scopes = ["integrations:b2c:write"]

    @extend_schema(tags=["Integrations - B2C"], summary="B2C inbound event inbox", request=B2cIntegrationEventSerializer)
    def post(self, request: Request):
        ser = B2cIntegrationEventSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        event, duplicate = _ingest_event(data=ser.validated_data)
        status_code = 200 if duplicate else (201 if event.status == IntegrationEvent.Status.PROCESSED else 202)
        if event.status == IntegrationEvent.Status.FAILED and not duplicate:
            status_code = 422
        return envelope_response(
            _serialize_event(event, duplicate=duplicate),
            request,
            status=status_code,
        )


class _ShortcutIngestView(IdempotentCreateMixin, APIView):
    permission_classes = [HasIntegrationsB2cWrite]
    api_key_scopes = ["integrations:b2c:write"]
    default_event_type = ""

    def post(self, request: Request):
        data = dict(request.data) if hasattr(request.data, "items") else {}
        if not data.get("eventType"):
            data["eventType"] = self.default_event_type
        if "payload" not in data:
            # Treat body as payload + optional envelope fields
            envelope_keys = {
                "eventId",
                "eventType",
                "sourceSystem",
                "schemaVersion",
                "occurredAt",
                "correlationId",
                "idempotencyKey",
            }
            payload = {k: v for k, v in data.items() if k not in envelope_keys}
            data = {**{k: data[k] for k in envelope_keys if k in data}, "payload": payload, "eventType": data["eventType"]}
        event, duplicate = _ingest_event(data=data, default_event_type=self.default_event_type)
        status_code = 200 if duplicate else (201 if event.status == IntegrationEvent.Status.PROCESSED else 202)
        if event.status == IntegrationEvent.Status.FAILED and not duplicate:
            status_code = 422
        return envelope_response(
            _serialize_event(event, duplicate=duplicate),
            request,
            status=status_code,
        )


class B2cIntegrationCustomersView(_ShortcutIngestView):
    default_event_type = "customer.upsert"

    @extend_schema(tags=["Integrations - B2C"], summary="B2C customer upsert shortcut")
    def post(self, request: Request):
        return super().post(request)


class B2cIntegrationConsentsView(_ShortcutIngestView):
    default_event_type = "consent.append"

    @extend_schema(tags=["Integrations - B2C"], summary="B2C consent append shortcut")
    def post(self, request: Request):
        return super().post(request)


class B2cIntegrationContractsView(_ShortcutIngestView):
    default_event_type = "contract.accept"

    @extend_schema(tags=["Integrations - B2C"], summary="B2C contract acceptance shortcut")
    def post(self, request: Request):
        return super().post(request)


class B2cIntegrationCartsView(_ShortcutIngestView):
    default_event_type = "cart.upsert"

    @extend_schema(tags=["Integrations - B2C"], summary="B2C cart upsert / event ingest")
    def post(self, request: Request):
        return super().post(request)

"""OPS messaging channel status + outbound logs."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response, paginated_envelope_response

from .models import ChannelOutboundLog
from .services import messaging_status


def serialize_outbound(log: ChannelOutboundLog) -> dict:
    return {
        "id": str(log.id),
        "channel": log.channel,
        "recipient": log.recipient,
        "templateKey": log.template_key,
        "status": log.status,
        "provider": log.provider,
        "providerRef": log.provider_ref or None,
        "skipReason": log.skip_reason or None,
        "errorMessage": log.error_message or None,
        "correlationId": log.correlation_id or None,
        "createdAt": log.created_at.isoformat(),
    }


class OpsMessagingStatusView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "notifications:manage"

    @extend_schema(tags=["OPS - Messaging"], summary="SMS/WhatsApp kanal durumu")
    def get(self, request: Request):
        return envelope_response(messaging_status(), request)


class OpsMessagingLogListView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "notifications:manage"

    @extend_schema(tags=["OPS - Messaging"], summary="Kanal gönderim logları")
    def get(self, request: Request):
        qs = ChannelOutboundLog.objects.all().order_by("-created_at")
        channel = (request.query_params.get("channel") or "").strip().upper()
        if channel:
            qs = qs.filter(channel=channel)
        status = (request.query_params.get("status") or "").strip().upper()
        if status:
            qs = qs.filter(status=status)
        return paginated_envelope_response(qs, request, serialize_outbound)

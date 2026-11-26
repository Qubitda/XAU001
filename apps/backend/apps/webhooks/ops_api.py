import secrets

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from apps.organizations.models import Organization
from config.exceptions import DomainError

from .models import (
    ORGANIZATION_WEBHOOK_EVENTS,
    PLATFORM_WEBHOOK_EVENTS,
    WEBHOOK_EVENTS,
    WebhookEndpoint,
)
from .url_safety import validate_webhook_url


def serialize_webhook_endpoint(endpoint: WebhookEndpoint) -> dict:
    return {
        "id": str(endpoint.id),
        "organizationId": str(endpoint.organization_id) if endpoint.organization_id else None,
        "organizationCode": endpoint.organization.code if endpoint.organization_id else None,
        "organizationName": endpoint.organization.name if endpoint.organization_id else None,
        "isPlatform": endpoint.is_platform,
        "url": endpoint.url,
        "events": endpoint.events or [],
        "isActive": endpoint.is_active,
        "createdAt": endpoint.created_at.isoformat(),
        "updatedAt": endpoint.updated_at.isoformat(),
    }


class OpsWebhookCreateSerializer(serializers.Serializer):
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    isPlatform = serializers.BooleanField(required=False, default=False)
    url = serializers.URLField(max_length=512)
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=list(WEBHOOK_EVENTS)),
        allow_empty=False,
    )


class OpsWebhookListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Webhooks"], summary="Webhook uç noktalarını listele")
    def get(self, request: Request):
        qs = WebhookEndpoint.objects.select_related("organization").order_by("-created_at")
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id, is_platform=False)
        platform = request.query_params.get("isPlatform")
        if platform in ("true", "false", "1", "0"):
            qs = qs.filter(is_platform=platform in ("true", "1"))
        active = request.query_params.get("isActive")
        if active in ("true", "false", "1", "0"):
            qs = qs.filter(is_active=active in ("true", "1"))
        return envelope_response([serialize_webhook_endpoint(ep) for ep in qs], request)

    @extend_schema(tags=["OPS - Webhooks"], summary="Webhook uç noktası oluştur")
    def post(self, request: Request):
        serializer = OpsWebhookCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        is_platform = bool(d.get("isPlatform"))
        events = list(d["events"])
        url = validate_webhook_url(d["url"])

        if is_platform:
            invalid = [e for e in events if e not in PLATFORM_WEBHOOK_EVENTS]
            if invalid:
                raise DomainError(
                    f"Platform webhook yalnızca şu olayları alabilir: {sorted(PLATFORM_WEBHOOK_EVENTS)}.",
                    code="WEBHOOK_EVENTS_INVALID",
                    status_code=400,
                )
            organization = None
        else:
            invalid = [e for e in events if e not in ORGANIZATION_WEBHOOK_EVENTS]
            if invalid:
                raise DomainError(
                    "Bayi webhook'ları B2C olaylarını alamaz (kiracı sızıntısı engeli). "
                    f"İzinli olaylar: {sorted(ORGANIZATION_WEBHOOK_EVENTS)}.",
                    code="WEBHOOK_EVENTS_INVALID",
                    status_code=400,
                )
            org_id = d.get("organizationId")
            if not org_id:
                raise DomainError(
                    "Bayi webhook için organizationId zorunlu.",
                    code="ORG_REQUIRED",
                    status_code=400,
                )
            organization = Organization.objects.filter(id=org_id, is_active=True).first()
            if organization is None:
                raise DomainError("Firma bulunamadı.", code="ORG_NOT_FOUND", status_code=404)

        endpoint = WebhookEndpoint.objects.create(
            organization=organization,
            is_platform=is_platform,
            url=url,
            events=events,
            secret=secrets.token_hex(32),
        )
        payload = serialize_webhook_endpoint(endpoint)
        payload["secret"] = endpoint.secret
        payload["meta"] = {"secretShownOnce": True, "note": "Webhook secret yalnızca oluşturulurken gösterilir."}
        return envelope_response(payload, request, status=201)


class OpsWebhookRevokeView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Webhooks"], summary="Webhook uç noktasını iptal et (sil)")
    def post(self, request: Request, endpoint_id: str):
        endpoint = WebhookEndpoint.objects.select_related("organization").filter(id=endpoint_id).first()
        if endpoint is None:
            raise DomainError("Webhook bulunamadı.", code="WEBHOOK_NOT_FOUND", status_code=404)
        endpoint.is_active = False
        endpoint.save(update_fields=["is_active", "updated_at"])
        return envelope_response(serialize_webhook_endpoint(endpoint), request)

    def delete(self, request: Request, endpoint_id: str):
        return self.post(request, endpoint_id)

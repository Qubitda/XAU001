import uuid

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from apps.organizations.models import Organization
from config.exceptions import DomainError

from .constants import VALID_SCOPES
from .models import ApiKey
from .services import create_api_key, revoke_api_key


def serialize_api_key(api_key: ApiKey, *, include_plaintext: str | None = None) -> dict:
    payload = {
        "id": str(api_key.id),
        "name": api_key.name,
        "prefix": api_key.prefix,
        "organizationId": str(api_key.organization_id),
        "organizationCode": api_key.organization.code,
        "organizationName": api_key.organization.name,
        "scopes": api_key.scopes or [],
        "isActive": api_key.is_active,
        "expiresAt": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "lastUsedAt": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        "createdById": str(api_key.created_by_id),
        "createdByEmail": api_key.created_by.email,
        "createdAt": api_key.created_at.isoformat(),
        "updatedAt": api_key.updated_at.isoformat(),
    }
    if include_plaintext:
        payload["key"] = include_plaintext
        payload["meta"] = {
            "plaintextShownOnce": True,
            "ownerUserId": str(api_key.created_by_id),
            "note": (
                "Storefront cart/order kayıtları bu kullanıcıya (created_by) bağlanır. "
                "Anahtarı güvenli saklayın; yeniden görüntülenemez."
            ),
        }
    return payload


class OpsApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    organizationId = serializers.UUIDField()
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=sorted(VALID_SCOPES)),
        required=False,
        allow_empty=False,
    )
    expiresAt = serializers.DateTimeField(required=False, allow_null=True)


class OpsApiKeyListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "api_keys:read",
        "POST": "api_keys:manage",
    }

    @extend_schema(tags=["OPS - API Keys"], summary="API anahtarlarını listele")
    def get(self, request: Request):
        qs = (
            ApiKey.objects.select_related("organization", "created_by")
            .order_by("-created_at")
        )
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        active = request.query_params.get("isActive")
        if active in ("true", "false", "1", "0"):
            qs = qs.filter(is_active=active in ("true", "1"))
        return envelope_response([serialize_api_key(k) for k in qs], request)

    @extend_schema(tags=["OPS - API Keys"], summary="Yeni API anahtarı oluştur (plaintext bir kez)")
    def post(self, request: Request):
        serializer = OpsApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        organization = Organization.objects.filter(id=data["organizationId"], is_active=True).first()
        if organization is None:
            raise DomainError("Firma bulunamadı.", code="ORG_NOT_FOUND", status_code=404)

        expires_at = data.get("expiresAt")
        api_key, plaintext = create_api_key(
            organization=organization,
            name=data["name"],
            created_by=request.user,
            scopes=data.get("scopes"),
            expires_at=expires_at,
        )
        record_audit(
            action="api_key.create",
            entity_type="api_key",
            entity_id=str(api_key.id),
            actor=request.user,
            organization=organization,
            metadata={"name": api_key.name, "prefix": api_key.prefix, "scopes": api_key.scopes},
        )
        api_key = ApiKey.objects.select_related("organization", "created_by").get(pk=api_key.pk)
        return envelope_response(serialize_api_key(api_key, include_plaintext=plaintext), request, status=201)


class OpsApiKeyRevokeView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "POST": "api_keys:manage",
        "DELETE": "api_keys:manage",
    }

    @extend_schema(tags=["OPS - API Keys"], summary="API anahtarını iptal et (revoke)")
    def post(self, request: Request, key_id: uuid.UUID):
        return self._revoke(request, key_id)

    def delete(self, request: Request, key_id: uuid.UUID):
        return self._revoke(request, key_id)

    def _revoke(self, request: Request, key_id: uuid.UUID):
        api_key = (
            ApiKey.objects.select_related("organization", "created_by")
            .filter(id=key_id)
            .first()
        )
        if api_key is None:
            raise DomainError("API anahtarı bulunamadı.", code="NOT_FOUND", status_code=404)
        if not api_key.is_active:
            return envelope_response(serialize_api_key(api_key), request)
        api_key = revoke_api_key(api_key)
        record_audit(
            action="api_key.revoke",
            entity_type="api_key",
            entity_id=str(api_key.id),
            actor=request.user,
            organization=api_key.organization,
            metadata={"name": api_key.name, "prefix": api_key.prefix},
        )
        api_key = ApiKey.objects.select_related("organization", "created_by").get(pk=api_key.pk)
        return envelope_response(serialize_api_key(api_key), request)
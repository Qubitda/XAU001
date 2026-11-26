from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import (
    apply_safe_ordering,
    envelope_response,
    paginated_envelope_response,
)
from config.exceptions import DomainError
from .models import AuditLog


def serialize_ops_audit_log(log: AuditLog) -> dict:
    return {
        "id": str(log.id),
        "actorId": str(log.actor_id) if log.actor_id else None,
        "actorEmail": log.actor.email if log.actor else None,
        "actorName": log.actor.full_name if log.actor else None,
        "organizationId": str(log.organization_id) if log.organization_id else None,
        "organizationCode": log.organization.code if log.organization else None,
        "action": log.action,
        "entityType": log.entity_type,
        "entityId": log.entity_id,
        "metadata": log.metadata,
        "createdAt": log.created_at.isoformat(),
    }


class OpsAuditLogListView(APIView):
    """Strictly read-only AuditLog endpoint."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "audit:read"

    @extend_schema(tags=["OPS - Audit"], summary="Denetim kayıtlarını listele ve filtrele (salt okunur)")
    def get(self, request: Request):
        qs = AuditLog.objects.select_related("actor", "organization")
        action = (request.query_params.get("action") or "").strip()
        if action:
            qs = qs.filter(action=action)
        entity_type = (request.query_params.get("entityType") or request.query_params.get("entity_type") or "").strip()
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        entity_id = (request.query_params.get("entityId") or request.query_params.get("entity_id") or "").strip()
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        actor_id = (request.query_params.get("actorId") or "").strip()
        if actor_id:
            qs = qs.filter(actor_id=actor_id)
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(action__icontains=q)
                | Q(entity_type__icontains=q)
                | Q(entity_id__icontains=q)
                | Q(actor__email__icontains=q)
            )
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "action": "action", "entityType": "entity_type"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_audit_log)


class OpsAuditLogDetailView(APIView):
    """Strictly read-only AuditLog detail endpoint."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "audit:read"

    @extend_schema(tags=["OPS - Audit"], summary="Denetim kaydı detayını getir (salt okunur)")
    def get(self, request: Request, log_id: str):
        log = AuditLog.objects.select_related("actor", "organization").filter(id=log_id).first()
        if log is None:
            raise DomainError("Denetim kaydı bulunamadı.", code="AUDIT_LOG_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_audit_log(log), request)

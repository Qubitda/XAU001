import uuid
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import (
    apply_safe_ordering,
    envelope_response,
    paginated_envelope_response,
)
from apps.organizations.models import Organization
from config.exceptions import DomainError
from .models import WorkOrder
from .services import create_work_order, transition_work_order_status


def serialize_ops_work_order(wo: WorkOrder) -> dict:
    return {
        "id": str(wo.id),
        "workOrderNo": wo.work_order_no,
        "sourceOrderNo": wo.source_order_no,
        "organizationId": str(wo.organization_id) if wo.organization_id else None,
        "organizationCode": wo.organization.code if wo.organization else None,
        "organizationName": wo.organization.name if wo.organization else None,
        "sku": wo.sku,
        "size": wo.size,
        "quantity": wo.quantity,
        "engravingOrStampNote": wo.engraving_or_stamp_note,
        "status": wo.status,
        "createdAt": wo.created_at.isoformat(),
        "updatedAt": wo.updated_at.isoformat(),
    }


class OpsWorkOrderCreateSerializer(serializers.Serializer):
    workOrderNo = serializers.CharField(max_length=40, required=False, allow_blank=True)
    sourceOrderNo = serializers.CharField(max_length=40)
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    sku = serializers.CharField(max_length=64)
    size = serializers.IntegerField(min_value=0, max_value=70, default=14)
    quantity = serializers.IntegerField(min_value=1, max_value=1000, default=1)
    engravingOrStampNote = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class OpsWorkOrderUpdateSerializer(serializers.Serializer):
    size = serializers.IntegerField(min_value=0, max_value=70, required=False)
    quantity = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    engravingOrStampNote = serializers.CharField(max_length=120, required=False, allow_blank=True)


class OpsWorkOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=WorkOrder.Status.values)


def _find_work_order(work_order_id: str, *, for_update: bool = False) -> WorkOrder | None:
    qs = WorkOrder.objects.select_related("organization")
    if for_update:
        qs = qs.select_for_update()
    wo = qs.filter(work_order_no=work_order_id).first()
    if wo is not None:
        return wo
    try:
        uuid.UUID(str(work_order_id))
        return qs.filter(id=work_order_id).first()
    except ValueError:
        return None


class OpsWorkOrderListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "production:manage"

    @extend_schema(tags=["OPS - Production"], summary="Atölye iş emirlerini listele")
    def get(self, request: Request):
        qs = WorkOrder.objects.select_related("organization")
        status_val = (request.query_params.get("status") or "").strip().upper()
        if status_val:
            qs = qs.filter(status=status_val)
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        source_order = (request.query_params.get("sourceOrderNo") or "").strip()
        if source_order:
            qs = qs.filter(source_order_no__icontains=source_order)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(work_order_no__icontains=q)
                | Q(source_order_no__icontains=q)
                | Q(sku__icontains=q)
                | Q(engraving_or_stamp_note__icontains=q)
            )
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "workOrderNo": "work_order_no", "status": "status"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_work_order)

    @extend_schema(tags=["OPS - Production"], summary="Yeni atölye iş emri oluştur", request=OpsWorkOrderCreateSerializer)
    def post(self, request: Request):
        serializer = OpsWorkOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        org = None
        if d.get("organizationId"):
            org = Organization.objects.filter(id=d["organizationId"]).first()
            if org is None:
                raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)

        wo = create_work_order(
            work_order_no=d.get("workOrderNo"),
            source_order_no=d["sourceOrderNo"],
            organization=org,
            sku=d["sku"],
            size=d["size"],
            quantity=d["quantity"],
            engraving_or_stamp_note=d.get("engravingOrStampNote", ""),
            actor=request.user,
        )
        wo = WorkOrder.objects.select_related("organization").get(id=wo.id)
        return envelope_response(serialize_ops_work_order(wo), request, status=201)


class OpsWorkOrderDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "production:manage"

    @extend_schema(tags=["OPS - Production"], summary="İş emri detayını getir")
    def get(self, request: Request, work_order_id: str):
        wo = _find_work_order(work_order_id)
        if wo is None:
            raise DomainError("İş emri bulunamadı.", code="WORK_ORDER_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_work_order(wo), request)

    @extend_schema(tags=["OPS - Production"], summary="İş emri detaylarını güncelle", request=OpsWorkOrderUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, work_order_id: str):
        wo = _find_work_order(work_order_id, for_update=True)
        if wo is None:
            raise DomainError("İş emri bulunamadı.", code="WORK_ORDER_NOT_FOUND", status_code=404)
        if wo.status == WorkOrder.Status.COMPLETED:
            raise DomainError("Tamamlanmış iş emri değiştirilemez.", code="WORK_ORDER_LOCKED", status_code=409)

        serializer = OpsWorkOrderUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "size" in d:
            wo.size = d["size"]
        if "quantity" in d:
            wo.quantity = d["quantity"]
        if "engravingOrStampNote" in d:
            wo.engraving_or_stamp_note = d["engravingOrStampNote"].strip()
        wo.save()
        record_audit(
            action="WORK_ORDER_UPDATED",
            entity_type="WorkOrder",
            entity_id=wo.work_order_no,
            actor=request.user,
            organization=wo.organization,
        )
        return envelope_response(serialize_ops_work_order(wo), request)


class OpsWorkOrderStatusView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "production:manage"

    @extend_schema(tags=["OPS - Production"], summary="İş emri üretim aşamasını state-machine üzerinden ilerlet", request=OpsWorkOrderStatusSerializer)
    def patch(self, request: Request, work_order_id: str):
        serializer = OpsWorkOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wo = transition_work_order_status(
            work_order_id_or_no=work_order_id,
            next_status=serializer.validated_data["status"],
            actor=request.user,
        )
        wo = WorkOrder.objects.select_related("organization").get(id=wo.id)
        return envelope_response(serialize_ops_work_order(wo), request)

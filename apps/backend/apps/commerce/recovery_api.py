"""OPS API for abandoned-cart / draft sales follow-up tasks."""

from django.db import transaction
from django.utils import timezone
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
from config.exceptions import DomainError

from .models import OpsSalesTask
from .recovery import serialize_ops_sales_task


class OpsSalesTaskUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[OpsSalesTask.Status.DONE, OpsSalesTask.Status.DISMISSED, OpsSalesTask.Status.OPEN]
    )
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class OpsSalesTaskListView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    @extend_schema(tags=["OPS - Sales Tasks"], summary="Satış takip görevlerini listele")
    def get(self, request: Request):
        qs = OpsSalesTask.objects.select_related("user", "organization")
        status = (request.query_params.get("status") or "").strip().upper()
        if status == "ALL":
            pass
        elif status:
            qs = qs.filter(status=status)
        else:
            qs = qs.filter(status=OpsSalesTask.Status.OPEN)
        segment = (request.query_params.get("segment") or "").strip().upper()
        if segment:
            qs = qs.filter(segment=segment)
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"dueAt": "due_at", "createdAt": "created_at", "cartValueTry": "cart_value_try"},
            default="-due_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_sales_task)


class OpsSalesTaskDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    @extend_schema(tags=["OPS - Sales Tasks"], summary="Satış takip görevi detayı")
    def get(self, request: Request, task_id: str):
        task = OpsSalesTask.objects.select_related("user", "organization").filter(id=task_id).first()
        if task is None:
            raise DomainError("Görev bulunamadı.", code="NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_sales_task(task), request)

    @extend_schema(
        tags=["OPS - Sales Tasks"],
        summary="Görevi tamamla / kapat",
        request=OpsSalesTaskUpdateSerializer,
    )
    @transaction.atomic
    def patch(self, request: Request, task_id: str):
        task = (
            OpsSalesTask.objects.select_for_update()
            .select_related("user", "organization")
            .filter(id=task_id)
            .first()
        )
        if task is None:
            raise DomainError("Görev bulunamadı.", code="NOT_FOUND", status_code=404)
        serializer = OpsSalesTaskUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        if "status" in d:
            task.status = d["status"]
            if d["status"] in (OpsSalesTask.Status.DONE, OpsSalesTask.Status.DISMISSED):
                task.completed_by = request.user
                task.completed_at = timezone.now()
            elif d["status"] == OpsSalesTask.Status.OPEN:
                task.completed_by = None
                task.completed_at = None
        if "note" in d:
            task.note = (d.get("note") or "").strip()[:500]
        task.save()
        record_audit(
            action="OPS_SALES_TASK_UPDATED",
            entity_type="OpsSalesTask",
            entity_id=str(task.id),
            actor=request.user,
            metadata={"status": task.status},
        )
        task = OpsSalesTask.objects.select_related("user", "organization").get(id=task.id)
        return envelope_response(serialize_ops_sales_task(task), request)

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
from .api import _serialize_b2c_order, serialize_ops_b2b_order
from .models import B2bOrder, B2cOrder


class OpsB2cOrderListView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    @extend_schema(tags=["OPS - Orders"], summary="Tüm B2C perakende siparişlerini listele ve filtrele")
    def get(self, request: Request):
        qs = B2cOrder.objects.select_related("customer", "created_by", "rate_snapshot").prefetch_related("items")
        status_val = (request.query_params.get("status") or "").strip().upper()
        if status_val:
            qs = qs.filter(status=status_val)
        payment = (request.query_params.get("paymentMethod") or "").strip().upper()
        if payment:
            qs = qs.filter(payment_method=payment)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(order_no__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__email__icontains=q)
                | Q(customer__phone__icontains=q)
            )
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={
                "createdAt": "created_at",
                "grandTotalTry": "grand_total_try",
                "orderNo": "order_no",
                "status": "status",
            },
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, _serialize_b2c_order)


class OpsB2cOrderDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    @extend_schema(tags=["OPS - Orders"], summary="B2C sipariş detayını getir")
    def get(self, request: Request, order_no: str):
        order = (
            B2cOrder.objects.select_related("customer", "created_by", "rate_snapshot")
            .prefetch_related("items")
            .filter(order_no=order_no)
            .first()
        )
        if order is None:
            raise DomainError("B2C sipariş bulunamadı.", code="ORDER_NOT_FOUND", status_code=404)
        return envelope_response(_serialize_b2c_order(order), request)


class OpsB2bOrderListView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    @extend_schema(tags=["OPS - Orders"], summary="Tüm B2B bayi siparişlerini listele ve filtrele")
    def get(self, request: Request):
        qs = B2bOrder.objects.select_related(
            "organization", "branch", "created_by", "rate_snapshot"
        ).prefetch_related("lines")
        status_val = (request.query_params.get("status") or "").strip().upper()
        if status_val:
            qs = qs.filter(status=status_val)
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        settlement = (request.query_params.get("settlementMethod") or "").strip().upper()
        if settlement:
            qs = qs.filter(settlement_method=settlement)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(order_no__icontains=q)
                | Q(organization__code__icontains=q)
                | Q(organization__name__icontains=q)
                | Q(contact_person__icontains=q)
            )
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={
                "createdAt": "created_at",
                "totalWholesaleUsd": "total_wholesale_usd",
                "totalWholesaleTry": "total_wholesale_try",
                "orderNo": "order_no",
                "status": "status",
            },
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_b2b_order)


class OpsB2bOrderDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    @extend_schema(tags=["OPS - Orders"], summary="B2B sipariş detayını getir")
    def get(self, request: Request, order_no: str):
        order = (
            B2bOrder.objects.select_related("organization", "branch", "created_by", "rate_snapshot")
            .prefetch_related("lines")
            .filter(order_no=order_no)
            .first()
        )
        if order is None:
            raise DomainError("B2B sipariş bulunamadı.", code="ORDER_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_b2b_order(order), request)

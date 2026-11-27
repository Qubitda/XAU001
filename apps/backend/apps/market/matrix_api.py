"""OPS Settings API endpoints for central ExchangeMetalMatrix management."""

from __future__ import annotations

from decimal import Decimal
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response, paginated_envelope_response
from config.exceptions import DomainError
from .matrix_services import (
    create_matrix_draft,
    get_or_create_active_matrix,
    publish_matrix_version,
    serialize_exchange_metal_matrix,
)
from .models import ExchangeMetalMatrix


class ExchangeMetalMatrixCreateSerializer(serializers.Serializer):
    fxBaseRates = serializers.DictField(
        child=serializers.DecimalField(max_digits=16, decimal_places=4, min_value=Decimal("0.0001")),
    )
    note = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    autoPublish = serializers.BooleanField(required=False, default=False)


class OpsExchangeMetalMatrixActiveView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "POST": "rates:edit",
    }

    @extend_schema(tags=["OPS - Settings"], summary="Aktif Çapraz Kur & Değerli Metal Matrisini getir")
    def get(self, request: Request):
        matrix = get_or_create_active_matrix(actor=request.user)
        return envelope_response(serialize_exchange_metal_matrix(matrix), request)

    @extend_schema(
        tags=["OPS - Settings"],
        summary="Yeni Çapraz Kur & Değerli Metal Matrisi taslak versiyonu oluştur",
        request=ExchangeMetalMatrixCreateSerializer,
    )
    def post(self, request: Request):
        ser = ExchangeMetalMatrixCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        matrix = create_matrix_draft(
            d["fxBaseRates"],
            actor=request.user,
            note=d.get("note", ""),
        )
        if d.get("autoPublish"):
            matrix, _ = publish_matrix_version(str(matrix.id), actor=request.user)
        return envelope_response(serialize_exchange_metal_matrix(matrix), request, status=201)


class OpsExchangeMetalMatrixVersionsView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:read"

    @extend_schema(tags=["OPS - Settings"], summary="Çapraz Kur & Değerli Metal Matrisi versiyon geçmişi")
    def get(self, request: Request):
        qs = ExchangeMetalMatrix.objects.prefetch_related("rates").select_related("created_by").filter(
            organization__isnull=True
        )
        return paginated_envelope_response(qs, request, serialize_exchange_metal_matrix)


class OpsExchangeMetalMatrixDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:read"

    @extend_schema(tags=["OPS - Settings"], summary="Belirli bir matris versiyonunu getir")
    def get(self, request: Request, matrix_id: str):
        matrix = (
            ExchangeMetalMatrix.objects.prefetch_related("rates")
            .select_related("created_by")
            .filter(id=matrix_id)
            .first()
        )
        if matrix is None:
            raise DomainError("Matris versiyonu bulunamadı.", code="NOT_FOUND", status_code=404)
        return envelope_response(serialize_exchange_metal_matrix(matrix), request)


class OpsExchangeMetalMatrixPublishView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "rates:edit"

    @extend_schema(tags=["OPS - Settings"], summary="Taslak matris versiyonunu yayınla")
    def post(self, request: Request, matrix_id: str):
        matrix, _ = publish_matrix_version(matrix_id, actor=request.user)
        return envelope_response(serialize_exchange_metal_matrix(matrix), request)

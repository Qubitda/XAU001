"""OPS catalog variant, stone-line, media, and category endpoints."""
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.catalog.api.ops_serializers import _validate_https_url
from apps.catalog.models import ProductMedia, ProductModel, ProductVariant, StoneLine
from apps.catalog.services import sync_default_variant_center_carat
from apps.common.responses import (
    CARAT_Q,
    GRAM_Q,
    apply_safe_ordering,
    dec_str,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from apps.inventory.services import (
    get_or_create_default_warehouse,
    set_variant_warehouse_stock,
    sync_variant_and_product_stock,
)
from config.exceptions import DomainError

from .serializers import (
    OpsStoneLineCreateSerializer,
    OpsStoneLineUpdateSerializer,
    serialize_ops_stone_line,
)

class OpsStoneLineListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Taş satırlarını listele")
    def get(self, request: Request):
        qs = StoneLine.objects.select_related("product")
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(product__parent_sku=parent_sku)
        role = (request.query_params.get("role") or "").strip().upper()
        if role:
            qs = qs.filter(role=role)
        qs = apply_safe_ordering(qs, request, allowed_fields={"createdAt": "created_at", "carat": "carat"}, default="created_at")
        return paginated_envelope_response(qs, request, serialize_ops_stone_line)

    @extend_schema(tags=["OPS - Catalog"], summary="Ürüne yeni taş satırı ekle", request=OpsStoneLineCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsStoneLineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        product = ProductModel.objects.select_for_update().filter(parent_sku=d["parentSku"].strip().upper()).first()
        if product is None:
            raise DomainError("Ana ürün modeli bulunamadı.", code="PRODUCT_NOT_FOUND", status_code=404)

        stone = StoneLine.objects.create(
            product=product,
            role=d["role"],
            stone_type=d["stoneType"].strip(),
            measure_unit=d["measureUnit"],
            count=d["count"],
            carat=d["carat"],
            clarity=d.get("clarity", "").strip(),
            color_grade=d.get("colorGrade", "").strip(),
            cut_shape=d.get("cutShape", "").strip(),
        )
        sync_default_variant_center_carat(product)
        record_audit(
            action="OPS_STONE_LINE_CREATED",
            entity_type="StoneLine",
            entity_id=str(stone.id),
            actor=request.user,
            metadata={"parent_sku": product.parent_sku, "role": stone.role, "carat": str(stone.carat)},
        )
        stone = StoneLine.objects.select_related("product").get(id=stone.id)
        return envelope_response(serialize_ops_stone_line(stone), request, status=201)


class OpsStoneLineDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Taş satırı detayını getir")
    def get(self, request: Request, stone_id: str):
        stone = StoneLine.objects.select_related("product").filter(id=stone_id).first()
        if stone is None:
            raise DomainError("Taş satırı bulunamadı.", code="STONE_LINE_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_stone_line(stone), request)

    @extend_schema(tags=["OPS - Catalog"], summary="Taş satırını güncelle", request=OpsStoneLineUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, stone_id: str):
        stone = StoneLine.objects.select_for_update().select_related("product").filter(id=stone_id).first()
        if stone is None:
            raise DomainError("Taş satırı bulunamadı.", code="STONE_LINE_NOT_FOUND", status_code=404)
        serializer = OpsStoneLineUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        field_map = {
            "role": "role",
            "stoneType": "stone_type",
            "measureUnit": "measure_unit",
            "count": "count",
            "carat": "carat",
            "clarity": "clarity",
            "colorGrade": "color_grade",
            "cutShape": "cut_shape",
        }
        for api_key, model_field in field_map.items():
            if api_key in d:
                val = d[api_key].strip() if isinstance(d[api_key], str) else d[api_key]
                setattr(stone, model_field, val)
        stone.save()
        sync_default_variant_center_carat(stone.product)
        record_audit(
            action="OPS_STONE_LINE_UPDATED",
            entity_type="StoneLine",
            entity_id=str(stone.id),
            actor=request.user,
            metadata={"parent_sku": stone.product.parent_sku},
        )
        return envelope_response(serialize_ops_stone_line(stone), request)

    @extend_schema(tags=["OPS - Catalog"], summary="Taş satırını sil")
    @transaction.atomic
    def delete(self, request: Request, stone_id: str):
        stone = StoneLine.objects.select_for_update().select_related("product").filter(id=stone_id).first()
        if stone is None:
            raise DomainError("Taş satırı bulunamadı.", code="STONE_LINE_NOT_FOUND", status_code=404)
        product = stone.product
        parent_sku = product.parent_sku
        stone.delete()
        sync_default_variant_center_carat(product)
        record_audit(
            action="OPS_STONE_LINE_DELETED",
            entity_type="StoneLine",
            entity_id=str(stone_id),
            actor=request.user,
            metadata={"parent_sku": parent_sku},
        )
        return envelope_response({"id": str(stone_id), "deleted": True}, request)



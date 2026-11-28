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
    OpsMediaCreateSerializer,
    OpsMediaUpdateSerializer,
    serialize_ops_media,
)

class OpsProductMediaListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Ürün medya kayıtlarını listele")
    def get(self, request: Request):
        qs = ProductMedia.objects.select_related("product")
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(product__parent_sku=parent_sku)
        role = (request.query_params.get("role") or "").strip().upper()
        if role:
            qs = qs.filter(role=role)
        color = (request.query_params.get("metalColor") or "").strip()
        if color:
            qs = qs.filter(metal_color=color)
        qs = apply_safe_ordering(qs, request, allowed_fields={"sortOrder": "sort_order", "createdAt": "created_at"}, default="sort_order")
        return paginated_envelope_response(qs, request, serialize_ops_media)

    @extend_schema(tags=["OPS - Catalog"], summary="Ürüne yeni medya kaydı ekle", request=OpsMediaCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsMediaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        product = ProductModel.objects.select_for_update().filter(parent_sku=d["parentSku"].strip().upper()).first()
        if product is None:
            raise DomainError("Ana ürün modeli bulunamadı.", code="PRODUCT_NOT_FOUND", status_code=404)

        media = ProductMedia.objects.create(
            product=product,
            metal_color=d["metalColor"],
            role=d["role"],
            url=d["url"].strip(),
            sort_order=d["sortOrder"],
        )
        record_audit(
            action="OPS_MEDIA_CREATED",
            entity_type="ProductMedia",
            entity_id=str(media.id),
            actor=request.user,
            metadata={"parent_sku": product.parent_sku, "role": media.role},
        )
        media = ProductMedia.objects.select_related("product").get(id=media.id)
        return envelope_response(serialize_ops_media(media), request, status=201)


class OpsProductMediaDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Ürün medya detayını getir")
    def get(self, request: Request, media_id: str):
        media = ProductMedia.objects.select_related("product").filter(id=media_id).first()
        if media is None:
            raise DomainError("Medya kaydı bulunamadı.", code="MEDIA_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_media(media), request)

    @extend_schema(tags=["OPS - Catalog"], summary="Ürün medya kaydını güncelle", request=OpsMediaUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, media_id: str):
        media = ProductMedia.objects.select_for_update().select_related("product").filter(id=media_id).first()
        if media is None:
            raise DomainError("Medya kaydı bulunamadı.", code="MEDIA_NOT_FOUND", status_code=404)
        serializer = OpsMediaUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "metalColor" in d:
            media.metal_color = d["metalColor"]
        if "role" in d:
            media.role = d["role"]
        if "url" in d:
            media.url = d["url"].strip()
        if "sortOrder" in d:
            media.sort_order = d["sortOrder"]
        media.save()
        record_audit(
            action="OPS_MEDIA_UPDATED",
            entity_type="ProductMedia",
            entity_id=str(media.id),
            actor=request.user,
            metadata={"parent_sku": media.product.parent_sku},
        )
        return envelope_response(serialize_ops_media(media), request)

    @extend_schema(tags=["OPS - Catalog"], summary="Ürün medya kaydını sil")
    @transaction.atomic
    def delete(self, request: Request, media_id: str):
        media = ProductMedia.objects.select_for_update().select_related("product").filter(id=media_id).first()
        if media is None:
            raise DomainError("Medya kaydı bulunamadı.", code="MEDIA_NOT_FOUND", status_code=404)
        parent_sku = media.product.parent_sku
        media.delete()
        record_audit(
            action="OPS_MEDIA_DELETED",
            entity_type="ProductMedia",
            entity_id=str(media_id),
            actor=request.user,
            metadata={"parent_sku": parent_sku},
        )
        return envelope_response({"id": str(media_id), "deleted": True}, request)



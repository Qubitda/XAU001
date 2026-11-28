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


def serialize_ops_variant(v: ProductVariant) -> dict:
    return {
        "id": str(v.id),
        "productId": str(v.product_id),
        "parentSku": v.product.parent_sku,
        "productTitle": v.product.title,
        "sku": v.sku,
        "purityCode": v.purity_code,
        "metalColor": v.metal_color,
        "size": v.size,
        "centerStoneCarat": dec_str(v.center_stone_carat, CARAT_Q),
        "grossWeightGram": dec_str(v.gross_weight_gram, GRAM_Q),
        "stockQty": v.stock_qty,
        "isDefault": v.is_default,
        "isActive": v.is_active,
        "createdAt": v.created_at.isoformat(),
        "updatedAt": v.updated_at.isoformat(),
    }


def serialize_ops_stone_line(s: StoneLine) -> dict:
    return {
        "id": str(s.id),
        "productId": str(s.product_id),
        "parentSku": s.product.parent_sku,
        "role": s.role,
        "stoneType": s.stone_type,
        "measureUnit": s.measure_unit,
        "count": s.count,
        "carat": dec_str(s.carat, GRAM_Q),
        "clarity": s.clarity,
        "colorGrade": s.color_grade,
        "cutShape": s.cut_shape,
        "createdAt": s.created_at.isoformat(),
        "updatedAt": s.updated_at.isoformat(),
    }


def serialize_ops_media(m: ProductMedia) -> dict:
    return {
        "id": str(m.id),
        "productId": str(m.product_id),
        "parentSku": m.product.parent_sku,
        "metalColor": m.metal_color,
        "role": m.role,
        "url": m.url,
        "sortOrder": m.sort_order,
        "createdAt": m.created_at.isoformat(),
        "updatedAt": m.updated_at.isoformat(),
    }


class OpsVariantCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32)
    sku = serializers.CharField(max_length=64)
    purityCode = serializers.CharField(max_length=16)
    metalColor = serializers.CharField(max_length=32)
    size = serializers.IntegerField(min_value=0, max_value=70, default=14)
    centerStoneCarat = serializers.DecimalField(max_digits=6, decimal_places=3, min_value=Decimal("0"), default=Decimal("0.000"))
    grossWeightGram = serializers.DecimalField(max_digits=10, decimal_places=4, min_value=Decimal("0.01"))
    initialStockQty = serializers.IntegerField(min_value=0, default=0)
    isDefault = serializers.BooleanField(default=False)
    isActive = serializers.BooleanField(default=True)


class OpsVariantUpdateSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64, required=False)
    purityCode = serializers.CharField(max_length=16, required=False)
    metalColor = serializers.CharField(max_length=32, required=False)
    size = serializers.IntegerField(min_value=0, max_value=70, required=False)
    centerStoneCarat = serializers.DecimalField(max_digits=6, decimal_places=3, min_value=Decimal("0"), required=False)
    grossWeightGram = serializers.DecimalField(max_digits=10, decimal_places=4, min_value=Decimal("0.01"), required=False)
    isDefault = serializers.BooleanField(required=False)
    isActive = serializers.BooleanField(required=False)


class OpsStoneLineCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32)
    role = serializers.ChoiceField(choices=StoneLine.Role.values, default=StoneLine.Role.MERKEZ)
    stoneType = serializers.CharField(max_length=48, default="Pırlanta")
    measureUnit = serializers.ChoiceField(choices=["ct", "gr", "mm"], default="ct")
    count = serializers.IntegerField(min_value=1, max_value=2000, default=1)
    carat = serializers.DecimalField(max_digits=8, decimal_places=4, min_value=Decimal("0.0001"))
    clarity = serializers.CharField(max_length=24, required=False, allow_blank=True, default="")
    colorGrade = serializers.CharField(max_length=24, required=False, allow_blank=True, default="")
    cutShape = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class OpsStoneLineUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=StoneLine.Role.values, required=False)
    stoneType = serializers.CharField(max_length=48, required=False)
    measureUnit = serializers.ChoiceField(choices=["ct", "gr", "mm"], required=False)
    count = serializers.IntegerField(min_value=1, max_value=2000, required=False)
    carat = serializers.DecimalField(max_digits=8, decimal_places=4, min_value=Decimal("0.0001"), required=False)
    clarity = serializers.CharField(max_length=24, required=False, allow_blank=True)
    colorGrade = serializers.CharField(max_length=24, required=False, allow_blank=True)
    cutShape = serializers.CharField(max_length=64, required=False, allow_blank=True)


class OpsMediaCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32)
    metalColor = serializers.CharField(max_length=32, default="Beyaz")
    role = serializers.ChoiceField(choices=ProductMedia.MediaRole.values, default=ProductMedia.MediaRole.GALLERY_MAIN)
    url = serializers.CharField(max_length=500)
    sortOrder = serializers.IntegerField(min_value=1, max_value=999, default=1)

    def validate_url(self, value: str) -> str:
        cleaned = _validate_https_url(value)
        if not cleaned:
            raise serializers.ValidationError("Medya URL'si zorunludur.")
        return cleaned


class OpsMediaUpdateSerializer(serializers.Serializer):
    metalColor = serializers.CharField(max_length=32, required=False)
    role = serializers.ChoiceField(choices=ProductMedia.MediaRole.values, required=False)
    url = serializers.CharField(max_length=500, required=False)
    sortOrder = serializers.IntegerField(min_value=1, max_value=999, required=False)

    def validate_url(self, value: str) -> str:
        cleaned = _validate_https_url(value)
        if not cleaned:
            raise serializers.ValidationError("Medya URL'si boş olamaz.")
        return cleaned


class OpsVariantBulkMatrixSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32)
    purities = serializers.ListField(child=serializers.CharField(max_length=16), min_length=1)
    colors = serializers.ListField(child=serializers.CharField(max_length=32), min_length=1)
    sizes = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=70), min_length=1)
    centerStoneCarat = serializers.DecimalField(
        max_digits=6, decimal_places=3, min_value=Decimal("0"), default=Decimal("0.000")
    )
    grossWeightGram = serializers.DecimalField(max_digits=10, decimal_places=4, min_value=Decimal("0.01"))
    initialStockQty = serializers.IntegerField(min_value=0, default=0)



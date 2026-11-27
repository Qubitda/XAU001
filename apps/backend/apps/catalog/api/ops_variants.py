"""
OPS catalog surfaces for product variants, stone lines, and media.

API boundaries (do not conflate):
- Product card fields → catalog product create/patch APIs
- Sellable configs → /api/v1/ops/variants (this module)
- Physical stock → /api/v1/ops/stocks + stock-movements (inventory app)
- Pricing recipes/quotes → pricing ops APIs

Product PATCH must not write WarehouseStock quantities or invent variant axes.
"""

from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
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
from apps.catalog.models import ProductMedia, ProductModel, ProductVariant, StoneLine


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
    url = serializers.URLField(max_length=500)
    sortOrder = serializers.IntegerField(min_value=1, max_value=999, default=1)


class OpsMediaUpdateSerializer(serializers.Serializer):
    metalColor = serializers.ChoiceField(choices=["Beyaz", "Sarı", "Rose"], required=False)
    role = serializers.ChoiceField(choices=ProductMedia.MediaRole.values, required=False)
    url = serializers.URLField(max_length=500, required=False)
    sortOrder = serializers.IntegerField(min_value=1, max_value=999, required=False)


class OpsVariantListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Ürün varyantlarını listele")
    def get(self, request: Request):
        qs = ProductVariant.objects.select_related("product")
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(product__parent_sku=parent_sku)
        purity = (request.query_params.get("purityCode") or request.query_params.get("purity") or "").strip()
        if purity:
            qs = qs.filter(purity_code=purity)
        color = (request.query_params.get("metalColor") or request.query_params.get("color") or "").strip()
        if color:
            qs = qs.filter(metal_color=color)
        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(sku__icontains=q) | Q(product__parent_sku__icontains=q) | Q(product__title__icontains=q))

        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"sku": "sku", "stockQty": "stock_qty", "grossWeightGram": "gross_weight_gram", "createdAt": "created_at"},
            default="-is_default",
        )
        return paginated_envelope_response(qs, request, serialize_ops_variant)

    @extend_schema(tags=["OPS - Catalog"], summary="Yeni ürün varyantı oluştur", request=OpsVariantCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsVariantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        product = ProductModel.objects.filter(parent_sku=d["parentSku"].strip().upper()).first()
        if product is None:
            raise DomainError("Ana ürün modeli bulunamadı.", code="PRODUCT_NOT_FOUND", status_code=404)

        sku = d["sku"].strip().upper()
        if ProductVariant.objects.filter(sku__iexact=sku).exists():
            raise DomainError(f"Varyant SKU zaten mevcut: {sku}", code="DUPLICATE_VARIANT_SKU", status_code=409)

        if d.get("isDefault"):
            ProductVariant.objects.filter(product=product, is_default=True).update(is_default=False)

        try:
            variant = ProductVariant.objects.create(
                product=product,
                sku=sku,
                purity_code=d["purityCode"],
                metal_color=d["metalColor"],
                size=d["size"],
                center_stone_carat=d["centerStoneCarat"],
                gross_weight_gram=d["grossWeightGram"],
                stock_qty=0,
                is_default=d.get("isDefault", False),
                is_active=d.get("isActive", True),
            )
        except IntegrityError as exc:
            raise DomainError(
                "Aynı ayar, renk, ölçü ve karat ekseninde bir varyant zaten mevcut.",
                code="DUPLICATE_VARIANT_AXES",
                status_code=409,
            ) from exc

        if d.get("initialStockQty", 0) > 0:
            from apps.organizations.selectors import resolve_tenant_context

            ctx = resolve_tenant_context(request)
            if "inventory:manage" not in ctx.permissions:
                raise DomainError(
                    "Başlangıç stoğu girmek için 'inventory:manage' yetkisi gereklidir.",
                    code="FORBIDDEN_FIELD",
                    status_code=403,
                )
            set_variant_warehouse_stock(
                variant=variant,
                warehouse=get_or_create_default_warehouse(),
                quantity=d["initialStockQty"],
                reference_no=f"INIT-{variant.sku}",
                actor=request.user,
            )

        record_audit(
            action="OPS_VARIANT_CREATED",
            entity_type="ProductVariant",
            entity_id=variant.sku,
            actor=request.user,
            metadata={"parent_sku": product.parent_sku, "initial_stock_qty": d.get("initialStockQty", 0)},
        )
        variant = ProductVariant.objects.select_related("product").get(id=variant.id)
        return envelope_response(serialize_ops_variant(variant), request, status=201)


class OpsVariantDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "catalog:write",
        "PATCH": "catalog:write",
        "DELETE": "catalog:delete",
    }

    @extend_schema(tags=["OPS - Catalog"], summary="Varyant detayını getir")
    def get(self, request: Request, variant_id: str):
        variant = ProductVariant.objects.select_related("product").filter(id=variant_id).first()
        if variant is None:
            raise DomainError("Varyant bulunamadı.", code="VARIANT_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_variant(variant), request)

    @extend_schema(tags=["OPS - Catalog"], summary="Varyant fiziksel özelliklerini güncelle", request=OpsVariantUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, variant_id: str):
        variant = ProductVariant.objects.select_for_update().select_related("product").filter(id=variant_id).first()
        if variant is None:
            raise DomainError("Varyant bulunamadı.", code="VARIANT_NOT_FOUND", status_code=404)

        serializer = OpsVariantUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "sku" in d:
            new_sku = d["sku"].strip().upper()
            if ProductVariant.objects.filter(sku__iexact=new_sku).exclude(id=variant.id).exists():
                raise DomainError(f"Varyant SKU zaten mevcut: {new_sku}", code="DUPLICATE_VARIANT_SKU", status_code=409)
            variant.sku = new_sku
        if "purityCode" in d:
            variant.purity_code = d["purityCode"]
        if "metalColor" in d:
            variant.metal_color = d["metalColor"]
        if "size" in d:
            variant.size = d["size"]
        if "centerStoneCarat" in d:
            variant.center_stone_carat = d["centerStoneCarat"]
        if "grossWeightGram" in d:
            variant.gross_weight_gram = d["grossWeightGram"]
        if "isDefault" in d:
            if d["isDefault"]:
                ProductVariant.objects.filter(product=variant.product, is_default=True).exclude(id=variant.id).update(is_default=False)
            variant.is_default = d["isDefault"]
        if "isActive" in d:
            variant.is_active = d["isActive"]

        try:
            variant.save()
        except IntegrityError as exc:
            raise DomainError(
                "Aynı ayar, renk, ölçü ve karat ekseninde bir varyant zaten mevcut.",
                code="DUPLICATE_VARIANT_AXES",
                status_code=409,
            ) from exc

        sync_variant_and_product_stock(variant)
        record_audit(
            action="OPS_VARIANT_UPDATED",
            entity_type="ProductVariant",
            entity_id=variant.sku,
            actor=request.user,
            metadata={"parent_sku": variant.product.parent_sku, "is_active": variant.is_active},
        )
        variant = ProductVariant.objects.select_related("product").get(id=variant.id)
        return envelope_response(serialize_ops_variant(variant), request)

    @extend_schema(tags=["OPS - Catalog"], summary="Varyantı pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, variant_id: str):
        variant = ProductVariant.objects.select_for_update().select_related("product").filter(id=variant_id).first()
        if variant is None:
            raise DomainError("Varyant bulunamadı.", code="VARIANT_NOT_FOUND", status_code=404)
        variant.is_active = False
        variant.save(update_fields=["is_active", "updated_at"])
        sync_variant_and_product_stock(variant)
        record_audit(
            action="OPS_VARIANT_DEACTIVATED",
            entity_type="ProductVariant",
            entity_id=variant.sku,
            actor=request.user,
        )
        return envelope_response({"id": str(variant.id), "sku": variant.sku, "isActive": False}, request)


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

        product = ProductModel.objects.filter(parent_sku=d["parentSku"].strip().upper()).first()
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

        product = ProductModel.objects.filter(parent_sku=d["parentSku"].strip().upper()).first()
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


class OpsCategorySummaryView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Katalog kategori, alt kategori ve koleksiyon özetini getir")
    def get(self, request: Request):
        categories = list(
            ProductModel.objects.values("category")
            .annotate(productCount=Count("id"))
            .order_by("category")
        )
        sub_categories = list(
            ProductModel.objects.exclude(sub_category="")
            .values("category", "sub_category")
            .annotate(productCount=Count("id"))
            .order_by("category", "sub_category")
        )
        collections = list(
            ProductModel.objects.values("collection")
            .annotate(productCount=Count("id"))
            .order_by("collection")
        )
        return envelope_response(
            {
                "categories": categories,
                "subCategories": [
                    {
                        "category": row["category"],
                        "subCategory": row["sub_category"],
                        "productCount": row["productCount"],
                    }
                    for row in sub_categories
                ],
                "collections": collections,
            },
            request,
        )

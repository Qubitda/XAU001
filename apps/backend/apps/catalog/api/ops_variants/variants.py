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
    OpsVariantBulkMatrixSerializer,
    OpsVariantCreateSerializer,
    OpsVariantUpdateSerializer,
    serialize_ops_variant,
)

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

        product = ProductModel.objects.select_for_update().filter(parent_sku=d["parentSku"].strip().upper()).first()
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

    @extend_schema(tags=["OPS - Catalog"], summary="Varyantı pasifleştir veya hareketsizse sil")
    @transaction.atomic
    def delete(self, request: Request, variant_id: str):
        variant = ProductVariant.objects.select_for_update().select_related("product").filter(id=variant_id).first()
        if variant is None:
            raise DomainError("Varyant bulunamadı.", code="VARIANT_NOT_FOUND", status_code=404)

        from apps.commerce.models import B2bDraftLine, B2bOrderLine, B2cCartItem, B2cOrderItem
        from apps.inventory.models import StockMovement, WarehouseStock

        has_refs = (
            variant.is_default
            or StockMovement.objects.filter(variant=variant).exists()
            or WarehouseStock.objects.filter(variant=variant, quantity__gt=0).exists()
            or B2cOrderItem.objects.filter(variant=variant).exists()
            or B2bOrderLine.objects.filter(variant=variant).exists()
            or B2cCartItem.objects.filter(variant=variant).exists()
            or B2bDraftLine.objects.filter(variant=variant).exists()
        )
        if not has_refs:
            sku = variant.sku
            product = variant.product
            variant.delete()
            total_avail = sum(
                ProductVariant.objects.filter(product=product, is_active=True).values_list("stock_qty", flat=True)
            )
            product.stock_qty = total_avail
            product.save(update_fields=["stock_qty", "updated_at"])
            record_audit(
                action="OPS_VARIANT_DELETED",
                entity_type="ProductVariant",
                entity_id=sku,
                actor=request.user,
            )
            return envelope_response({"id": str(variant_id), "sku": sku, "isActive": False, "deleted": True}, request)

        variant.is_active = False
        variant.save(update_fields=["is_active", "updated_at"])
        sync_variant_and_product_stock(variant)
        record_audit(
            action="OPS_VARIANT_DEACTIVATED",
            entity_type="ProductVariant",
            entity_id=variant.sku,
            actor=request.user,
        )
        return envelope_response({"id": str(variant.id), "sku": variant.sku, "isActive": False, "deleted": False}, request)


class OpsVariantBulkCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Matristen toplu varyant üret", request=OpsVariantBulkMatrixSerializer)
    @transaction.atomic
    def post(self, request: Request):
        from django.utils.text import slugify

        serializer = OpsVariantBulkMatrixSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        product = ProductModel.objects.select_for_update().filter(parent_sku=d["parentSku"].strip().upper()).first()
        if product is None:
            raise DomainError("Ana ürün modeli bulunamadı.", code="PRODUCT_NOT_FOUND", status_code=404)

        init_qty = d.get("initialStockQty", 0)
        if init_qty > 0:
            from apps.organizations.selectors import resolve_tenant_context

            ctx = resolve_tenant_context(request)
            if "inventory:manage" not in ctx.permissions:
                raise DomainError(
                    "Başlangıç stoğu girmek için 'inventory:manage' yetkisi gereklidir.",
                    code="FORBIDDEN_FIELD",
                    status_code=403,
                )

        color_map = {"Beyaz": "BYZ", "Beyaz Altın": "BYZ", "Sarı": "SRY", "Sarı Altın": "SRY", "Rose": "RSE", "Rose Altın": "RSE"}
        created_items: list[dict] = []
        skipped_count = 0
        default_wh = get_or_create_default_warehouse() if init_qty > 0 else None

        for purity in d["purities"]:
            p_clean = purity.strip()
            for color in d["colors"]:
                c_clean = color.strip()
                c_code = color_map.get(c_clean, (slugify(c_clean).replace("-", "").upper()[:3] or "STD"))
                for size in d["sizes"]:
                    exists = ProductVariant.objects.filter(
                        product=product,
                        purity_code=p_clean,
                        metal_color=c_clean,
                        size=size,
                        center_stone_carat=d["centerStoneCarat"],
                    ).exists()
                    if exists:
                        skipped_count += 1
                        continue
                    base_sku = f"{product.parent_sku}-{p_clean}-{c_code}-{size}".upper()
                    sku = base_sku
                    suffix = 2
                    while ProductVariant.objects.filter(sku__iexact=sku).exists():
                        sku = f"{base_sku}-{suffix}"
                        suffix += 1
                    try:
                        with transaction.atomic():
                            variant = ProductVariant.objects.create(
                                product=product,
                                sku=sku,
                                purity_code=p_clean,
                                metal_color=c_clean,
                                size=size,
                                center_stone_carat=d["centerStoneCarat"],
                                gross_weight_gram=d["grossWeightGram"],
                                stock_qty=0,
                                is_default=False,
                                is_active=True,
                            )
                    except IntegrityError:
                        skipped_count += 1
                        continue
                    if init_qty > 0 and default_wh is not None:
                        set_variant_warehouse_stock(
                            variant=variant,
                            warehouse=default_wh,
                            quantity=init_qty,
                            reference_no=f"MATRIX-{variant.sku}",
                            actor=request.user,
                        )
                    created_items.append(serialize_ops_variant(variant))

        record_audit(
            action="OPS_VARIANTS_BULK_CREATED",
            entity_type="ProductModel",
            entity_id=product.parent_sku,
            actor=request.user,
            metadata={"created": len(created_items), "skipped": skipped_count},
        )
        return envelope_response(
            {"createdCount": len(created_items), "skippedCount": skipped_count, "items": created_items},
            request,
            status=201,
        )



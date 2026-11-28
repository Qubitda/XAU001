from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.idempotency.mixins import IdempotentCreateMixin
from apps.catalog.models import ProductVariant
from apps.common.responses import (
    apply_safe_ordering,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from apps.organizations.selectors import resolve_active_branch, resolve_tenant_context
from config.exceptions import DomainError
from .models import StockMovement, Warehouse, WarehouseStock
from .services import record_manual_stock_movement, transfer_warehouse_stock


def serialize_ops_warehouse(wh: Warehouse) -> dict:
    return {
        "id": str(wh.id),
        "code": wh.code,
        "name": wh.name,
        "branchId": str(wh.branch_id) if wh.branch_id else None,
        "branchCode": wh.branch.code if wh.branch else None,
        "branchName": wh.branch.name if wh.branch else None,
        "organizationId": str(wh.branch.organization_id) if wh.branch_id else None,
        "isActive": wh.is_active,
        "createdAt": wh.created_at.isoformat(),
        "updatedAt": wh.updated_at.isoformat(),
    }


def serialize_ops_warehouse_stock(ws: WarehouseStock) -> dict:
    return {
        "id": str(ws.id),
        "warehouseId": str(ws.warehouse_id),
        "warehouseCode": ws.warehouse.code,
        "warehouseName": ws.warehouse.name,
        "variantId": str(ws.variant_id),
        "variantSku": ws.variant.sku,
        "parentSku": ws.variant.product.parent_sku,
        "productTitle": ws.variant.product.title,
        "purityCode": ws.variant.purity_code,
        "metalColor": ws.variant.metal_color,
        "size": ws.variant.size,
        "quantity": ws.quantity,
        "reservedQty": ws.reserved_qty,
        "availableQty": ws.available_qty,
        "ownerOrganizationId": str(ws.owner_organization_id) if ws.owner_organization_id else None,
        "controllerOrganizationId": (
            str(ws.controller_organization_id) if ws.controller_organization_id else None
        ),
        "sourceSupplierName": ws.source_supplier_name,
        "ownershipType": ws.ownership_type,
        "grossWeightGram": str(ws.gross_weight_gram) if ws.gross_weight_gram is not None else None,
        "certificateNumber": ws.certificate_number,
        "lotOrSerial": ws.lot_or_serial,
        "updatedAt": ws.updated_at.isoformat(),
    }


def serialize_ops_stock_movement(mv: StockMovement) -> dict:
    return {
        "id": str(mv.id),
        "productId": str(mv.product_id),
        "parentSku": mv.product.parent_sku,
        "variantId": str(mv.variant_id) if mv.variant_id else None,
        "variantSku": mv.variant.sku if mv.variant else None,
        "warehouseId": str(mv.warehouse_id) if mv.warehouse_id else None,
        "warehouseCode": mv.warehouse.code if mv.warehouse else None,
        "movementType": mv.movement_type,
        "quantityDelta": mv.quantity_delta,
        "referenceNo": mv.reference_no,
        "grossWeightGram": str(mv.gross_weight_gram) if mv.gross_weight_gram is not None else None,
        "purityCode": mv.purity_code,
        "certificateNumber": mv.certificate_number,
        "lotOrSerial": mv.lot_or_serial,
        "actorId": str(mv.actor_id) if mv.actor_id else None,
        "actorEmail": mv.actor.email if mv.actor else None,
        "createdAt": mv.created_at.isoformat(),
    }


class OpsWarehouseCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=120)
    branchId = serializers.UUIDField(required=False, allow_null=True)
    isActive = serializers.BooleanField(default=True)


class OpsWarehouseUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    branchId = serializers.UUIDField(required=False, allow_null=True)
    isActive = serializers.BooleanField(required=False)


class OpsStockMovementCreateSerializer(serializers.Serializer):
    variantId = serializers.UUIDField(required=False)
    variantSku = serializers.CharField(max_length=64, required=False, allow_blank=True)
    warehouseId = serializers.UUIDField(required=False)
    warehouseCode = serializers.CharField(max_length=32, required=False, allow_blank=True)
    movementType = serializers.ChoiceField(choices=[*StockMovement.MovementType.values, "SET"])
    quantity = serializers.IntegerField(min_value=0, max_value=100000)
    referenceNo = serializers.CharField(max_length=64)

    def validate(self, attrs):
        if attrs.get("movementType") != "SET" and attrs.get("quantity", 0) < 1:
            raise serializers.ValidationError({"quantity": "Bu hareket tipi için adet en az 1 olmalıdır."})
        if not attrs.get("variantId") and not attrs.get("variantSku"):
            raise serializers.ValidationError("variantId veya variantSku zorunludur.")
        if not attrs.get("warehouseId") and not attrs.get("warehouseCode"):
            raise serializers.ValidationError("warehouseId veya warehouseCode zorunludur.")
        return attrs


class OpsStockTransferSerializer(serializers.Serializer):
    variantId = serializers.UUIDField(required=False)
    variantSku = serializers.CharField(max_length=64, required=False, allow_blank=True)
    sourceWarehouseId = serializers.UUIDField()
    targetWarehouseId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=100000)
    referenceNo = serializers.CharField(max_length=64)

    def validate(self, attrs):
        if not attrs.get("variantId") and not attrs.get("variantSku"):
            raise serializers.ValidationError("variantId veya variantSku zorunludur.")
        return attrs


def _resolve_variant(variant_id=None, variant_sku=None) -> ProductVariant:
    qs = ProductVariant.objects.select_related("product")
    variant = qs.filter(id=variant_id).first() if variant_id else qs.filter(sku__iexact=str(variant_sku).strip()).first()
    if variant is None:
        raise DomainError("Ürün varyantı bulunamadı.", code="VARIANT_NOT_FOUND", status_code=404)
    return variant


def _resolve_warehouse(warehouse_id=None, warehouse_code=None) -> Warehouse:
    wh = (
        Warehouse.objects.filter(id=warehouse_id).first()
        if warehouse_id
        else Warehouse.objects.filter(code__iexact=str(warehouse_code).strip()).first()
    )
    if wh is None:
        raise DomainError("Depo bulunamadı.", code="WAREHOUSE_NOT_FOUND", status_code=404)
    return wh


class OpsWarehouseListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "inventory:manage"

    @extend_schema(tags=["OPS - Inventory"], summary="Depoları listele")
    def get(self, request: Request):
        qs = Warehouse.objects.select_related("branch")
        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        qs = apply_safe_ordering(qs, request, allowed_fields={"code": "code", "name": "name", "createdAt": "created_at"}, default="code")
        return paginated_envelope_response(qs, request, serialize_ops_warehouse)

    @extend_schema(tags=["OPS - Inventory"], summary="Yeni depo oluştur", request=OpsWarehouseCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsWarehouseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        code = d["code"].strip().upper()
        if Warehouse.objects.filter(code__iexact=code).exists():
            raise DomainError(f"Depo kodu zaten mevcut: {code}", code="DUPLICATE_WAREHOUSE_CODE", status_code=409)

        branch = None
        if d.get("branchId"):
            ctx = resolve_tenant_context(request)
            branch = resolve_active_branch(d["branchId"])
            if not ctx.is_ops:
                raise DomainError(
                    "Depo oluşturma yalnızca OPS yetkisi ile yapılabilir.",
                    code="OPS_REQUIRED",
                    status_code=403,
                )

        wh = Warehouse.objects.create(
            code=code,
            name=d["name"].strip(),
            branch=branch,
            is_active=d.get("isActive", True),
        )
        record_audit(
            action="OPS_WAREHOUSE_CREATED",
            entity_type="Warehouse",
            entity_id=str(wh.id),
            actor=request.user,
            metadata={"code": wh.code, "name": wh.name},
        )
        wh = Warehouse.objects.select_related("branch").get(id=wh.id)
        return envelope_response(serialize_ops_warehouse(wh), request, status=201)


class OpsWarehouseDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "inventory:manage"

    @extend_schema(tags=["OPS - Inventory"], summary="Depo detayını getir")
    def get(self, request: Request, warehouse_id: str):
        wh = Warehouse.objects.select_related("branch").filter(id=warehouse_id).first()
        if wh is None:
            raise DomainError("Depo bulunamadı.", code="WAREHOUSE_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_warehouse(wh), request)

    @extend_schema(tags=["OPS - Inventory"], summary="Depo bilgilerini güncelle", request=OpsWarehouseUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, warehouse_id: str):
        wh = Warehouse.objects.select_for_update().select_related("branch").filter(id=warehouse_id).first()
        if wh is None:
            raise DomainError("Depo bulunamadı.", code="WAREHOUSE_NOT_FOUND", status_code=404)
        serializer = OpsWarehouseUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "name" in d:
            wh.name = d["name"].strip()
        if "branchId" in d:
            if d["branchId"] is None:
                wh.branch = None
            else:
                ctx = resolve_tenant_context(request)
                if not ctx.is_ops:
                    raise DomainError(
                        "Depo şube ataması yalnızca OPS yetkisi ile yapılabilir.",
                        code="OPS_REQUIRED",
                        status_code=403,
                    )
                wh.branch = resolve_active_branch(d["branchId"])
        if "isActive" in d:
            wh.is_active = d["isActive"]

        wh.save()
        record_audit(
            action="OPS_WAREHOUSE_UPDATED",
            entity_type="Warehouse",
            entity_id=str(wh.id),
            actor=request.user,
            metadata={"code": wh.code, "is_active": wh.is_active},
        )
        return envelope_response(serialize_ops_warehouse(wh), request)


class OpsWarehouseStockListView(APIView):
    """Read-only Warehouse × Variant stock balances (mutations go exclusively through stock movements)."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "inventory:manage"

    @extend_schema(tags=["OPS - Inventory"], summary="Depo bazlı varyant stok bakiyelerini listele")
    def get(self, request: Request):
        qs = WarehouseStock.objects.select_related("warehouse", "variant", "variant__product")
        warehouse_id = (request.query_params.get("warehouseId") or "").strip()
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        variant_id = (request.query_params.get("variantId") or "").strip()
        if variant_id:
            qs = qs.filter(variant_id=variant_id)
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(variant__product__parent_sku=parent_sku)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(variant__sku__icontains=q)
                | Q(variant__product__parent_sku__icontains=q)
                | Q(warehouse__code__icontains=q)
                | Q(warehouse__name__icontains=q)
            )
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"quantity": "quantity", "reservedQty": "reserved_qty", "updatedAt": "updated_at"},
            default="-updated_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_warehouse_stock)


class OpsWarehouseStockDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "inventory:manage"

    @extend_schema(tags=["OPS - Inventory"], summary="Depo stok bakiye detayını getir")
    def get(self, request: Request, stock_id: str):
        ws = WarehouseStock.objects.select_related("warehouse", "variant", "variant__product").filter(id=stock_id).first()
        if ws is None:
            raise DomainError("Depo stok kaydı bulunamadı.", code="STOCK_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_warehouse_stock(ws), request)


class OpsStockMovementListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "inventory:manage"

    @extend_schema(tags=["OPS - Inventory"], summary="Stok hareket defterini listele")
    def get(self, request: Request):
        qs = StockMovement.objects.select_related("product", "variant", "warehouse", "actor")
        warehouse_id = (request.query_params.get("warehouseId") or "").strip()
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        variant_id = (request.query_params.get("variantId") or "").strip()
        if variant_id:
            qs = qs.filter(variant_id=variant_id)
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(product__parent_sku=parent_sku)
        movement_type = (request.query_params.get("movementType") or "").strip().upper()
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(reference_no__icontains=q)
                | Q(product__parent_sku__icontains=q)
                | Q(variant__sku__icontains=q)
            )
        qs = apply_safe_ordering(qs, request, allowed_fields={"createdAt": "created_at", "quantityDelta": "quantity_delta"}, default="-created_at")
        return paginated_envelope_response(qs, request, serialize_ops_stock_movement)

    @extend_schema(tags=["OPS - Inventory"], summary="Yeni stok hareketi (INBOUND / SHIP / RESERVE / RELEASE) kaydet", request=OpsStockMovementCreateSerializer)
    def post(self, request: Request):
        serializer = OpsStockMovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        variant = _resolve_variant(d.get("variantId"), d.get("variantSku"))
        warehouse = _resolve_warehouse(d.get("warehouseId"), d.get("warehouseCode"))
        movement = record_manual_stock_movement(
            variant=variant,
            warehouse=warehouse,
            movement_type=d["movementType"],
            quantity=d["quantity"],
            reference_no=d["referenceNo"],
            actor=request.user,
        )
        movement = StockMovement.objects.select_related("product", "variant", "warehouse", "actor").get(id=movement.id)
        return envelope_response(serialize_ops_stock_movement(movement), request, status=201)


class OpsStockTransferView(IdempotentCreateMixin, APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "inventory:manage"

    @extend_schema(tags=["OPS - Inventory"], summary="Depolar arası atomik stok transferi gerçekleştir", request=OpsStockTransferSerializer)
    def post(self, request: Request):
        serializer = OpsStockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        variant = _resolve_variant(d.get("variantId"), d.get("variantSku"))
        src = _resolve_warehouse(warehouse_id=d["sourceWarehouseId"])
        dst = _resolve_warehouse(warehouse_id=d["targetWarehouseId"])

        out_mv, in_mv = transfer_warehouse_stock(
            variant=variant,
            source_warehouse=src,
            target_warehouse=dst,
            quantity=d["quantity"],
            reference_no=d["referenceNo"],
            actor=request.user,
        )
        out_mv = StockMovement.objects.select_related("product", "variant", "warehouse", "actor").get(id=out_mv.id)
        in_mv = StockMovement.objects.select_related("product", "variant", "warehouse", "actor").get(id=in_mv.id)
        return envelope_response(
            {
                "outboundMovement": serialize_ops_stock_movement(out_mv),
                "inboundMovement": serialize_ops_stock_movement(in_mv),
            },
            request,
            status=201,
        )

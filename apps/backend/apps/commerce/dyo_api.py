from decimal import Decimal

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from rest_framework.permissions import IsAuthenticated

from apps.api_keys.permissions import HasApiScopeRead, HasApiScopeWrite
from apps.authorization.permissions import IsB2bOrganizationMember
from apps.catalog.api import serialize_b2b_product, serialize_storefront_product
from apps.catalog.models import ProductModel
from apps.catalog.product_details import serialize_loose_stone_detail
from apps.common.responses import envelope_response
from apps.market.services import get_current_rate_snapshot
from apps.pricing.models import PricingRecipe
from config.exceptions import DomainError

from .dyo import (
    calculate_dyo_bundle,
    compatible_stones_queryset,
    create_dyo_bundle,
    extend_bundle_lock,
    get_mounting_detail,
    public_dyo_pricing,
    serialize_bundle,
    validate_mounting_stone_pair,
)
from .models import CustomBundle


class DyoBundleCreateSerializer(serializers.Serializer):
    mountingSku = serializers.CharField(max_length=32)
    stoneSku = serializers.CharField(max_length=32)
    addToCart = serializers.BooleanField(required=False, default=True)


class DyoValidateSerializer(serializers.Serializer):
    mountingSku = serializers.CharField(max_length=32)
    stoneSku = serializers.CharField(max_length=32)


def _mounting_by_sku(sku: str) -> ProductModel:
    product = ProductModel.objects.filter(parent_sku__iexact=sku.strip()).first()
    if product is None:
        raise DomainError(f"Montür bulunamadı: {sku}", code="PRODUCT_NOT_FOUND", status_code=404)
    get_mounting_detail(product)
    return product


class CompatibleStonesView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeRead]
    audience = "b2c"

    def get(self, request: Request):
        mounting_sku = (request.query_params.get("mountingSku") or "").strip()
        if not mounting_sku:
            raise DomainError("mountingSku zorunlu.", code="VALIDATION_ERROR", status_code=400)
        mounting = _mounting_by_sku(mounting_sku)
        color = (request.query_params.get("color") or "").strip()
        clarity = (request.query_params.get("clarity") or "").strip()
        try:
            limit = min(int(request.query_params.get("limit") or 50), 200)
        except ValueError:
            limit = 50

        qs = compatible_stones_queryset(
            mounting, exclude_user_id=request.user.id, color=color, clarity=clarity
        )[:limit]
        rates = get_current_rate_snapshot()
        items = []
        for stone_detail in qs:
            product = stone_detail.product
            recipe = (
                PricingRecipe.objects.filter(product=product, status=PricingRecipe.Status.PUBLISHED)
                .first()
            )
            if self.audience == "b2b":
                payload = serialize_b2b_product(product, recipe, rates)
            else:
                payload = serialize_storefront_product(product, recipe, rates)
            payload["looseStoneDetail"] = serialize_loose_stone_detail(stone_detail, for_ops=False)
            payload["compatible"] = True
            items.append(payload)
        mount_detail = get_mounting_detail(mounting)
        return envelope_response(
            {
                "mountingSku": mounting.parent_sku,
                "filters": {
                    "compatibleShapes": mount_detail.compatible_shapes,
                    "minCarat": float(mount_detail.min_carat) if mount_detail.min_carat is not None else None,
                    "maxCarat": float(mount_detail.max_carat) if mount_detail.max_carat is not None else None,
                },
                "items": items,
                "count": len(items),
            },
            request,
        )


class B2bCompatibleStonesView(CompatibleStonesView):
    permission_classes = [IsB2bOrganizationMember]
    audience = "b2b"


class DyoValidateView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeWrite]

    def post(self, request: Request):
        ser = DyoValidateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        mounting = _mounting_by_sku(d["mountingSku"])
        stone = ProductModel.objects.filter(parent_sku__iexact=d["stoneSku"]).first()
        if stone is None:
            raise DomainError(f"Taş bulunamadı: {d['stoneSku']}", code="PRODUCT_NOT_FOUND", status_code=404)
        validate_mounting_stone_pair(mounting, stone)
        pricing = calculate_dyo_bundle(mounting=mounting, stone=stone)
        return envelope_response(
            {
                "compatible": True,
                "mountingSku": mounting.parent_sku,
                "stoneSku": stone.parent_sku,
                "pricing": public_dyo_pricing(pricing),
            },
            request,
        )


class DyoBundleCreateView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeWrite]
    audience = "B2C"

    def post(self, request: Request):
        ser = DyoBundleCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        bundle, pricing = create_dyo_bundle(
            user=request.user,
            mounting_sku=d["mountingSku"],
            stone_sku=d["stoneSku"],
            audience=self.audience,
            add_to_cart=d.get("addToCart", True),
        )
        return envelope_response(serialize_bundle(bundle, pricing), request, status=201)


class B2bDyoBundleCreateView(DyoBundleCreateView):
    permission_classes = [IsB2bOrganizationMember]
    audience = "B2B"


class DyoBundleDetailView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeRead]

    def get(self, request: Request, bundle_id):
        bundle = CustomBundle.objects.filter(id=bundle_id, user=request.user).select_related(
            "mounting_product", "stone_product"
        ).first()
        if bundle is None:
            raise DomainError("Bundle bulunamadı.", code="BUNDLE_NOT_FOUND", status_code=404)
        pricing = calculate_dyo_bundle(
            mounting=bundle.mounting_product,
            stone=bundle.stone_product,
            setting_labor_usd=bundle.setting_labor_usd,
        )
        return envelope_response(serialize_bundle(bundle, pricing), request)

    def post(self, request: Request, bundle_id):
        """Extend soft-lock TTL (checkout start)."""
        bundle = CustomBundle.objects.filter(id=bundle_id, user=request.user).first()
        if bundle is None:
            raise DomainError("Bundle bulunamadı.", code="BUNDLE_NOT_FOUND", status_code=404)
        if bundle.status not in (CustomBundle.Status.DRAFT, CustomBundle.Status.IN_CART):
            raise DomainError("Bundle uzatılamaz.", code="BUNDLE_NOT_EXTENDABLE", status_code=400)
        extend_bundle_lock(bundle=bundle)
        return envelope_response(serialize_bundle(bundle), request)

    def delete(self, request: Request, bundle_id):
        from .dyo import release_stone_soft_lock
        from .models import B2bDraftLine, B2cCartItem

        bundle = CustomBundle.objects.filter(id=bundle_id, user=request.user).first()
        if bundle is None:
            raise DomainError("Bundle bulunamadı.", code="BUNDLE_NOT_FOUND", status_code=404)
        B2cCartItem.objects.filter(bundle=bundle).delete()
        B2bDraftLine.objects.filter(bundle=bundle).delete()
        release_stone_soft_lock(stone=bundle.stone_product, user=request.user)
        bundle.status = CustomBundle.Status.CANCELLED
        bundle.save(update_fields=["status", "updated_at"])
        return envelope_response({"id": str(bundle.id), "deleted": True}, request)

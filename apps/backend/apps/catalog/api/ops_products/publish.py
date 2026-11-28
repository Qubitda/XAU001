"""OPS product endpoints."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.catalog.models import ProductModel, ProductVariant, StoneLine
from apps.catalog.product_details import dual_write_product_details
from apps.catalog.product_kinds import kind_to_product_type_label, normalize_product_kind
from apps.catalog.services import sync_default_variant_center_carat, validate_publishable
from apps.common.responses import apply_safe_ordering, envelope_response, paginated_envelope_response
from apps.inventory.services import get_or_create_default_warehouse, set_variant_warehouse_stock
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_active_organization, resolve_tenant_context
from apps.pricing.models import PricingRecipe
from apps.pricing.services import publish_recipe
from config.exceptions import DomainError
from ..common import (
    _apply_kind_fields,
    _detail_overrides_from_payload,
    _normalize_sales_channels,
    _parse_decimal,
    _parse_int,
    _sync_product_media,
)
from ..ops_serializers import OpsProductSerializer
from ..recipe_sync import _sync_recipe_from_ledger
from ..serializers import _apply_filters, _products_queryset, serialize_ops_product


class OpsProductPublishView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:publish"

    @transaction.atomic
    def post(self, request: Request, parent_sku: str):
        product = ProductModel.objects.select_for_update().filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        missing = validate_publishable(product)
        if missing:
            return envelope_response(
                {"code": "NOT_PUBLISHABLE", "message": "Ürün yayın koşulları sağlanmadı.", "missing": missing},
                request,
                status=422,
            )
        prev = product.catalog_status
        product.catalog_status = ProductModel.CatalogStatus.ACTIVE
        product.save(update_fields=["catalog_status", "updated_at"])
        record_audit(
            action="PRODUCT_PUBLISHED",
            entity_type="ProductModel",
            entity_id=parent_sku,
            actor=request.user,
            metadata={"changed": {"catalogStatus": {"from": prev, "to": "ACTIVE"}}},
        )
        return envelope_response({"parentSku": parent_sku, "catalogStatus": product.catalog_status}, request)


class OpsProductUnpublishView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:publish"

    @extend_schema(tags=["OPS - Catalog"], summary="Ürünü yayından kaldır (DRAFT)")
    @transaction.atomic
    def post(self, request: Request, parent_sku: str):
        product = ProductModel.objects.select_for_update().filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        prev = product.catalog_status
        product.catalog_status = ProductModel.CatalogStatus.DRAFT
        product.save(update_fields=["catalog_status", "updated_at"])
        record_audit(
            action="PRODUCT_UNPUBLISHED",
            entity_type="ProductModel",
            entity_id=parent_sku,
            actor=request.user,
            metadata={"changed": {"catalogStatus": {"from": prev, "to": "DRAFT"}}},
        )
        return envelope_response({"parentSku": parent_sku, "catalogStatus": product.catalog_status}, request)


class OpsProductRecipePublishView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:edit"

    @transaction.atomic
    def post(self, request: Request, parent_sku: str):
        product = ProductModel.objects.select_for_update().filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        draft = (
            PricingRecipe.objects.filter(product=product, status=PricingRecipe.Status.DRAFT)
            .order_by("-version")
            .first()
        )
        if draft is None:
            raise DomainError("Yayınlanacak DRAFT fiyat reçetesi bulunamadı.", code="DRAFT_RECIPE_NOT_FOUND", status_code=404)
        published, _ = publish_recipe(draft, actor=request.user)
        record_audit(
            action="PRODUCT_RECIPE_PUBLISHED",
            entity_type="PricingRecipe",
            entity_id=str(published.id),
            actor=request.user,
            metadata={"parentSku": parent_sku, "version": published.version},
        )
        return envelope_response(
            {"parentSku": parent_sku, "recipeId": str(published.id), "version": published.version, "status": published.status},
            request,
        )



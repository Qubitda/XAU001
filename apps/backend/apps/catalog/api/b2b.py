"""B2B dealer catalog product endpoints."""
from django.db.models import Exists, OuterRef
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import IsB2bOrganizationMember
from apps.common.responses import apply_safe_ordering, envelope_response, paginated_envelope_response
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_tenant_context, scope_queryset_to_organization
from apps.pricing.models import PricingRecipe
from config.exceptions import DomainError
from apps.catalog.models import ProductModel
from .serializers import (
    _apply_filters,
    _channel_filter,
    _products_queryset,
    serialize_b2b_product,
)

CATALOG_ORDER_FIELDS = {"createdAt": "created_at", "title": "title", "parentSku": "parent_sku"}


class B2bProductListView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request):
        ctx = resolve_tenant_context(request, require_organization=True)
        rates = get_current_rate_snapshot()
        channel = "B2B_API" if getattr(request, "api_key", None) is not None else "B2B"
        has_published = Exists(
            PricingRecipe.objects.filter(product=OuterRef("pk"), status=PricingRecipe.Status.PUBLISHED)
        )
        # B2B sees central platform catalog + own organization's private catalog (ACTIVE + channel)
        qs = scope_queryset_to_organization(
            _products_queryset()
            .filter(catalog_status=ProductModel.CatalogStatus.ACTIVE)
            .filter(has_published),
            ctx,
            org_field="owner_organization",
            include_shared=True,
        )
        qs = _channel_filter(qs, channel)
        qs = _apply_filters(qs, request)
        qs = apply_safe_ordering(qs, request, allowed_fields=CATALOG_ORDER_FIELDS, default="-created_at")
        return paginated_envelope_response(
            qs,
            request,
            lambda p: serialize_b2b_product(p, p.published_recipes[0], rates),
            default_page_size=24,
            max_page_size=100,
        )


class B2bProductDetailView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request, parent_sku: str):
        ctx = resolve_tenant_context(request, require_organization=True)
        rates = get_current_rate_snapshot()
        channel = "B2B_API" if getattr(request, "api_key", None) is not None else "B2B"
        product = (
            _channel_filter(
                scope_queryset_to_organization(
                    _products_queryset().filter(
                        catalog_status=ProductModel.CatalogStatus.ACTIVE,
                        parent_sku=parent_sku,
                    ),
                    ctx,
                    org_field="owner_organization",
                    include_shared=True,
                ),
                channel,
            )
            .first()
        )
        if product is None or not product.published_recipes:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        recipe = product.published_recipes[0]
        return envelope_response(serialize_b2b_product(product, recipe, rates), request)

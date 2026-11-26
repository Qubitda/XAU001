"""B2B dealer catalog product endpoints."""
from django.db.models import Q
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import IsB2bOrganizationMember
from apps.common.responses import envelope_response
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError
from apps.catalog.models import ProductModel
from .serializers import (
    _apply_filters,
    _products_queryset,
    serialize_b2b_product,
)

class B2bProductListView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request):
        ctx = resolve_tenant_context(request, require_organization=True)
        rates = get_current_rate_snapshot()
        # B2B sees central platform catalog + own organization's private catalog (ACTIVE only)
        qs = _products_queryset().filter(
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
        ).filter(Q(owner_organization__isnull=True) | Q(owner_organization=ctx.organization))
        qs = _apply_filters(qs, request)
        payload = [
            serialize_b2b_product(p, p.published_recipes[0] if p.published_recipes else None, rates)
            for p in qs
            if p.published_recipes
        ]
        return envelope_response(payload, request)


class B2bProductDetailView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request, parent_sku: str):
        ctx = resolve_tenant_context(request, require_organization=True)
        rates = get_current_rate_snapshot()
        product = (
            _products_queryset()
            .filter(
                catalog_status=ProductModel.CatalogStatus.ACTIVE,
            )
            .filter(Q(owner_organization__isnull=True) | Q(owner_organization=ctx.organization))
            .filter(parent_sku=parent_sku)
            .first()
        )
        if product is None or not product.published_recipes:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        recipe = product.published_recipes[0]
        return envelope_response(serialize_b2b_product(product, recipe, rates), request)

"""Storefront (B2C) product and favorites endpoints."""
from django.db.models import Q
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.api_keys.permissions import HasApiScopeRead, HasApiScopeWrite
from apps.common.responses import envelope_response
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError
from apps.catalog.models import Favorite, ProductModel
from .serializers import (
    _apply_filters,
    _products_queryset,
    serialize_storefront_product,
)

class StorefrontProductListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request):
        rates = get_current_rate_snapshot()
        # Storefront shows central platform catalog only — ACTIVE + published recipe required
        qs = _apply_filters(
            _products_queryset().filter(
                owner_organization__isnull=True,
                catalog_status=ProductModel.CatalogStatus.ACTIVE,
            ),
            request,
        )
        payload = [
            serialize_storefront_product(p, p.published_recipes[0] if p.published_recipes else None, rates)
            for p in qs
            if p.published_recipes
        ]
        return envelope_response(payload, request)


class StorefrontProductDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, parent_sku: str):
        rates = get_current_rate_snapshot()
        product = (
            _products_queryset()
            .filter(
                owner_organization__isnull=True,
                catalog_status=ProductModel.CatalogStatus.ACTIVE,
                parent_sku=parent_sku,
            )
            .first()
        )
        if product is None or not product.published_recipes:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        recipe = product.published_recipes[0]
        return envelope_response(serialize_storefront_product(product, recipe, rates), request)

class FavoriteListView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeRead]

    def get(self, request: Request):
        skus = list(
            Favorite.objects.filter(user=request.user)
            .select_related("product")
            .values_list("product__parent_sku", flat=True)
        )
        return envelope_response(skus, request)


class FavoriteToggleView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeWrite]

    def post(self, request: Request):
        sku = str(request.data.get("parentSku", "")).strip()
        ctx = resolve_tenant_context(request)
        qs = ProductModel.objects.filter(
            parent_sku=sku,
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
        )
        if not ctx.is_ops:
            if ctx.organization is not None:
                qs = qs.filter(Q(owner_organization__isnull=True) | Q(owner_organization=ctx.organization))
            else:
                qs = qs.filter(owner_organization__isnull=True)
        product = qs.first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        fav, created = Favorite.objects.get_or_create(user=request.user, product=product)
        if not created:
            fav.delete()
        skus = list(
            Favorite.objects.filter(user=request.user).values_list("product__parent_sku", flat=True)
        )
        return envelope_response(skus, request)

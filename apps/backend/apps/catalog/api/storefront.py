"""Storefront (B2C) product and favorites endpoints."""
import hashlib

from django.core.cache import cache
from django.db.models import Exists, OuterRef, Q
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_keys.permissions import HasApiScopeRead, HasApiScopeWrite
from apps.common.responses import apply_safe_ordering, envelope_response, paginated_envelope_response
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_tenant_context, scope_queryset_to_organization
from apps.pricing.models import PricingRecipe
from config.exceptions import DomainError
from apps.catalog.models import Favorite, ProductModel
from .serializers import (
    _apply_filters,
    _channel_filter,
    _products_queryset,
    serialize_storefront_product,
)

CATALOG_ORDER_FIELDS = {"createdAt": "created_at", "title": "title", "parentSku": "parent_sku"}


class StorefrontProductListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request):
        rates = get_current_rate_snapshot()
        is_anon = not (request.user and request.user.is_authenticated)
        cache_key = ""
        if is_anon:
            q_hash = hashlib.sha256(request.META.get("QUERY_STRING", "").encode("utf-8")).hexdigest()[:24]
            cache_key = f"sf_products:{rates.snapshot_code}:B2C_API:{q_hash}"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

        has_published = Exists(
            PricingRecipe.objects.filter(product=OuterRef("pk"), status=PricingRecipe.Status.PUBLISHED)
        )
        qs = _apply_filters(
            _channel_filter(
                _products_queryset()
                .filter(
                    owner_organization__isnull=True,
                    catalog_status=ProductModel.CatalogStatus.ACTIVE,
                )
                .filter(has_published),
                "B2C_API",
            ),
            request,
        )
        qs = apply_safe_ordering(qs, request, allowed_fields=CATALOG_ORDER_FIELDS, default="-created_at")
        resp = paginated_envelope_response(
            qs,
            request,
            lambda p: serialize_storefront_product(p, p.published_recipes[0], rates),
            default_page_size=24,
            max_page_size=100,
        )
        if is_anon and cache_key:
            cache.set(cache_key, resp.data, timeout=60)
        return resp


class StorefrontProductDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, parent_sku: str):
        rates = get_current_rate_snapshot()
        product = (
            _channel_filter(
                _products_queryset().filter(
                    owner_organization__isnull=True,
                    catalog_status=ProductModel.CatalogStatus.ACTIVE,
                    parent_sku=parent_sku,
                ),
                "B2C_API",
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
        qs = scope_queryset_to_organization(qs, ctx, org_field="owner_organization", include_shared=True)
        if not ctx.is_ops:
            ch = (
                ("B2B_API" if getattr(request, "api_key", None) is not None else "B2B")
                if ctx.organization is not None
                else "B2C_API"
            )
            qs = _channel_filter(qs, ch)
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

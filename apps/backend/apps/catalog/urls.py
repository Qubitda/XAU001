"""Catalog HTTP routes (storefront, B2B, OPS products/variants/media)."""

from django.urls import path

from apps.catalog.api import (
    B2bProductDetailView,
    B2bProductListView,
    FavoriteListView,
    FavoriteToggleView,
    OpsProductDetailView,
    OpsProductListCreateView,
    StorefrontProductDetailView,
    StorefrontProductListView,
)
from apps.catalog.api.ops_variants import (
    OpsCategorySummaryView,
    OpsProductMediaDetailView,
    OpsProductMediaListCreateView,
    OpsStoneLineDetailView,
    OpsStoneLineListCreateView,
    OpsVariantDetailView,
    OpsVariantListCreateView,
)

urlpatterns = [
    path("api/v1/storefront/products", StorefrontProductListView.as_view(), name="storefront-products"),
    path(
        "api/v1/storefront/products/<str:parent_sku>",
        StorefrontProductDetailView.as_view(),
        name="storefront-product-detail",
    ),
    path("api/v1/storefront/favorites", FavoriteListView.as_view(), name="storefront-favorites"),
    path(
        "api/v1/storefront/favorites/toggle",
        FavoriteToggleView.as_view(),
        name="storefront-favorites-toggle",
    ),
    path("api/v1/b2b/products", B2bProductListView.as_view(), name="b2b-products"),
    path(
        "api/v1/b2b/products/<str:parent_sku>",
        B2bProductDetailView.as_view(),
        name="b2b-product-detail",
    ),
    path("api/v1/ops/products", OpsProductListCreateView.as_view(), name="ops-products"),
    path(
        "api/v1/ops/products/<str:parent_sku>",
        OpsProductDetailView.as_view(),
        name="ops-product-detail",
    ),
    path("api/v1/ops/variants", OpsVariantListCreateView.as_view(), name="ops-variants"),
    path(
        "api/v1/ops/variants/<uuid:variant_id>",
        OpsVariantDetailView.as_view(),
        name="ops-variant-detail",
    ),
    path("api/v1/ops/stone-lines", OpsStoneLineListCreateView.as_view(), name="ops-stone-lines"),
    path(
        "api/v1/ops/stone-lines/<uuid:stone_id>",
        OpsStoneLineDetailView.as_view(),
        name="ops-stone-line-detail",
    ),
    path("api/v1/ops/media", OpsProductMediaListCreateView.as_view(), name="ops-media"),
    path(
        "api/v1/ops/media/<uuid:media_id>",
        OpsProductMediaDetailView.as_view(),
        name="ops-media-detail",
    ),
    path("api/v1/ops/categories", OpsCategorySummaryView.as_view(), name="ops-categories"),
]

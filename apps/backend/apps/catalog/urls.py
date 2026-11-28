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
from apps.catalog.api.ops_products import (
    OpsCatalogMediaUploadView,
    OpsProductPublishView,
    OpsProductRecipePublishView,
    OpsProductUnpublishView,
)
from apps.catalog.api.ops_variants import (
    OpsCategorySummaryView,
    OpsProductMediaDetailView,
    OpsProductMediaListCreateView,
    OpsStoneLineDetailView,
    OpsStoneLineListCreateView,
    OpsVariantBulkCreateView,
    OpsVariantDetailView,
    OpsVariantListCreateView,
)
from apps.catalog.api.supplier import (
    OpsProductOffersView,
    OpsSupplierOfferDecisionView,
    SupplierOfferDetailView,
    SupplierOfferListCreateView,
    SupplierProductListView,
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
    path(
        "api/v1/ops/products/<str:parent_sku>/publish",
        OpsProductPublishView.as_view(),
        name="ops-product-publish",
    ),
    path(
        "api/v1/ops/products/<str:parent_sku>/unpublish",
        OpsProductUnpublishView.as_view(),
        name="ops-product-unpublish",
    ),
    path(
        "api/v1/ops/products/<str:parent_sku>/recipe/publish",
        OpsProductRecipePublishView.as_view(),
        name="ops-product-recipe-publish",
    ),
    path("api/v1/ops/variants", OpsVariantListCreateView.as_view(), name="ops-variants"),
    path("api/v1/ops/variants/bulk", OpsVariantBulkCreateView.as_view(), name="ops-variants-bulk"),
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
    path("api/v1/ops/catalog/media-upload", OpsCatalogMediaUploadView.as_view(), name="ops-catalog-media-upload"),
    path(
        "api/v1/ops/media/<uuid:media_id>",
        OpsProductMediaDetailView.as_view(),
        name="ops-media-detail",
    ),
    path("api/v1/ops/categories", OpsCategorySummaryView.as_view(), name="ops-categories"),
    path("api/v1/supplier/products", SupplierProductListView.as_view(), name="supplier-products"),
    path("api/v1/supplier/offers", SupplierOfferListCreateView.as_view(), name="supplier-offers"),
    path(
        "api/v1/supplier/offers/<uuid:offer_id>",
        SupplierOfferDetailView.as_view(),
        name="supplier-offer-detail",
    ),
    path(
        "api/v1/ops/products/<str:parent_sku>/offers",
        OpsProductOffersView.as_view(),
        name="ops-product-offers",
    ),
    path(
        "api/v1/ops/offers/<uuid:offer_id>/decision",
        OpsSupplierOfferDecisionView.as_view(),
        name="ops-supplier-offer-decision",
    ),
]

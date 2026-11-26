"""OPS + public storefront routes for tanım grupları / seçenekleri."""

from django.urls import path

from apps.definitions.api import (
    OpsDefinitionItemDetailView,
    OpsDefinitionItemListCreateView,
    OpsDefinitionMediaUploadView,
    OpsDefinitionTableDetailView,
    OpsDefinitionTableListView,
    OpsSalesChannelsView,
)
from apps.definitions.storefront_api import StorefrontDefinitionsView

urlpatterns = [
    path(
        "api/v1/storefront/definitions",
        StorefrontDefinitionsView.as_view(),
        name="storefront-definitions",
    ),
    path("api/v1/ops/definitions", OpsDefinitionTableListView.as_view(), name="ops-definitions"),
    path(
        "api/v1/ops/definitions/sales-channels",
        OpsSalesChannelsView.as_view(),
        name="ops-sales-channels",
    ),
    path(
        "api/v1/ops/definitions/media",
        OpsDefinitionMediaUploadView.as_view(),
        name="ops-definition-media",
    ),
    path(
        "api/v1/ops/definitions/<str:table_code>",
        OpsDefinitionTableDetailView.as_view(),
        name="ops-definition-table",
    ),
    path(
        "api/v1/ops/definitions/<str:table_code>/items",
        OpsDefinitionItemListCreateView.as_view(),
        name="ops-definition-items",
    ),
    path(
        "api/v1/ops/definition-items/<uuid:item_id>",
        OpsDefinitionItemDetailView.as_view(),
        name="ops-definition-item-detail",
    ),
]

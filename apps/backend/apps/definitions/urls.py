"""OPS routes for tanım grupları / seçenekleri (DefinitionTable / DefinitionItem)."""

from django.urls import path

from apps.definitions.api import (
    OpsDefinitionItemDetailView,
    OpsDefinitionItemListCreateView,
    OpsDefinitionTableDetailView,
    OpsDefinitionTableListView,
    OpsSalesChannelsView,
)

urlpatterns = [
    path("api/v1/ops/definitions", OpsDefinitionTableListView.as_view(), name="ops-definitions"),
    path(
        "api/v1/ops/definitions/sales-channels",
        OpsSalesChannelsView.as_view(),
        name="ops-sales-channels",
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

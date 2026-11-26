"""Inventory OPS routes (warehouses, stocks, movements, transfers)."""

from django.urls import path

from apps.inventory.api import (
    OpsStockMovementListCreateView,
    OpsStockTransferView,
    OpsWarehouseDetailView,
    OpsWarehouseListCreateView,
    OpsWarehouseStockDetailView,
    OpsWarehouseStockListView,
)

urlpatterns = [
    path("api/v1/ops/warehouses", OpsWarehouseListCreateView.as_view(), name="ops-warehouses"),
    path(
        "api/v1/ops/warehouses/<uuid:warehouse_id>",
        OpsWarehouseDetailView.as_view(),
        name="ops-warehouse-detail",
    ),
    path("api/v1/ops/stocks", OpsWarehouseStockListView.as_view(), name="ops-stocks"),
    path(
        "api/v1/ops/stocks/<uuid:stock_id>",
        OpsWarehouseStockDetailView.as_view(),
        name="ops-stock-detail",
    ),
    path(
        "api/v1/ops/stock-movements",
        OpsStockMovementListCreateView.as_view(),
        name="ops-stock-movements",
    ),
    path("api/v1/ops/stock-transfers", OpsStockTransferView.as_view(), name="ops-stock-transfers"),
]

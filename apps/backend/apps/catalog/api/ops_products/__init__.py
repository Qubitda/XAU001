"""Backward-compatible exports for split OPS product views."""
from .detail import OpsProductDetailView
from .list_create import OpsProductListCreateView
from .media import OpsCatalogMediaUploadView
from .permissions import FIELD_PERMISSIONS, _enforce_field_permissions
from .publish import OpsProductPublishView, OpsProductRecipePublishView, OpsProductUnpublishView

__all__ = [
    "FIELD_PERMISSIONS",
    "_enforce_field_permissions",
    "OpsCatalogMediaUploadView",
    "OpsProductDetailView",
    "OpsProductListCreateView",
    "OpsProductPublishView",
    "OpsProductRecipePublishView",
    "OpsProductUnpublishView",
]

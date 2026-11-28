"""OPS catalog variant, stone-line, media, and category endpoints."""
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.catalog.api.ops_serializers import _validate_https_url
from apps.catalog.models import ProductMedia, ProductModel, ProductVariant, StoneLine
from apps.catalog.services import sync_default_variant_center_carat
from apps.common.responses import (
    CARAT_Q,
    GRAM_Q,
    apply_safe_ordering,
    dec_str,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from apps.inventory.services import (
    get_or_create_default_warehouse,
    set_variant_warehouse_stock,
    sync_variant_and_product_stock,
)
from config.exceptions import DomainError

class OpsCategorySummaryView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"

    @extend_schema(tags=["OPS - Catalog"], summary="Katalog kategori, alt kategori ve koleksiyon özetini getir")
    def get(self, request: Request):
        categories = list(
            ProductModel.objects.values("category")
            .annotate(productCount=Count("id"))
            .order_by("category")
        )
        sub_categories = list(
            ProductModel.objects.exclude(sub_category="")
            .values("category", "sub_category")
            .annotate(productCount=Count("id"))
            .order_by("category", "sub_category")
        )
        collections = list(
            ProductModel.objects.values("collection")
            .annotate(productCount=Count("id"))
            .order_by("collection")
        )
        return envelope_response(
            {
                "categories": categories,
                "subCategories": [
                    {
                        "category": row["category"],
                        "subCategory": row["sub_category"],
                        "productCount": row["productCount"],
                    }
                    for row in sub_categories
                ],
                "collections": collections,
            },
            request,
        )

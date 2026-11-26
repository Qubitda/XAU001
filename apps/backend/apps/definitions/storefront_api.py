"""Public storefront reads for definition tables used by B2C/B2B nav & filters."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.common.responses import envelope_response
from apps.definitions.serialize import serialize_definitions_bundle
from apps.definitions.services import list_definition_tables

# Tables exposed without auth. Keep this list tight — storefront only needs nav/filter SSOT.
STOREFRONT_PUBLIC_TABLE_CODES: frozenset[str] = frozenset(
    {
        "kategori",
        "alt_kategori",
        "metal_rengi",
    }
)


class StorefrontDefinitionsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Storefront - Definitions"],
        summary="Storefront tanım grupları (kategori / renk)",
    )
    def get(self, request: Request):
        raw = (request.query_params.get("tables") or "").strip()
        requested = {c.strip() for c in raw.split(",") if c.strip()} if raw else set()
        allowed = (
            requested & STOREFRONT_PUBLIC_TABLE_CODES
            if requested
            else set(STOREFRONT_PUBLIC_TABLE_CODES)
        )

        qs = [
            t
            for t in list_definition_tables(include_items=True)
            if t.code in allowed and t.is_active
        ]

        # Public payload: active items only (hide inactive OPS drafts).
        for table in qs:
            active_items = [i for i in table.items.all() if i.is_active]
            # Attach filtered list onto the instance for serialize_table(items.all()).
            table._prefetched_objects_cache = getattr(table, "_prefetched_objects_cache", {})
            table._prefetched_objects_cache["items"] = active_items  # type: ignore[attr-defined]

        bundle = serialize_definitions_bundle(qs, include_items=True)
        return envelope_response(bundle, request)

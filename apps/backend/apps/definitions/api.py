"""OPS HTTP layer for definition groups and options — thin views over services."""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.storage import default_storage
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from apps.definitions.sales_channels import serialize_sales_channels
from apps.definitions.serialize import serialize_definitions_bundle
from apps.definitions.serializers import DefinitionItemPatchSerializer, DefinitionItemWriteSerializer
from apps.definitions.services import (
    create_definition_item,
    deactivate_definition_item,
    delete_definition_item,
    get_definition_item,
    get_definition_table,
    list_definition_tables,
    list_table_items,
    seed_definition_tables,
    serialize_item,
    serialize_table,
    update_definition_item,
)
from config.exceptions import DomainError

_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class OpsDefinitionTableListView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "catalog:read",
        "POST": "catalog:write",
    }

    @extend_schema(tags=["OPS - Tanımlar"], summary="Tanım gruplarını listele")
    def get(self, request: Request):
        include_items = request.query_params.get("includeItems", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        qs = list(list_definition_tables(include_items=include_items))
        bundle = serialize_definitions_bundle(qs, include_items=include_items)
        return envelope_response(
            {
                **bundle,
                "salesChannels": serialize_sales_channels(),
            },
            request,
        )

    @extend_schema(tags=["OPS - Tanımlar"], summary="Sistem tanım seed'ini yükle/yenile")
    def post(self, request: Request):
        reset = bool(request.data.get("resetSystemItems")) if isinstance(request.data, dict) else False
        result = seed_definition_tables(reset_system_items=reset)
        qs = list(list_definition_tables(include_items=True))
        bundle = serialize_definitions_bundle(qs, include_items=True)
        return envelope_response(
            {
                "seeded": result,
                **bundle,
                "salesChannels": serialize_sales_channels(),
            },
            request,
        )


class OpsDefinitionTableDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:read"

    @extend_schema(tags=["OPS - Tanımlar"], summary="Tek tanım grubu + seçenekler")
    def get(self, request: Request, table_code: str):
        table = get_definition_table(table_code, with_items=True)
        return envelope_response(serialize_table(table), request)


class OpsDefinitionItemListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "catalog:read",
        "POST": "catalog:write",
    }

    @extend_schema(tags=["OPS - Tanımlar"], summary="Tanım seçeneklerini listele")
    def get(self, request: Request, table_code: str):
        table = get_definition_table(table_code)
        active_raw = request.query_params.get("isActive")
        is_active = None
        if active_raw in ("true", "1"):
            is_active = True
        elif active_raw in ("false", "0"):
            is_active = False
        items = list_table_items(
            table,
            is_active=is_active,
            parent_id=(request.query_params.get("parentId") or "").strip(),
            parent_code=(request.query_params.get("parentCode") or "").strip(),
            parent_label=(request.query_params.get("parentLabel") or "").strip(),
        )
        return envelope_response([serialize_item(i) for i in items], request)

    @extend_schema(tags=["OPS - Tanımlar"], summary="Yeni tanım seçeneği ekle")
    def post(self, request: Request, table_code: str):
        table = get_definition_table(table_code)
        ser = DefinitionItemWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        item = create_definition_item(
            table,
            code=data["code"],
            label=data["label"],
            meta=data.get("meta") or {},
            sort_order=data.get("sortOrder", 100),
            is_active=data.get("isActive", True),
            parent_ids=data.get("parentIds") or [],
        )
        return envelope_response(serialize_item(item), request, status=201)


class OpsDefinitionItemDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "PATCH": "catalog:write",
        "DELETE": "catalog:write",
    }

    @extend_schema(tags=["OPS - Tanımlar"], summary="Tanım seçeneğini güncelle")
    def patch(self, request: Request, item_id):
        item = get_definition_item(item_id)
        ser = DefinitionItemPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        item = update_definition_item(item, ser.validated_data)
        return envelope_response(serialize_item(item), request)

    @extend_schema(
        tags=["OPS - Tanımlar"],
        summary="Tanım seçeneğini sil (hard) veya pasifleştir (soft=1)",
    )
    def delete(self, request: Request, item_id):
        item = get_definition_item(item_id)
        soft = (request.query_params.get("soft") or "").lower() in ("1", "true", "yes")
        if soft:
            item = deactivate_definition_item(item)
            return envelope_response(serialize_item(item), request)
        delete_definition_item(item, hard=True)
        return envelope_response({"id": str(item_id), "deleted": True}, request)


class OpsSalesChannelsView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:read"

    @extend_schema(
        tags=["OPS - Tanımlar"],
        summary="Sabit ürün satış kanalları (B2B / B2B_API / B2C_API)",
    )
    def get(self, request: Request):
        return envelope_response({"salesChannels": serialize_sales_channels()}, request)


class OpsDefinitionMediaUploadView(APIView):
    """Upload an image for definition meta (e.g. kategori storefrontImageUrl)."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=["OPS - Tanımlar"], summary="Tanım görseli yükle")
    def post(self, request: Request):
        upload = request.FILES.get("file")
        if upload is None:
            raise DomainError("Dosya gerekli (file).", code="DEFINITION_MEDIA_REQUIRED", status_code=400)
        if upload.size and upload.size > _MAX_UPLOAD_BYTES:
            raise DomainError(
                "Görsel en fazla 8 MB olabilir.",
                code="DEFINITION_MEDIA_TOO_LARGE",
                status_code=400,
            )
        ext = PurePosixPath(upload.name or "").suffix.lower()
        if ext not in _ALLOWED_IMAGE_EXT:
            raise DomainError(
                "Desteklenen uzantılar: jpg, jpeg, png, webp, gif.",
                code="DEFINITION_MEDIA_TYPE",
                status_code=400,
            )
        filename = f"definitions/{uuid.uuid4().hex}{ext}"
        saved = default_storage.save(filename, upload)
        relative = f"{settings.MEDIA_URL.rstrip('/')}/{saved.lstrip('/')}"
        absolute = request.build_absolute_uri(relative)
        return envelope_response({"url": absolute, "path": relative}, request, status=201)

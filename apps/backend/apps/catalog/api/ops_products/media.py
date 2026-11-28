"""OPS catalog media upload endpoint."""
from pathlib import PurePosixPath
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from config.exceptions import DomainError

_CATALOG_UPLOAD_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_CATALOG_UPLOAD_MAX_VIDEO_BYTES = 25 * 1024 * 1024
_CATALOG_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_CATALOG_VIDEO_EXTS = {".mp4", ".webm", ".mov"}
_CATALOG_CERT_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


class OpsCatalogMediaUploadView(APIView):
    """Upload a product image, video, 360 asset, or certificate PDF for catalog media fields."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "catalog:write"
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=["OPS - Catalog"], summary="Katalog medya dosyası yükle")
    def post(self, request: Request):
        upload = request.FILES.get("file")
        if upload is None:
            raise DomainError("Dosya gerekli (file).", code="CATALOG_MEDIA_REQUIRED", status_code=400)

        kind = str(request.data.get("kind") or "any").strip().lower()
        ext = PurePosixPath(upload.name or "").suffix.lower()

        if kind == "image":
            allowed_exts = _CATALOG_IMAGE_EXTS
            max_bytes = _CATALOG_UPLOAD_MAX_IMAGE_BYTES
            label = "Görsel (jpg, jpeg, png, webp, gif)"
        elif kind == "video":
            allowed_exts = _CATALOG_VIDEO_EXTS
            max_bytes = _CATALOG_UPLOAD_MAX_VIDEO_BYTES
            label = "Video (mp4, webm, mov)"
        elif kind == "certificate":
            allowed_exts = _CATALOG_CERT_EXTS
            max_bytes = _CATALOG_UPLOAD_MAX_IMAGE_BYTES
            label = "Sertifika (pdf, jpg, jpeg, png, webp)"
        else:
            allowed_exts = _CATALOG_IMAGE_EXTS | _CATALOG_VIDEO_EXTS | _CATALOG_CERT_EXTS
            max_bytes = _CATALOG_UPLOAD_MAX_VIDEO_BYTES if ext in _CATALOG_VIDEO_EXTS else _CATALOG_UPLOAD_MAX_IMAGE_BYTES
            label = "Görsel, video veya PDF"

        if ext not in allowed_exts:
            raise DomainError(
                f"Desteklenmeyen dosya türü ({ext or 'yok'}). İzin verilen: {label}.",
                code="CATALOG_MEDIA_TYPE",
                status_code=400,
            )

        if upload.size and upload.size > max_bytes:
            limit_mb = max_bytes // (1024 * 1024)
            raise DomainError(
                f"Dosya boyutu en fazla {limit_mb} MB olabilir.",
                code="CATALOG_MEDIA_TOO_LARGE",
                status_code=400,
            )

        filename = f"catalog/{uuid.uuid4().hex}{ext}"
        saved = default_storage.save(filename, upload)
        relative = f"{settings.MEDIA_URL.rstrip('/')}/{saved.lstrip('/')}"
        absolute = request.build_absolute_uri(relative)
        return envelope_response(
            {
                "url": absolute,
                "path": relative,
                "filename": upload.name or PurePosixPath(saved).name,
                "size": upload.size or 0,
            },
            request,
            status=201,
        )

"""Public read-only serving for catalog and definition media assets."""
from __future__ import annotations

import mimetypes
from pathlib import PurePosixPath

from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.views import View

ALLOWED_PUBLIC_MEDIA_PREFIXES = frozenset({"catalog", "definitions"})


class PublicCatalogMediaView(View):
    """Serve uploaded catalog/definition media files safely without exposing private directories."""

    prefix: str = ""

    def get(self, request, filename: str):
        if self.prefix not in ALLOWED_PUBLIC_MEDIA_PREFIXES:
            raise Http404("Media not found")

        clean = PurePosixPath(filename.replace("\\", "/"))
        if clean.is_absolute() or ".." in clean.parts or not clean.parts:
            raise Http404("Invalid media path")

        storage_key = f"{self.prefix}/{clean.as_posix()}"
        if not default_storage.exists(storage_key):
            raise Http404("Media not found")

        try:
            file_handle = default_storage.open(storage_key, "rb")
        except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
            raise Http404("Media not found") from exc

        content_type, _ = mimetypes.guess_type(clean.name)
        response = FileResponse(file_handle, content_type=content_type or "application/octet-stream")
        response["Cache-Control"] = "public, max-age=604800"
        response["X-Content-Type-Options"] = "nosniff"
        if clean.suffix.lower() == ".pdf":
            response["Content-Disposition"] = f'inline; filename="{clean.name}"'
        return response

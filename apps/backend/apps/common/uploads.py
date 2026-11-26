"""Upload content-type / magic-byte validation for KYC and partner documents."""

from __future__ import annotations

from typing import BinaryIO

from config.exceptions import DomainError

# Allowed MIME types for organization KYC / partner documents.
ALLOWED_DOCUMENT_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)

_PDF_MAGIC = b"%PDF"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF = b"RIFF"
_WEBP_WEBP = b"WEBP"
_MAX_SNIFF = 16


def _sniff_content_type(file_obj: BinaryIO) -> str | None:
    pos = file_obj.tell()
    try:
        head = file_obj.read(_MAX_SNIFF)
    finally:
        file_obj.seek(pos)

    if head.startswith(_PDF_MAGIC):
        return "application/pdf"
    if head.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if head.startswith(_PNG_MAGIC):
        return "image/png"
    if len(head) >= 12 and head.startswith(_WEBP_RIFF) and head[8:12] == _WEBP_WEBP:
        return "image/webp"
    return None


def validate_uploaded_document(file_obj, *, max_bytes: int = 10 * 1024 * 1024) -> str:
    """
    Validate size + declared content type + magic bytes.
    Returns the sniffed content type on success.
    """
    size = getattr(file_obj, "size", None)
    if size is None:
        pos = file_obj.tell()
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(pos)
    if size > max_bytes:
        raise DomainError("Belge en fazla 10 MB olabilir.", code="DOCUMENT_TOO_LARGE", status_code=400)

    declared = (getattr(file_obj, "content_type", None) or "").split(";")[0].strip().lower()
    sniffed = _sniff_content_type(file_obj)
    if sniffed is None:
        raise DomainError(
            "Dosya türü desteklenmiyor. PDF, JPEG, PNG veya WEBP yükleyin.",
            code="DOCUMENT_TYPE_INVALID",
            status_code=400,
        )
    if declared and declared not in ALLOWED_DOCUMENT_CONTENT_TYPES and declared != "application/octet-stream":
        raise DomainError(
            "Dosya Content-Type geçersiz.",
            code="DOCUMENT_TYPE_INVALID",
            status_code=400,
        )
    if declared in ALLOWED_DOCUMENT_CONTENT_TYPES and declared != sniffed:
        raise DomainError(
            "Dosya içeriği bildirilen tür ile uyuşmuyor.",
            code="DOCUMENT_TYPE_MISMATCH",
            status_code=400,
        )
    return sniffed

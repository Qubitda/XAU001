"""OPS LegalDocument detail / patch / IYS export hook."""

from __future__ import annotations

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from apps.consent.models import ConsentLog
from apps.consent.services import serialize_consent_log
from config.exceptions import DomainError

from .models import LegalDocument
from .services import serialize_legal_document


class OpsLegalDocumentDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "contracts:view",
        "PATCH": "legal_docs:manage",
    }

    def _get(self, doc_id: str) -> LegalDocument:
        doc = LegalDocument.objects.filter(id=doc_id).first()
        if doc is None:
            raise DomainError("Belge bulunamadı.", code="LEGAL_NOT_FOUND", status_code=404)
        return doc

    @extend_schema(tags=["OPS - Legal CMS"], summary="Yasal belge detay")
    def get(self, request: Request, document_id: str):
        return envelope_response(serialize_legal_document(self._get(document_id)), request)

    @extend_schema(tags=["OPS - Legal CMS"], summary="Yasal belge güncelle / yayınla")
    def patch(self, request: Request, document_id: str):
        doc = self._get(document_id)

        class Ser(serializers.Serializer):
            title = serializers.CharField(max_length=200, required=False)
            bodyHtml = serializers.CharField(required=False, allow_blank=True)
            bodyMd = serializers.CharField(required=False, allow_blank=True)
            isPublished = serializers.BooleanField(required=False)
            audience = serializers.ChoiceField(
                choices=LegalDocument.Audience.values, required=False
            )
            effectiveFrom = serializers.CharField(required=False, allow_blank=True, allow_null=True)

        ser = Ser(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if "title" in d:
            doc.title = d["title"].strip()
            # title is part of content_hash material — force recompute on save()
            doc.content_hash = ""
        if "bodyHtml" in d:
            doc.body_html = d["bodyHtml"]
            doc.content_hash = ""
        if "bodyMd" in d:
            doc.body_md = d["bodyMd"]
            doc.content_hash = ""
        if "isPublished" in d:
            doc.is_published = d["isPublished"]
        if "audience" in d:
            doc.audience = d["audience"]
        if "effectiveFrom" in d:
            doc.effective_from = parse_datetime(d["effectiveFrom"]) if d["effectiveFrom"] else None
        doc.save()
        return envelope_response(serialize_legal_document(doc), request)


class OpsIysConsentExportView(APIView):
    """Export hook for IYS — lists commercial consents with iys_reference fields."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "consents:view"

    @extend_schema(tags=["OPS - Consent"], summary="İYS dışa aktarım (hook)")
    def get(self, request: Request):
        qs = ConsentLog.objects.filter(
            purpose__in=[
                "COMMERCIAL_EMAIL",
                "COMMERCIAL_SMS",
                "COMMERCIAL_WHATSAPP",
                "COMMERCIAL_CALL",
            ]
        ).order_by("-created_at")[:2000]
        rows = []
        for log in qs:
            base = serialize_consent_log(log)
            rows.append(
                {
                    **base,
                    "iysReady": bool(log.iys_reference) or log.status in ("GRANTED", "WITHDRAWN"),
                    "exportedAtHint": timezone.now().isoformat(),
                }
            )
        return envelope_response(
            {
                "items": rows,
                "note": "Gerçek İYS API entegrasyonu sonraki fazda; bu endpoint export hook’tur.",
            },
            request,
        )

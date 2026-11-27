"""Public storefront legal document reads."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.common.responses import envelope_response
from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent
from config.exceptions import DomainError

from .models import LegalDocument
from .services import get_published_document, serialize_legal_document


class StorefrontLegalDocumentListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Storefront - Legal"], summary="Yayınlanan yasal metin listesi")
    def get(self, request: Request):
        qs = (
            LegalDocument.objects.filter(is_published=True)
            .order_by("code", "-effective_from", "-created_at")
        )
        # Latest published per code
        seen: set[str] = set()
        items = []
        for doc in qs:
            if doc.code in seen:
                continue
            seen.add(doc.code)
            items.append(serialize_legal_document(doc, include_body=False))
        return envelope_response(items, request)


class StorefrontLegalDocumentDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Storefront - Legal"], summary="Kod ile yayınlanan yasal metin")
    def get(self, request: Request, code: str):
        doc = get_published_document(code.upper())
        if doc is None:
            raise DomainError("Yasal metin bulunamadı.", code="LEGAL_NOT_FOUND", status_code=404)
        return envelope_response(serialize_legal_document(doc, include_body=True), request)


class NewsletterSubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()


class StorefrontNewsletterSubscribeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Storefront - Legal"], summary="Bülten / ticari e-posta aboneliği")
    def post(self, request: Request):
        ser = NewsletterSubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].strip().lower()
        log = append_consent(
            guest_email=email,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.FOOTER,
            ip_address=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return envelope_response(
            {"id": str(log.id), "email": email, "status": log.status},
            request,
            status=201,
        )

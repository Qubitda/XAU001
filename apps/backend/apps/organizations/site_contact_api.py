"""OPS + storefront APIs for site contact settings."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response

from .site_contact import get_or_create_site_contact, serialize_site_contact, update_site_contact


class SiteContactWriteSerializer(serializers.Serializer):
    companyName = serializers.CharField(max_length=200, required=False, allow_blank=True)
    tagline = serializers.CharField(max_length=320, required=False, allow_blank=True)
    addressLine = serializers.CharField(max_length=320, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=64, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    workingHours = serializers.CharField(max_length=120, required=False, allow_blank=True)
    whatsapp = serializers.CharField(max_length=64, required=False, allow_blank=True)
    instagramUrl = serializers.CharField(max_length=500, required=False, allow_blank=True)
    youtubeUrl = serializers.CharField(max_length=500, required=False, allow_blank=True)
    tiktokUrl = serializers.CharField(max_length=500, required=False, allow_blank=True)
    pinterestUrl = serializers.CharField(max_length=500, required=False, allow_blank=True)
    mapUrl = serializers.CharField(max_length=500, required=False, allow_blank=True)


class OpsSiteContactView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "legal_docs:manage",
        "PUT": "legal_docs:manage",
        "PATCH": "legal_docs:manage",
    }

    @extend_schema(tags=["OPS - Site Contact"], summary="Şirket iletişim bilgileri")
    def get(self, request: Request):
        return envelope_response(serialize_site_contact(get_or_create_site_contact()), request)

    @extend_schema(tags=["OPS - Site Contact"], summary="Şirket iletişim güncelle")
    def put(self, request: Request):
        return self._save(request)

    @extend_schema(tags=["OPS - Site Contact"], summary="Şirket iletişim kısmi güncelle")
    def patch(self, request: Request):
        return self._save(request)

    def _save(self, request: Request):
        ser = SiteContactWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        row = update_site_contact(ser.validated_data)
        return envelope_response(serialize_site_contact(row), request)


class StorefrontSiteContactView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Storefront"], summary="Yayınlanan şirket iletişim bilgileri")
    def get(self, request: Request):
        return envelope_response(serialize_site_contact(get_or_create_site_contact()), request)

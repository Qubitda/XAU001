from __future__ import annotations

import hashlib
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.catalog.models import ProductModel
from apps.common.responses import envelope_response

from ..models import SocialAttribution, SocialCampaign, SocialPlatform
from ..services import (
    SocialCommerceError,
    build_social_b2c_product_dto,
    ingest_social_webhook,
)

ALLOWED_PUBLIC_ATTRIBUTION_EVENTS = frozenset({"CLICK", "VIEW", "SHARE"})


class SocialAttributionRateThrottle(AnonRateThrottle):
    """Rate limit public traffic attribution endpoint to prevent spam/abuse."""

    scope = "social_attribution"


class StorefrontSocialShareLinkView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Storefront Social"], summary="Get B2C shareable link & OG metadata for a product")
    def get(self, request: Request, parent_sku: str):
        product = get_object_or_404(
            ProductModel,
            parent_sku=parent_sku,
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            owner_organization__isnull=True,
        )
        if "B2C_API" not in (product.sales_channels or []):
            raise Http404("Ürün B2C kanalında aktif değil.")
        dto = build_social_b2c_product_dto(product)
        return envelope_response(dto, request=request)


class StorefrontSocialAttributionView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SocialAttributionRateThrottle]

    @extend_schema(tags=["Storefront Social"], summary="Record social traffic / UTM attribution (traffic events only)")
    def post(self, request: Request):
        platform = str(request.data.get("platform") or SocialPlatform.INSTAGRAM).upper()
        if platform not in SocialPlatform.values:
            platform = SocialPlatform.INSTAGRAM
        event_type = str(request.data.get("eventType") or "CLICK").upper()[:32]
        if event_type not in ALLOWED_PUBLIC_ATTRIBUTION_EVENTS:
            return envelope_response(
                {
                    "error": {
                        "code": "INVALID_EVENT_TYPE",
                        "message": "İstemci yalnızca CLICK, VIEW veya SHARE olayı gönderebilir; ORDER sunucu tarafında doğrulanır.",
                    }
                },
                request=request,
                status=status.HTTP_400_BAD_REQUEST,
            )

        touch_role = str(request.data.get("touchRole") or SocialAttribution.TouchRole.LAST_TOUCH).upper()
        if touch_role not in SocialAttribution.TouchRole.values:
            touch_role = SocialAttribution.TouchRole.LAST_TOUCH

        sku = str(request.data.get("parentSku") or "").strip()
        camp_code = str(request.data.get("utmCampaign") or "").strip()
        session_key = str(request.data.get("sessionKey") or "").strip()[:64]

        # Short-window burst deduplication per session/IP + event + sku + campaign
        client_ident = session_key or str(request.META.get("REMOTE_ADDR") or "anon")
        burst_raw = f"{client_ident}:{platform}:{event_type}:{sku}:{camp_code}".encode("utf-8")
        burst_key = f"soc_attr_burst:{hashlib.sha256(burst_raw).hexdigest()[:24]}"
        existing_id = cache.get(burst_key)
        if existing_id:
            return envelope_response({"id": existing_id, "deduplicated": True}, request=request, status=status.HTTP_200_OK)

        product = ProductModel.objects.filter(parent_sku=sku, owner_organization__isnull=True).first() if sku else None
        campaign = SocialCampaign.objects.filter(code=camp_code, audience="B2C").first() if camp_code else None

        attr = SocialAttribution.objects.create(
            platform=platform,
            touch_role=touch_role,
            utm_source=str(request.data.get("utmSource") or "")[:80],
            utm_medium=str(request.data.get("utmMedium") or "")[:80],
            utm_campaign=camp_code[:120],
            utm_content=str(request.data.get("utmContent") or "")[:120],
            product=product,
            campaign=campaign,
            session_key=session_key,
            event_type=event_type,
            order_no="",
            revenue_try=Decimal("0.00"),
            audience="B2C",
        )
        cache.set(burst_key, str(attr.id), timeout=5)
        return envelope_response({"id": str(attr.id)}, request=request, status=status.HTTP_201_CREATED)


class StorefrontSocialCampaignListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Storefront Social"], summary="List active public B2C social campaigns within date window")
    def get(self, request: Request):
        now = timezone.now()
        qs = (
            SocialCampaign.objects.filter(is_active=True, audience="B2C", organization__isnull=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))[:50]
        )
        data = [
            {
                "id": str(c.id),
                "name": c.name,
                "code": c.code,
                "channels": c.channels,
                "displayDiscountPct": str(c.discount_pct),
                "pricingApplied": c.discount_pct > 0,
            }
            for c in qs
        ]
        return envelope_response(data, request=request)


class StorefrontSocialWebhookView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Storefront Social"], summary="Meta/WhatsApp webhook verification challenge")
    def get(self, request: Request, platform: str):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")
        expected = getattr(settings, "SOCIAL_WEBHOOK_VERIFY_TOKEN", "")
        if mode == "subscribe" and expected and token == expected:
            return HttpResponse(challenge, content_type="text/plain", status=200)
        return HttpResponse("Forbidden", status=403)

    @extend_schema(tags=["Storefront Social"], summary="Ingest signed social platform webhook")
    def post(self, request: Request, platform: str):
        sig = (
            request.headers.get("X-Hub-Signature-256")
            or request.headers.get("X-Social-Signature")
            or ""
        )
        try:
            res = ingest_social_webhook(
                platform=platform,
                raw_body=request.body,
                signature_header=sig,
                payload=request.data if isinstance(request.data, dict) else {},
            )
            return envelope_response(res, request=request)
        except SocialCommerceError as exc:
            return envelope_response(
                {"error": {"code": exc.code, "message": exc.message}},
                request=request,
                status=exc.status_code,
            )

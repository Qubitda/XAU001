from __future__ import annotations

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import IsB2bOrganizationMember
from apps.catalog.models import ProductModel
from apps.common.responses import envelope_response
from apps.organizations.selectors import resolve_tenant_context, scope_queryset_to_organization

from ..models import SocialCampaign
from ..services import SocialCommerceError, build_b2b_social_catalog_items, build_b2b_social_product_dto


class B2bSocialCatalogView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    @extend_schema(tags=["B2B Social"], summary="B2B dealer-isolated shareable social catalog")
    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        if ctx.organization is None:
            return envelope_response([], request=request)
        items = build_b2b_social_catalog_items(organization=ctx.organization)
        return envelope_response(items, request=request)


class B2bSocialShareLinkView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    @extend_schema(tags=["B2B Social"], summary="B2B dealer product share link (B2B pricing & org-isolated)")
    def get(self, request: Request, parent_sku: str):
        ctx = resolve_tenant_context(request)
        if ctx.organization is None:
            raise Http404("Aktif bayi organizasyonu bulunamadı.")
        product = get_object_or_404(
            scope_queryset_to_organization(
                ProductModel.objects.all(),
                ctx,
                org_field="owner_organization",
                include_shared=True,
            ),
            parent_sku=parent_sku,
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
        )
        if "B2B" not in (product.sales_channels or []):
            raise Http404("Ürün B2B kanalında aktif değil.")
        try:
            dto = build_b2b_social_product_dto(product, ctx.organization)
        except SocialCommerceError as exc:
            return envelope_response(
                {"error": {"code": exc.code, "message": exc.message}},
                request=request,
                status=exc.status_code,
            )
        return envelope_response(dto, request=request)


class B2bSocialCampaignListView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    @extend_schema(tags=["B2B Social"], summary="List active B2B campaigns scoped to organization and date window")
    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        now = timezone.now()
        qs = (
            scope_queryset_to_organization(
                SocialCampaign.objects.filter(is_active=True, audience="B2B"),
                ctx,
                include_shared=True,
            )
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

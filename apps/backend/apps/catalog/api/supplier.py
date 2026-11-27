"""Supplier catalog & offer APIs + OPS supplier offer comparison & approval."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.catalog.models import ProductModel, ProductVariant, SupplierOffer
from apps.common.responses import MONEY_Q, apply_safe_ordering, dec_str, envelope_response, paginated_envelope_response
from apps.organizations.selectors import resolve_active_organization, resolve_tenant_context
from config.exceptions import DomainError

from .serializers import _apply_filters, _products_queryset


class SupplierOfferInputSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32)
    variantId = serializers.UUIDField(required=False, allow_null=True)
    supplierSku = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    costAmount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.ChoiceField(choices=["TRY", "USD", "EUR", "GBP", "XAU"], default="USD", required=False)
    leadTimeDays = serializers.IntegerField(min_value=0, max_value=365, default=3, required=False)
    availableQty = serializers.IntegerField(min_value=0, default=0, required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=[SupplierOffer.Status.DRAFT, SupplierOffer.Status.SUBMITTED],
        default=SupplierOffer.Status.SUBMITTED,
        required=False,
    )
    supplierOrganizationId = serializers.UUIDField(required=False, allow_null=True)


class OpsSupplierOfferDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[SupplierOffer.Status.APPROVED, SupplierOffer.Status.REJECTED])
    notes = serializers.CharField(required=False, allow_blank=True)


def _serialize_supplier_product(product: ProductModel) -> dict:
    return {
        "id": str(product.id),
        "parentSku": product.parent_sku,
        "title": product.title,
        "productKind": product.product_kind,
        "category": product.category,
        "subCategory": product.sub_category,
        "collection": product.collection,
        "purityCode": product.purity_code,
        "metalColor": product.metal_color,
        "grossWeightGram": str(product.gross_weight_gram),
        "catalogStatus": product.catalog_status,
        "variants": [
            {
                "id": str(v.id),
                "sku": v.sku,
                "purityCode": v.purity_code,
                "metalColor": v.metal_color,
                "size": v.size,
            }
            for v in product.variants.all()
            if v.is_active
        ],
    }


def _serialize_supplier_offer(offer: SupplierOffer, *, include_identity: bool = True, masked_label: str | None = None) -> dict:
    payload = {
        "id": str(offer.id),
        "offerRef": str(offer.offer_ref),
        "parentSku": offer.product.parent_sku,
        "productTitle": offer.product.title,
        "variantId": str(offer.variant_id) if offer.variant_id else None,
        "variantSku": offer.variant.sku if offer.variant else None,
        "costAmount": dec_str(offer.cost_amount, MONEY_Q),
        "currency": offer.currency,
        "leadTimeDays": offer.lead_time_days,
        "availableQty": offer.available_qty,
        "status": offer.status,
        "isActive": offer.is_active,
        "notes": offer.notes,
        "reviewedAt": offer.reviewed_at.isoformat() if offer.reviewed_at else None,
        "createdAt": offer.created_at.isoformat(),
        "updatedAt": offer.updated_at.isoformat(),
    }
    if include_identity:
        payload.update(
            {
                "supplierOrganizationId": str(offer.supplier_organization_id),
                "supplierName": offer.supplier_organization.name,
                "supplierCode": offer.supplier_organization.code,
                "supplierSku": offer.supplier_sku,
            }
        )
    elif masked_label:
        payload["supplierLabel"] = masked_label
    return payload


class SupplierProductListView(APIView):
    permission_classes = [HasPortalPermission]
    required_permission = "supplier_products:read"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = _products_queryset().exclude(catalog_status=ProductModel.CatalogStatus.ARCHIVED)
        if not ctx.is_ops:
            if ctx.organization is None:
                qs = qs.none()
            else:
                qs = qs.filter(Q(owner_organization__isnull=True) | Q(owner_organization=ctx.organization))
        qs = _apply_filters(qs, request)
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "title": "title", "parentSku": "parent_sku"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, _serialize_supplier_product, default_page_size=24, max_page_size=100)


class SupplierOfferListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    required_permissions_by_method = {
        "GET": "supplier_products:read",
        "POST": "supplier_products:write",
    }

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = SupplierOffer.objects.select_related("product", "variant", "supplier_organization").filter(is_active=True)
        if not ctx.is_ops:
            if ctx.organization is None:
                qs = qs.none()
            else:
                qs = qs.filter(supplier_organization=ctx.organization)
        status_filter = (request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(product__parent_sku=parent_sku)
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"costAmount": "cost_amount", "leadTimeDays": "lead_time_days", "createdAt": "created_at"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, _serialize_supplier_offer, default_page_size=24, max_page_size=100)

    @transaction.atomic
    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        serializer = SupplierOfferInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if ctx.is_ops and d.get("supplierOrganizationId"):
            supplier_org = resolve_active_organization(d["supplierOrganizationId"])
        elif ctx.organization is not None:
            supplier_org = ctx.organization
        else:
            raise DomainError("Tedarikçi organizasyon kapsamı bulunamadı.", code="ORGANIZATION_REQUIRED", status_code=403)

        sku = d["parentSku"].strip().upper()
        product = ProductModel.objects.filter(parent_sku=sku).exclude(catalog_status=ProductModel.CatalogStatus.ARCHIVED).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {sku}", code="PRODUCT_NOT_FOUND", status_code=404)

        variant = None
        if d.get("variantId"):
            variant = ProductVariant.objects.filter(id=d["variantId"], product=product, is_active=True).first()
            if variant is None:
                raise DomainError("Seçilen varyant bu ürüne ait değil veya pasif.", code="VARIANT_NOT_FOUND", status_code=404)

        try:
            offer = SupplierOffer.objects.create(
                product=product,
                variant=variant,
                supplier_organization=supplier_org,
                supplier_sku=d.get("supplierSku", "").strip(),
                cost_amount=d["costAmount"],
                currency=d.get("currency", "USD"),
                lead_time_days=d.get("leadTimeDays", 3),
                available_qty=d.get("availableQty", 0),
                notes=d.get("notes", ""),
                status=d.get("status", SupplierOffer.Status.SUBMITTED),
            )
        except IntegrityError:
            raise DomainError(
                "Bu ürün/varyant için aktif bir tedarikçi teklifiniz zaten mevcut.",
                code="DUPLICATE_SUPPLIER_OFFER",
                status_code=409,
            )

        record_audit(
            action="SUPPLIER_OFFER_CREATED",
            entity_type="SupplierOffer",
            entity_id=str(offer.id),
            actor=request.user,
            metadata={"parent_sku": product.parent_sku, "offer_ref": str(offer.offer_ref)},
        )
        offer = SupplierOffer.objects.select_related("product", "variant", "supplier_organization").get(id=offer.id)
        return envelope_response(_serialize_supplier_offer(offer), request, status=201)


class SupplierOfferDetailView(APIView):
    permission_classes = [HasPortalPermission]
    required_permissions_by_method = {
        "GET": "supplier_products:read",
        "PATCH": "supplier_products:write",
        "DELETE": "supplier_products:write",
    }

    def _get_offer(self, request: Request, offer_id: str, *, for_update: bool = False) -> SupplierOffer:
        ctx = resolve_tenant_context(request)
        qs = SupplierOffer.objects.select_related("product", "variant", "supplier_organization")
        if for_update:
            qs = qs.select_for_update()
        offer = qs.filter(id=offer_id, is_active=True).first()
        if offer is None:
            raise DomainError("Teklif bulunamadı.", code="SUPPLIER_OFFER_NOT_FOUND", status_code=404)
        if not ctx.is_ops and (ctx.organization is None or offer.supplier_organization_id != ctx.organization.id):
            raise DomainError("Teklif bulunamadı.", code="SUPPLIER_OFFER_NOT_FOUND", status_code=404)
        return offer

    def get(self, request: Request, offer_id: str):
        offer = self._get_offer(request, offer_id)
        return envelope_response(_serialize_supplier_offer(offer), request)

    @transaction.atomic
    def patch(self, request: Request, offer_id: str):
        offer = self._get_offer(request, offer_id, for_update=True)
        serializer = SupplierOfferInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        field_map = {
            "supplierSku": "supplier_sku",
            "costAmount": "cost_amount",
            "currency": "currency",
            "leadTimeDays": "lead_time_days",
            "availableQty": "available_qty",
            "notes": "notes",
            "status": "status",
        }
        for api_key, model_field in field_map.items():
            if api_key in d:
                val = d[api_key].strip() if isinstance(d[api_key], str) else d[api_key]
                setattr(offer, model_field, val)
        offer.save()
        record_audit(
            action="SUPPLIER_OFFER_UPDATED",
            entity_type="SupplierOffer",
            entity_id=str(offer.id),
            actor=request.user,
            metadata={"parent_sku": offer.product.parent_sku, "status": offer.status},
        )
        return envelope_response(_serialize_supplier_offer(offer), request)

    @transaction.atomic
    def delete(self, request: Request, offer_id: str):
        offer = self._get_offer(request, offer_id, for_update=True)
        offer.is_active = False
        offer.status = SupplierOffer.Status.INACTIVE
        offer.save(update_fields=["is_active", "status", "updated_at"])
        record_audit(
            action="SUPPLIER_OFFER_ARCHIVED",
            entity_type="SupplierOffer",
            entity_id=str(offer.id),
            actor=request.user,
            metadata={"parent_sku": offer.product.parent_sku},
        )
        return envelope_response({"id": str(offer.id), "archived": True}, request)


class OpsProductOffersView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "suppliers:manage"

    def get(self, request: Request, parent_sku: str):
        ctx = resolve_tenant_context(request)
        product = ProductModel.objects.filter(parent_sku=parent_sku).first()
        if product is None:
            raise DomainError(f"Ürün bulunamadı: {parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
        can_view_identity = "supplier_identity:view" in ctx.permissions
        offers = (
            SupplierOffer.objects.select_related("product", "variant", "supplier_organization")
            .filter(product=product, is_active=True)
            .order_by("cost_amount", "lead_time_days")
        )
        items = [
            _serialize_supplier_offer(
                o,
                include_identity=can_view_identity,
                masked_label=None if can_view_identity else f"Tedarikçi #{idx}",
            )
            for idx, o in enumerate(offers, start=1)
        ]
        return envelope_response({"parentSku": product.parent_sku, "offers": items}, request)


class OpsSupplierOfferDecisionView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "suppliers:manage"

    @transaction.atomic
    def post(self, request: Request, offer_id: str):
        offer = (
            SupplierOffer.objects.select_for_update()
            .select_related("product", "variant", "supplier_organization")
            .filter(id=offer_id, is_active=True)
            .first()
        )
        if offer is None:
            raise DomainError("Teklif bulunamadı.", code="SUPPLIER_OFFER_NOT_FOUND", status_code=404)
        serializer = OpsSupplierOfferDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        prev_status = offer.status
        offer.status = d["decision"]
        if "notes" in d:
            offer.notes = d["notes"]
        offer.reviewed_by = request.user
        offer.reviewed_at = timezone.now()
        offer.save(update_fields=["status", "notes", "reviewed_by", "reviewed_at", "updated_at"])
        record_audit(
            action="OPS_SUPPLIER_OFFER_DECISION",
            entity_type="SupplierOffer",
            entity_id=str(offer.id),
            actor=request.user,
            metadata={"changed": {"status": {"from": prev_status, "to": offer.status}}},
        )
        return envelope_response(_serialize_supplier_offer(offer), request)

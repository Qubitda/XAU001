from decimal import Decimal, ROUND_HALF_UP
from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.api_keys.permissions import HasApiScopeWrite, StorefrontScopedPermissionsMixin
from apps.idempotency.mixins import IdempotentCreateMixin
from apps.authorization.permissions import HasPortalPermission, IsB2bOrganizationMember
from apps.common.responses import envelope_response
from apps.market.services import get_current_rate_snapshot
from apps.organizations.selectors import resolve_tenant_context
from apps.pricing.services import get_latest_price_lock, get_or_refresh_price_lock
from config.exceptions import DomainError
from .models import B2bDraftLine, B2bOrder, B2cCartItem, B2cOrder
from .services import (
    add_b2b_draft_lines,
    add_b2c_cart_item,
    refresh_b2c_cart_price_lock,
    reorder_b2b_order,
    submit_b2b_order,
    submit_b2c_order,
    transition_b2b_order_status,
    transition_b2c_order_status,
)


MONEY_Q = Decimal("0.01")
GRAM_Q = Decimal("0.0001")


def _dec_str(value: Decimal, q: Decimal) -> str:
    return str(Decimal(value).quantize(q, rounding=ROUND_HALF_UP))


# ── Strict Input Validation Serializers ──────────────────────────────────
class B2cCartItemCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32, required=False, allow_blank=True)
    variantId = serializers.UUIDField(required=False)
    variantSku = serializers.CharField(max_length=64, required=False, allow_blank=True)
    purityCode = serializers.CharField(max_length=16, required=False)
    metalColor = serializers.ChoiceField(choices=["Beyaz", "Sarı", "Rose"], required=False)
    size = serializers.IntegerField(min_value=6, max_value=70, required=False)
    qty = serializers.IntegerField(min_value=1, max_value=10, default=1)
    engravingText = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    giftWrap = serializers.BooleanField(required=False, default=False)
    giftNote = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("parentSku") and not attrs.get("variantId") and not attrs.get("variantSku"):
            raise serializers.ValidationError("parentSku, variantId veya variantSku gereklidir.")
        return attrs


class B2cCartItemUpdateSerializer(serializers.Serializer):
    qty = serializers.IntegerField(min_value=1, max_value=10, required=False)
    engravingText = serializers.CharField(max_length=40, required=False, allow_blank=True)
    giftWrap = serializers.BooleanField(required=False)
    giftNote = serializers.CharField(max_length=200, required=False, allow_blank=True)


class B2cOrderCreateSerializer(serializers.Serializer):
    customerName = serializers.CharField(max_length=160)
    customerPhone = serializers.CharField(max_length=32)
    customerEmail = serializers.EmailField()
    isTurkishCitizen = serializers.BooleanField(required=False, default=True)
    identityNumber = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    shippingCity = serializers.CharField(max_length=80)
    shippingAddress = serializers.CharField(max_length=500)
    billingName = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    billingCity = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    billingAddress = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    billingIdentityOrTaxNo = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    paymentMethod = serializers.ChoiceField(choices=["CREDIT_CARD", "BANK_TRANSFER", "INSTALLMENT"])
    acceptedCustomPolicy = serializers.BooleanField(default=True)

    def validate(self, attrs):
        is_tr = attrs.get("isTurkishCitizen", True)
        tckn = (attrs.get("identityNumber") or "").strip()
        if is_tr:
            if not tckn.isdigit() or len(tckn) != 11:
                raise serializers.ValidationError(
                    {"identityNumber": "Türk vatandaşları için 11 haneli TC Kimlik No zorunludur."}
                )
        elif tckn and (not tckn.isdigit() or len(tckn) != 11):
            raise serializers.ValidationError(
                {"identityNumber": "TC Kimlik No girildiyse 11 haneli rakam olmalıdır."}
            )
        attrs["identityNumber"] = tckn
        return attrs


class B2bDraftLineCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32, required=False, allow_blank=True)
    variantId = serializers.UUIDField(required=False)
    variantSku = serializers.CharField(max_length=64, required=False, allow_blank=True)
    purityCode = serializers.CharField(max_length=16, required=False)
    metalColor = serializers.ChoiceField(choices=["Beyaz", "Sarı", "Rose"], required=False)
    size = serializers.IntegerField(min_value=6, max_value=70, required=False)
    qty = serializers.IntegerField(min_value=1, max_value=500, default=1)
    supplyType = serializers.ChoiceField(choices=["STOCK", "PRODUCTION"], required=False)
    dealerStampNote = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("parentSku") and not attrs.get("variantId") and not attrs.get("variantSku"):
            raise serializers.ValidationError("parentSku, variantId veya variantSku gereklidir.")
        return attrs


class B2bDraftLineUpdateSerializer(serializers.Serializer):
    qty = serializers.IntegerField(min_value=1, max_value=500, required=False)
    supplyType = serializers.ChoiceField(choices=["STOCK", "PRODUCTION"], required=False)
    dealerStampNote = serializers.CharField(max_length=80, required=False, allow_blank=True)


class B2bOrderCreateSerializer(serializers.Serializer):
    contactPerson = serializers.CharField(max_length=120)
    settlementMethod = serializers.ChoiceField(
        choices=["HAS_PLUS_CURRENCY", "FX_CASH", "CONSIGNMENT", "OPEN_ACCOUNT"]
    )
    rateLockMode = serializers.ChoiceField(choices=["LOCK_ON_ORDER", "SETTLE_ON_DELIVERY"])
    consignmentDays = serializers.IntegerField(min_value=1, max_value=180, required=False, allow_null=True)
    deliveryMethod = serializers.ChoiceField(
        choices=["BRINKS_INSURED", "KAPALICARSI_HANDOVER", "FACTORY_PICKUP"]
    )
    orderNote = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    acceptedWeightTolerance = serializers.BooleanField(default=True)
    shippingAddressId = serializers.UUIDField(required=False, allow_null=True)
    billingAddressId = serializers.UUIDField(required=False, allow_null=True)
    shippingCity = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    shippingAddress = serializers.CharField(required=False, allow_blank=True, default="")
    billingCity = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    billingAddress = serializers.CharField(required=False, allow_blank=True, default="")


# ── Output Serializers (Blind Pool & Decimal-as-String Compliant) ────────
def _serialize_b2c_item(item) -> dict:
    return {
        "id": str(item.id),
        "variantId": str(item.variant_id) if item.variant_id else None,
        "bundleId": str(item.bundle_id) if getattr(item, "bundle_id", None) else None,
        "bundleRole": getattr(item, "bundle_role", "") or None,
        "sku": item.sku,
        "parentSku": item.parent_sku,
        "title": item.title,
        "category": item.category,
        "metalColor": item.metal_color,
        "purityCode": item.purity_code,
        "size": item.size,
        "sizeUnitLabel": item.size_unit_label,
        "qty": item.qty,
        "engravingText": item.engraving_text,
        "giftWrap": item.gift_wrap,
        "giftNote": item.gift_note,
        "certificateLabel": item.certificate_label,
        "stockStatus": item.stock_status,
        "leadTimeText": item.lead_time_text,
        "grossWeightGram": _dec_str(item.gross_weight_gram, GRAM_Q),
        "unitListPriceTry": _dec_str(item.unit_list_price_try, MONEY_Q),
        "unitFinalPriceTry": _dec_str(item.unit_final_price_try, MONEY_Q),
        "snapshotId": item.snapshot_code,
        "addedAt": item.created_at.isoformat(),
    }


def _serialize_b2c_cart(user) -> dict:
    items = list(B2cCartItem.objects.filter(user=user))
    if items:
        lock = get_latest_price_lock(user) or get_or_refresh_price_lock(user)
    else:
        lock = get_or_refresh_price_lock(user)
    return {
        "items": [_serialize_b2c_item(i) for i in items],
        "priceLockedUntil": lock.expires_at.isoformat(),
        "snapshotId": lock.rate_snapshot.snapshot_code,
    }


def _serialize_b2c_order(order: B2cOrder) -> dict:
    # Prefer immutable order snapshot; fall back for pre-migration rows.
    ship_name = order.shipping_full_name or order.customer.full_name
    ship_phone = order.shipping_phone or order.customer.phone
    ship_email = order.shipping_email or order.customer.email
    ship_city = order.shipping_city or order.customer.city
    ship_address = order.shipping_address or order.customer.address
    return {
        "orderNo": order.order_no,
        "createdAt": order.created_at.isoformat(),
        "snapshotId": order.rate_snapshot.snapshot_code,
        "goldRateTryPerGram": _dec_str(order.gold_rate_try_per_gram, GRAM_Q),
        "customerName": ship_name,
        "customerPhone": ship_phone,
        "customerEmail": ship_email,
        "shippingCity": ship_city,
        "shippingAddress": ship_address,
        "billingName": order.billing_full_name or ship_name,
        "billingIdentityOrTaxNo": order.billing_identity_or_tax_no or order.customer.identity_or_tax_no,
        "billingCity": order.billing_city or ship_city,
        "billingAddress": order.billing_address or ship_address,
        "paymentMethod": order.payment_method,
        "acceptedCustomPolicy": order.accepted_custom_policy,
        "items": [_serialize_b2c_item(i) for i in order.items.all()],
        "subtotalListTry": _dec_str(order.subtotal_list_try, MONEY_Q),
        "campaignDiscountTry": _dec_str(order.campaign_discount_try, MONEY_Q),
        "transferDiscountTry": _dec_str(order.transfer_discount_try, MONEY_Q),
        "insuredShippingTry": _dec_str(order.insured_shipping_try, MONEY_Q),
        "vatIncludedTry": _dec_str(order.vat_included_try, MONEY_Q),
        "grandTotalTry": _dec_str(order.grand_total_try, MONEY_Q),
        "status": order.status,
    }


def _serialize_b2b_line(line, *, for_ops: bool = False) -> dict:
    """
    Dealer-facing B2B line: product attrs + wholesale prices only.
    Fire / net metal / labor+stone cost components stay OPS-only (blind-pool).
    """
    data = {
        "id": str(line.id),
        "variantId": str(line.variant_id) if line.variant_id else None,
        "sku": line.sku,
        "parentSku": line.parent_sku,
        "title": line.title,
        "category": line.category,
        "metalColor": line.metal_color,
        "purityCode": line.purity_code,
        "size": line.size,
        "sizeUnitLabel": line.size_unit_label,
        "qty": line.qty,
        "supplyType": line.supply_type,
        "dealerStampNote": line.dealer_stamp_note,
        "unitGrossGram": _dec_str(line.unit_gross_gram, GRAM_Q),
        "unitWholesaleUsd": _dec_str(line.unit_wholesale_usd, MONEY_Q),
        "unitWholesaleTry": _dec_str(line.unit_wholesale_try, MONEY_Q),
        "pricingCurrency": line.pricing_currency,
        "snapshotId": line.snapshot_code,
        "addedAt": line.created_at.isoformat(),
    }
    if for_ops:
        data.update(
            {
                "unitNetMetalGram": _dec_str(line.unit_net_metal_gram, GRAM_Q),
                "unitFireIncludedFineGram": _dec_str(line.unit_fire_included_fine_gram, GRAM_Q),
                "unitLaborAndStoneUsd": _dec_str(line.unit_labor_and_stone_usd, MONEY_Q),
            }
        )
    return data


def _serialize_b2b_draft(org, branch) -> dict:
    snap = get_current_rate_snapshot()
    lines = B2bDraftLine.objects.filter(organization=org)
    return {
        "lines": [_serialize_b2b_line(l, for_ops=False) for l in lines],
        "dealer": {
            "organizationId": str(org.id),
            "dealerCode": org.code,
            "companyName": org.name,
            "taxOfficeAndNo": org.tax_office_and_no,
            "contactName": org.contact_name,
            "city": f"{branch.city} / {branch.name}" if branch else org.city,
            "branchId": str(branch.id) if branch else "",
            "branchName": branch.name if branch else "Merkez",
            "creditLimitUsd": _dec_str(org.credit_limit_usd, MONEY_Q),
            "usedCreditUsd": _dec_str(org.used_credit_usd, MONEY_Q),
            "hasLimitGram": _dec_str(org.has_limit_gram, GRAM_Q),
            "usedHasGram": _dec_str(org.used_has_gram, GRAM_Q),
            "defaultConsignmentDays": org.default_consignment_days,
        },
        "snapshotId": snap.snapshot_code,
    }


def _serialize_b2b_order(order: B2bOrder, *, for_ops: bool = False) -> dict:
    data = {
        "orderNo": order.order_no,
        "createdAt": order.created_at.isoformat(),
        "snapshotId": order.rate_snapshot.snapshot_code,
        "usdTryRate": _dec_str(order.usd_try_rate, GRAM_Q),
        "goldRateTryPerGram": _dec_str(order.gold_rate_try_per_gram, GRAM_Q),
        "organizationId": str(order.organization_id),
        "branchId": str(order.branch_id) if order.branch_id else "",
        "branchName": order.branch.name if order.branch else "Merkez",
        "createdByUserId": str(order.created_by_id),
        "createdByUserName": order.created_by.full_name,
        "dealerCode": order.organization.code,
        "dealerName": order.organization.name,
        "taxOfficeAndNo": order.billing_tax_office_and_no or order.organization.tax_office_and_no,
        "contactPerson": order.contact_person,
        "settlementMethod": order.settlement_method,
        "rateLockMode": order.rate_lock_mode,
        "consignmentDays": order.consignment_days,
        "deliveryMethod": order.delivery_method,
        "orderNote": order.order_note,
        "acceptedWeightTolerance": order.accepted_weight_tolerance,
        "shippingTitle": order.shipping_title,
        "shippingCity": order.shipping_city,
        "shippingAddress": order.shipping_address,
        "shippingContactName": order.shipping_contact_name,
        "shippingPhone": order.shipping_phone,
        "billingTitle": order.billing_title,
        "billingCity": order.billing_city,
        "billingAddress": order.billing_address,
        "billingContactName": order.billing_contact_name,
        "billingPhone": order.billing_phone,
        "lines": [_serialize_b2b_line(l, for_ops=for_ops) for l in order.lines.all()],
        "totalPieces": order.total_pieces,
        "totalGrossGram": _dec_str(order.total_gross_gram, GRAM_Q),
        "totalWholesaleUsd": _dec_str(order.total_wholesale_usd, MONEY_Q),
        "totalWholesaleTry": _dec_str(order.total_wholesale_try, MONEY_Q),
        "status": order.status,
    }
    if for_ops:
        data.update(
            {
                "totalHasGoldGram": _dec_str(order.total_has_gold_gram, GRAM_Q),
                "totalLaborAndStoneUsd": _dec_str(order.total_labor_and_stone_usd, MONEY_Q),
            }
        )
    return data


def serialize_ops_b2b_order(order: B2bOrder) -> dict:
    """OPS order payload — includes internal HAS / labor+stone settlement components."""
    return _serialize_b2b_order(order, for_ops=True)


# ── Storefront B2C Views (/api/v1/storefront/*) ──────────────────────────
class StorefrontCartView(StorefrontScopedPermissionsMixin, APIView):
    def get(self, request: Request):
        return envelope_response(_serialize_b2c_cart(request.user), request)

    def delete(self, request: Request):
        from .dyo import release_stone_soft_lock
        from .models import CustomBundle

        items = list(B2cCartItem.objects.filter(user=request.user).select_related("bundle", "bundle__stone_product"))
        bundle_ids = {i.bundle_id for i in items if i.bundle_id}
        for item in items:
            if item.bundle_id and item.bundle:
                release_stone_soft_lock(stone=item.bundle.stone_product, user=request.user)
        B2cCartItem.objects.filter(user=request.user).delete()
        if bundle_ids:
            CustomBundle.objects.filter(id__in=bundle_ids).update(status=CustomBundle.Status.CANCELLED)
        from .models import CartRecoverySession
        from .recovery import suppress_b2c_cart

        suppress_b2c_cart(
            user=request.user, reason=CartRecoverySession.SuppressReason.EMPTIED
        )
        return envelope_response(_serialize_b2c_cart(request.user), request)


class StorefrontCartItemsView(IdempotentCreateMixin, APIView):
    permission_classes = [IsAuthenticated, HasApiScopeWrite]

    def post(self, request: Request):
        serializer = B2cCartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        add_b2c_cart_item(user=request.user, payload=serializer.validated_data)
        return envelope_response(_serialize_b2c_cart(request.user), request, status=201)


class StorefrontCartItemDetailView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeWrite]

    def patch(self, request: Request, item_id: str):
        item = B2cCartItem.objects.filter(id=item_id, user=request.user).first()
        if item is None:
            raise DomainError("Sepet kalemi bulunamadı.", code="NOT_FOUND", status_code=404)
        serializer = B2cCartItemUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        if item.bundle_id and "qty" in d and d["qty"] != 1:
            raise DomainError(
                "DYO bundle satırında adet değiştirilemez; kaldırın için DELETE /dyo/bundles/{id} kullanın.",
                code="BUNDLE_LINE_IMMUTABLE",
                status_code=409,
            )
        if "qty" in d:
            item.qty = d["qty"]
        if "engravingText" in d:
            item.engraving_text = d["engravingText"]
        if "giftWrap" in d:
            item.gift_wrap = d["giftWrap"]
        if "giftNote" in d:
            item.gift_note = d["giftNote"]
        item.save()
        from .recovery import touch_b2c_cart

        touch_b2c_cart(user=request.user)
        return envelope_response(_serialize_b2c_cart(request.user), request)

    def delete(self, request: Request, item_id: str):
        item = B2cCartItem.objects.filter(id=item_id, user=request.user).first()
        if item is None:
            raise DomainError("Sepet kalemi bulunamadı.", code="NOT_FOUND", status_code=404)
        if item.bundle_id:
            raise DomainError(
                "DYO bundle satırı tek başına silinemez; DELETE /dyo/bundles/{id} veya sepeti temizleyin.",
                code="BUNDLE_LINE_IMMUTABLE",
                status_code=409,
            )
        item.delete()
        from .recovery import touch_b2c_cart

        touch_b2c_cart(user=request.user)
        return envelope_response(_serialize_b2c_cart(request.user), request)


class StorefrontCartRefreshLockView(APIView):
    permission_classes = [IsAuthenticated, HasApiScopeWrite]

    def post(self, request: Request):
        refresh_b2c_cart_price_lock(user=request.user)
        return envelope_response(_serialize_b2c_cart(request.user), request)


class StorefrontOrdersView(IdempotentCreateMixin, StorefrontScopedPermissionsMixin, APIView):
    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = B2cOrder.objects.select_related("customer", "rate_snapshot").prefetch_related("items")
        if not ctx.is_ops:
            qs = qs.filter(created_by=request.user)
        return envelope_response([_serialize_b2c_order(o) for o in qs], request)

    def post(self, request: Request):
        serializer = B2cOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if payload.get("paymentMethod") == "BANK_TRANSFER":
            from apps.payments.bank_transfer import initiate_bank_transfer_checkout

            data = initiate_bank_transfer_checkout(
                user=request.user, payload=payload, request=request
            )
            return envelope_response(data, request, status=201)
        order = submit_b2c_order(user=request.user, payload=payload)
        return envelope_response(_serialize_b2c_order(order), request, status=201)


# ── B2B Tenant-Isolated Views (/api/v1/b2b/*) ────────────────────────────
class B2bDraftView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request):
        ctx = resolve_tenant_context(request, require_organization=True)
        return envelope_response(_serialize_b2b_draft(ctx.organization, ctx.branch), request)

    def delete(self, request: Request):
        ctx = resolve_tenant_context(request, require_organization=True)
        B2bDraftLine.objects.filter(organization=ctx.organization).delete()
        from .models import CartRecoverySession
        from .recovery import suppress_b2b_draft

        suppress_b2b_draft(
            organization=ctx.organization,
            reason=CartRecoverySession.SuppressReason.EMPTIED,
        )
        return envelope_response(_serialize_b2b_draft(ctx.organization, ctx.branch), request)


class B2bDraftLinesView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def post(self, request: Request):
        ctx = resolve_tenant_context(request, require_organization=True)
        is_many = isinstance(request.data, list)
        serializer = B2bDraftLineCreateSerializer(data=request.data, many=is_many)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data if is_many else [serializer.validated_data]
        add_b2b_draft_lines(
            user=request.user, organization=ctx.organization, items=items, is_ops=ctx.is_ops
        )
        return envelope_response(_serialize_b2b_draft(ctx.organization, ctx.branch), request, status=201)


class B2bDraftLineDetailView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def patch(self, request: Request, line_id: str):
        ctx = resolve_tenant_context(request, require_organization=True)
        line = B2bDraftLine.objects.filter(id=line_id, organization=ctx.organization).first()
        if line is None:
            raise DomainError("Sipariş fişi satırı bulunamadı.", code="NOT_FOUND", status_code=404)
        serializer = B2bDraftLineUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        if "qty" in d:
            line.qty = d["qty"]
        if "supplyType" in d:
            line.supply_type = d["supplyType"]
        if "dealerStampNote" in d:
            line.dealer_stamp_note = d["dealerStampNote"]
        line.save()
        from .recovery import touch_b2b_draft

        touch_b2b_draft(user=request.user, organization=ctx.organization)
        return envelope_response(_serialize_b2b_draft(ctx.organization, ctx.branch), request)

    def delete(self, request: Request, line_id: str):
        ctx = resolve_tenant_context(request, require_organization=True)
        B2bDraftLine.objects.filter(id=line_id, organization=ctx.organization).delete()
        from .recovery import touch_b2b_draft

        touch_b2b_draft(user=request.user, organization=ctx.organization)
        return envelope_response(_serialize_b2b_draft(ctx.organization, ctx.branch), request)


class B2bOrdersView(IdempotentCreateMixin, APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request):
        ctx = resolve_tenant_context(request, require_organization=True)
        qs = B2bOrder.objects.select_related(
            "organization", "branch", "created_by", "rate_snapshot"
        ).prefetch_related("lines")
        if not ctx.is_ops:
            qs = qs.filter(organization=ctx.organization)
        return envelope_response([_serialize_b2b_order(o) for o in qs], request)

    def post(self, request: Request):
        ctx = resolve_tenant_context(request, require_organization=True)
        serializer = B2bOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = submit_b2b_order(
            user=request.user,
            organization=ctx.organization,
            branch=ctx.branch,
            payload=serializer.validated_data,
        )
        return envelope_response(_serialize_b2b_order(order), request, status=201)


class B2bOrderReorderView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def post(self, request: Request, order_no: str):
        ctx = resolve_tenant_context(request, require_organization=True)
        reorder_b2b_order(
            order_no=order_no,
            organization=ctx.organization,
            user=request.user,
            is_ops=ctx.is_ops,
        )
        return envelope_response(_serialize_b2b_draft(ctx.organization, ctx.branch), request)


# ── OPS Fulfillment Status Views (/api/v1/ops/*) ─────────────────────────
class OpsB2cOrderStatusView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    def patch(self, request: Request, order_no: str):
        next_status = str(request.data.get("status", "")).strip()
        transition_b2c_order_status(order_no=order_no, next_status=next_status, actor=request.user)
        qs = B2cOrder.objects.select_related("customer", "rate_snapshot").prefetch_related("items")
        return envelope_response([_serialize_b2c_order(o) for o in qs], request)


class OpsB2bOrderStatusView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orders:manage"

    def patch(self, request: Request, order_no: str):
        next_status = str(request.data.get("status", "")).strip()
        transition_b2b_order_status(order_no=order_no, next_status=next_status, actor=request.user)
        qs = B2bOrder.objects.select_related("organization", "branch", "created_by", "rate_snapshot").prefetch_related("lines")
        return envelope_response([_serialize_b2b_order(o) for o in qs], request)


class GuestCartRecoveryLeadSerializer(serializers.Serializer):
    email = serializers.EmailField()
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False, max_length=40)


class StorefrontGuestCartRecoveryLeadView(APIView):
    """Guest cart email capture for abandoned-cart recovery (Faz 1.1)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request):
        from .recovery import capture_guest_cart_lead

        serializer = GuestCartRecoveryLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        session = capture_guest_cart_lead(email=d["email"], items=d["items"])
        if session is None:
            raise DomainError("Geçerli sepet özeti gerekli.", code="INVALID_CART", status_code=400)
        return envelope_response(
            {
                "captured": True,
                "email": session.guest_email,
                "lineCount": session.line_count,
                "cartValueTry": str(session.cart_value_try),
            },
            request,
            status=201,
        )


class B2bDraftProformaPdfView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request):
        from .proforma_pdf import build_text_pdf, draft_proforma_lines

        ctx = resolve_tenant_context(request, require_organization=True)
        lines = list(B2bDraftLine.objects.filter(organization=ctx.organization).order_by("-updated_at"))
        if not lines:
            raise DomainError("Taslak boş — PDF oluşturulamaz.", code="EMPTY_DRAFT", status_code=400)
        snap = get_current_rate_snapshot()
        text_lines = draft_proforma_lines(
            org_name=ctx.organization.name,
            org_code=ctx.organization.code,
            lines=lines,
            gold_rate=_dec_str(snap.live_has_gold_try_sell, MONEY_Q),
        )
        pdf = build_text_pdf(text_lines, title="TARA DIAMOND B2B PROFORMA / TASLAK")
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = 'attachment; filename="taslak-proforma.pdf"'
        return resp


class B2bOrderProformaPdfView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    def get(self, request: Request, order_no: str):
        from .proforma_pdf import build_text_pdf, order_proforma_lines

        ctx = resolve_tenant_context(request, require_organization=True)
        order = (
            B2bOrder.objects.select_related("organization", "branch")
            .prefetch_related("lines")
            .filter(order_no=order_no, organization=ctx.organization)
            .first()
        )
        if order is None:
            raise DomainError("Sipariş bulunamadı.", code="NOT_FOUND", status_code=404)
        pdf = build_text_pdf(order_proforma_lines(order), title="TARA DIAMOND B2B PROFORMA")
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{order.order_no}-proforma.pdf"'
        return resp

from decimal import Decimal
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.catalog.models import ProductModel
from apps.market.matrix_services import get_or_create_active_matrix, serialize_exchange_metal_matrix
from apps.common.responses import (
    GRAM_Q,
    MONEY_Q,
    apply_safe_ordering,
    dec_str,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from config.exceptions import DomainError
from .models import ChannelRule, CostLine, PriceLock, PriceQuote, PricingRecipe


RATE_Q = Decimal("0.000001")


def serialize_ops_cost_line(cl: CostLine) -> dict:
    return {
        "id": str(cl.id),
        "recipeId": str(cl.recipe_id),
        "lineType": cl.line_type,
        "fcCurrency": cl.fc_currency,
        "fcPrice": dec_str(cl.fc_price, MONEY_Q),
        "fcPriceManual": dec_str(cl.fc_price_manual, MONEY_Q),
        "rateOverride": dec_str(cl.rate_override, RATE_Q),
        "createdAt": cl.created_at.isoformat(),
        "updatedAt": cl.updated_at.isoformat(),
    }


def serialize_ops_channel_rule(cr: ChannelRule) -> dict:
    return {
        "id": str(cr.id),
        "recipeId": str(cr.recipe_id),
        "channel": cr.channel,
        "profitUnit": cr.profit_unit,
        "profitValue": dec_str(cr.profit_value, GRAM_Q),
        "discountUnit": cr.discount_unit,
        "discountValue": dec_str(cr.discount_value, GRAM_Q),
        "servisBedeliUnit": cr.servis_bedeli_unit,
        "servisBedeliValue": dec_str(cr.servis_bedeli_value, GRAM_Q),
        "createdAt": cr.created_at.isoformat(),
        "updatedAt": cr.updated_at.isoformat(),
    }


def serialize_ops_recipe(r: PricingRecipe) -> dict:
    return {
        "id": str(r.id),
        "productId": str(r.product_id),
        "parentSku": r.product.parent_sku,
        "productTitle": r.product.title,
        "version": r.version,
        "status": r.status,
        "pricingMode": r.pricing_mode,
        "lcCurrency": r.lc_currency,
        "lastSnapshotId": r.last_snapshot.snapshot_code if r.last_snapshot else None,
        "sourceMatrixId": str(r.source_matrix_id) if r.source_matrix_id else None,
        "sourceMatrixVersion": r.source_matrix_version,
        "appliedRatesSnapshot": r.applied_rates_snapshot or {},
        "appliedAt": r.applied_at.isoformat() if r.applied_at else None,
        "overrideMetadata": r.override_metadata or {},
        "cachedTotalCostLc": dec_str(r.cached_total_cost_lc, MONEY_Q),
        "cachedB2bTry": dec_str(r.cached_b2b_try, MONEY_Q),
        "cachedB2cTry": dec_str(r.cached_b2c_try, MONEY_Q),
        "cachedB2cListTry": dec_str(r.cached_b2c_list_try, MONEY_Q),
        "costLines": [serialize_ops_cost_line(cl) for cl in r.cost_lines.all()],
        "channelRules": [serialize_ops_channel_rule(cr) for cr in r.channel_rules.all()],
        "createdAt": r.created_at.isoformat(),
        "updatedAt": r.updated_at.isoformat(),
    }


def serialize_ops_price_quote(q: PriceQuote) -> dict:
    recipe_status = q.recipe.status if q.recipe_id else None
    is_active = recipe_status == PricingRecipe.Status.PUBLISHED
    return {
        "id": str(q.id),
        "productId": str(q.product_id) if q.product_id else None,
        "parentSku": q.product.parent_sku if q.product_id else q.product_sku,
        "variantId": str(q.variant_id) if q.variant_id else None,
        "variantSku": q.variant.sku if q.variant else None,
        "recipeId": str(q.recipe_id) if q.recipe_id else None,
        "recipeVersion": q.recipe.version if q.recipe_id else None,
        "recipeStatus": recipe_status,
        "isActive": is_active,
        "snapshotId": q.rate_snapshot.snapshot_code,
        "organizationId": str(q.organization_id) if q.organization_id else None,
        "organizationCode": q.organization.code if q.organization else None,
        "channel": q.channel,
        "lcCurrency": q.lc_currency,
        "listPriceTry": dec_str(q.list_price_try, MONEY_Q),
        "finalPriceLc": dec_str(q.final_price_lc, MONEY_Q),
        "finalPriceTry": dec_str(q.final_price_try, MONEY_Q),
        "effectiveDiscountPct": dec_str(q.effective_discount_pct, MONEY_Q),
        "validFrom": q.created_at.isoformat(),
        "validUntil": None,
        "internalAudit": q.internal_audit_json,
        "createdAt": q.created_at.isoformat(),
    }


def serialize_ops_price_lock(lock: PriceLock) -> dict:
    return {
        "id": str(lock.id),
        "userId": str(lock.user_id),
        "userEmail": lock.user.email,
        "snapshotId": lock.rate_snapshot.snapshot_code,
        "expiresAt": lock.expires_at.isoformat(),
        "isActive": lock.is_active,
        "createdAt": lock.created_at.isoformat(),
    }


class OpsRecipeCreateSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32)
    pricingMode = serializers.ChoiceField(choices=PricingRecipe.PricingMode.values, default=PricingRecipe.PricingMode.DETAILED)
    lcCurrency = serializers.CharField(max_length=8, default="TRY")
    appliedRatesSnapshot = serializers.DictField(required=False)
    overrideMetadata = serializers.DictField(required=False)


class OpsRecipeUpdateSerializer(serializers.Serializer):
    pricingMode = serializers.ChoiceField(choices=PricingRecipe.PricingMode.values, required=False)
    lcCurrency = serializers.CharField(max_length=8, required=False)
    status = serializers.ChoiceField(choices=[PricingRecipe.Status.DRAFT, PricingRecipe.Status.ARCHIVED], required=False)
    appliedRatesSnapshot = serializers.DictField(required=False)
    overrideMetadata = serializers.DictField(required=False)


class OpsCostLineCreateSerializer(serializers.Serializer):
    lineType = serializers.ChoiceField(choices=CostLine.LineType.values)
    fcCurrency = serializers.CharField(max_length=8, default="USD")
    fcPrice = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), default=Decimal("0.00"))
    fcPriceManual = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True)
    rateOverride = serializers.DecimalField(max_digits=14, decimal_places=6, min_value=Decimal("0.000001"), required=False, allow_null=True)


class OpsCostLineUpdateSerializer(serializers.Serializer):
    fcCurrency = serializers.CharField(max_length=8, required=False)
    fcPrice = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False)
    fcPriceManual = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True)
    rateOverride = serializers.DecimalField(max_digits=14, decimal_places=6, min_value=Decimal("0.000001"), required=False, allow_null=True)


class OpsChannelRuleCreateSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=ChannelRule.Channel.values)
    profitUnit = serializers.CharField(max_length=8, default="%")
    profitValue = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"), default=Decimal("0.0000"))
    discountUnit = serializers.CharField(max_length=8, default="%")
    discountValue = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"), default=Decimal("0.0000"))
    servisBedeliUnit = serializers.CharField(max_length=8, default="%")
    servisBedeliValue = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"), default=Decimal("0.0000"))


class OpsChannelRuleUpdateSerializer(serializers.Serializer):
    profitUnit = serializers.CharField(max_length=8, required=False)
    profitValue = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False)
    discountUnit = serializers.CharField(max_length=8, required=False)
    discountValue = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False)
    servisBedeliUnit = serializers.CharField(max_length=8, required=False)
    servisBedeliValue = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False)


def _recipes_queryset():
    return PricingRecipe.objects.select_related("product", "last_snapshot").prefetch_related(
        "cost_lines", "channel_rules"
    )


class OpsPricingRecipeListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "POST": "pricing:edit",
    }

    @extend_schema(tags=["OPS - Pricing"], summary="Fiyat reçetelerini listele")
    def get(self, request: Request):
        qs = _recipes_queryset()
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(product__parent_sku=parent_sku)
        status_filter = (request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        mode = (request.query_params.get("pricingMode") or "").strip()
        if mode:
            qs = qs.filter(pricing_mode=mode)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(product__parent_sku__icontains=q) | Q(product__title__icontains=q))
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"version": "version", "updatedAt": "updated_at", "createdAt": "created_at", "cachedB2cTry": "cached_b2c_try"},
            default="-updated_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_recipe)

    @extend_schema(tags=["OPS - Pricing"], summary="Yeni taslak fiyat reçetesi oluştur", request=OpsRecipeCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsRecipeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        product = ProductModel.objects.filter(parent_sku=d["parentSku"].strip().upper()).first()
        if product is None:
            raise DomainError("Ürün modeli bulunamadı.", code="PRODUCT_NOT_FOUND", status_code=404)

        max_ver = PricingRecipe.objects.filter(product=product).aggregate(v=Max("version")).get("v") or 0
        active_matrix = get_or_create_active_matrix(actor=request.user)
        matrix_data = serialize_exchange_metal_matrix(active_matrix)
        snapshot_rates = d.get("appliedRatesSnapshot") or {
            "sourceMatrixId": matrix_data["id"],
            "sourceMatrixVersion": matrix_data["version"],
            "fxBaseRates": matrix_data["fxBaseRates"],
            "liveHasGoldTrySell": matrix_data["liveHasGoldTrySell"],
        }
        recipe = PricingRecipe.objects.create(
            product=product,
            version=max_ver + 1,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode=d["pricingMode"],
            lc_currency=d["lcCurrency"].strip().upper()[:8],
            source_matrix=active_matrix,
            source_matrix_version=active_matrix.version,
            applied_rates_snapshot=snapshot_rates,
            applied_at=timezone.now(),
            override_metadata=d.get("overrideMetadata") or {},
        )
        record_audit(
            action="OPS_PRICING_RECIPE_CREATED",
            entity_type="PricingRecipe",
            entity_id=str(recipe.id),
            actor=request.user,
            metadata={"parent_sku": product.parent_sku, "version": recipe.version},
        )
        recipe = _recipes_queryset().get(id=recipe.id)
        return envelope_response(serialize_ops_recipe(recipe), request, status=201)


class OpsPricingRecipeDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "PATCH": "pricing:edit",
        "DELETE": "pricing:edit",
    }

    @extend_schema(tags=["OPS - Pricing"], summary="Fiyat reçetesi detayını getir")
    def get(self, request: Request, recipe_id: str):
        recipe = _recipes_queryset().filter(id=recipe_id).first()
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_recipe(recipe), request)

    @extend_schema(tags=["OPS - Pricing"], summary="Fiyat reçetesini güncelle", request=OpsRecipeUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, recipe_id: str):
        recipe = PricingRecipe.objects.select_for_update().select_related("product").filter(id=recipe_id).first()
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)

        serializer = OpsRecipeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "pricingMode" in d:
            recipe.pricing_mode = d["pricingMode"]
        if "lcCurrency" in d:
            recipe.lc_currency = d["lcCurrency"].strip().upper()[:8]
        if "status" in d:
            recipe.status = d["status"]
        if "appliedRatesSnapshot" in d:
            if recipe.status == PricingRecipe.Status.PUBLISHED:
                raise DomainError(
                    "Yayınlanmış fiyat reçetesinin snapshot değerleri değiştirilemez; yeni sürüm oluşturun.",
                    code="RECIPE_IMMUTABLE",
                    status_code=400,
                )
            recipe.applied_rates_snapshot = d["appliedRatesSnapshot"]
            recipe.applied_at = timezone.now()
        if "overrideMetadata" in d:
            recipe.override_metadata = d["overrideMetadata"]
        recipe.save()

        record_audit(
            action="OPS_PRICING_RECIPE_UPDATED",
            entity_type="PricingRecipe",
            entity_id=str(recipe.id),
            actor=request.user,
            metadata={"parent_sku": recipe.product.parent_sku, "status": recipe.status},
        )
        recipe = _recipes_queryset().get(id=recipe.id)
        return envelope_response(serialize_ops_recipe(recipe), request)

    @extend_schema(tags=["OPS - Pricing"], summary="Fiyat reçetesini arşivle (PASIF)")
    @transaction.atomic
    def delete(self, request: Request, recipe_id: str):
        recipe = PricingRecipe.objects.select_for_update().select_related("product").filter(id=recipe_id).first()
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)
        recipe.status = PricingRecipe.Status.ARCHIVED
        recipe.save(update_fields=["status", "updated_at"])
        record_audit(
            action="OPS_PRICING_RECIPE_ARCHIVED",
            entity_type="PricingRecipe",
            entity_id=str(recipe.id),
            actor=request.user,
        )
        return envelope_response({"id": str(recipe.id), "status": recipe.status}, request)


class OpsCostLineListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "POST": "pricing:edit",
    }

    @extend_schema(tags=["OPS - Pricing"], summary="Reçete maliyet kalemlerini listele")
    def get(self, request: Request, recipe_id: str):
        recipe = PricingRecipe.objects.filter(id=recipe_id).first()
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)
        lines = CostLine.objects.filter(recipe=recipe).order_by("line_type")
        return envelope_response([serialize_ops_cost_line(cl) for cl in lines], request)

    @extend_schema(tags=["OPS - Pricing"], summary="Reçeteye maliyet kalemi ekle veya güncelle", request=OpsCostLineCreateSerializer)
    @transaction.atomic
    def post(self, request: Request, recipe_id: str):
        recipe = PricingRecipe.objects.select_for_update().filter(id=recipe_id).first()
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)

        serializer = OpsCostLineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        cl, created = CostLine.objects.update_or_create(
            recipe=recipe,
            line_type=d["lineType"],
            defaults={
                "fc_currency": d["fcCurrency"].strip().upper()[:8],
                "fc_price": d["fcPrice"],
                "fc_price_manual": d.get("fcPriceManual"),
                "rate_override": d.get("rateOverride"),
            },
        )
        record_audit(
            action="OPS_COST_LINE_UPSERTED",
            entity_type="CostLine",
            entity_id=str(cl.id),
            actor=request.user,
            metadata={"recipe_id": str(recipe.id), "line_type": cl.line_type, "created": created},
        )
        return envelope_response(serialize_ops_cost_line(cl), request, status=201 if created else 200)


class OpsCostLineDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "PATCH": "pricing:edit",
        "DELETE": "pricing:edit",
    }

    @extend_schema(tags=["OPS - Pricing"], summary="Maliyet kalemi detayını getir")
    def get(self, request: Request, cost_line_id: str):
        cl = CostLine.objects.filter(id=cost_line_id).first()
        if cl is None:
            raise DomainError("Maliyet kalemi bulunamadı.", code="COST_LINE_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_cost_line(cl), request)

    @extend_schema(tags=["OPS - Pricing"], summary="Maliyet kalemini güncelle", request=OpsCostLineUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, cost_line_id: str):
        cl = CostLine.objects.select_for_update().filter(id=cost_line_id).first()
        if cl is None:
            raise DomainError("Maliyet kalemi bulunamadı.", code="COST_LINE_NOT_FOUND", status_code=404)
        serializer = OpsCostLineUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "fcCurrency" in d:
            cl.fc_currency = d["fcCurrency"].strip().upper()[:8]
        if "fcPrice" in d:
            cl.fc_price = d["fcPrice"]
        if "fcPriceManual" in d:
            cl.fc_price_manual = d["fcPriceManual"]
        if "rateOverride" in d:
            cl.rate_override = d["rateOverride"]
        cl.save()
        record_audit(
            action="OPS_COST_LINE_UPDATED",
            entity_type="CostLine",
            entity_id=str(cl.id),
            actor=request.user,
            metadata={"recipe_id": str(cl.recipe_id), "line_type": cl.line_type},
        )
        return envelope_response(serialize_ops_cost_line(cl), request)

    @extend_schema(tags=["OPS - Pricing"], summary="Maliyet kalemini sil")
    @transaction.atomic
    def delete(self, request: Request, cost_line_id: str):
        cl = CostLine.objects.select_for_update().filter(id=cost_line_id).first()
        if cl is None:
            raise DomainError("Maliyet kalemi bulunamadı.", code="COST_LINE_NOT_FOUND", status_code=404)
        recipe_id = str(cl.recipe_id)
        cl.delete()
        record_audit(
            action="OPS_COST_LINE_DELETED",
            entity_type="CostLine",
            entity_id=str(cost_line_id),
            actor=request.user,
            metadata={"recipe_id": recipe_id},
        )
        return envelope_response({"id": str(cost_line_id), "deleted": True}, request)


class OpsChannelRuleListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "POST": "pricing:edit",
    }

    @extend_schema(tags=["OPS - Pricing"], summary="Reçete kanal kurallarını listele")
    def get(self, request: Request, recipe_id: str):
        recipe = PricingRecipe.objects.filter(id=recipe_id).first()
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)
        rules = ChannelRule.objects.filter(recipe=recipe).order_by("channel")
        return envelope_response([serialize_ops_channel_rule(cr) for cr in rules], request)

    @extend_schema(tags=["OPS - Pricing"], summary="Reçeteye kanal kuralı ekle veya güncelle", request=OpsChannelRuleCreateSerializer)
    @transaction.atomic
    def post(self, request: Request, recipe_id: str):
        recipe = PricingRecipe.objects.select_for_update().filter(id=recipe_id).first()
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)

        serializer = OpsChannelRuleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        cr, created = ChannelRule.objects.update_or_create(
            recipe=recipe,
            channel=d["channel"],
            defaults={
                "profit_unit": d["profitUnit"].strip()[:8],
                "profit_value": d["profitValue"],
                "discount_unit": d["discountUnit"].strip()[:8],
                "discount_value": d["discountValue"],
                "servis_bedeli_unit": d["servisBedeliUnit"].strip()[:8],
                "servis_bedeli_value": d["servisBedeliValue"],
            },
        )
        record_audit(
            action="OPS_CHANNEL_RULE_UPSERTED",
            entity_type="ChannelRule",
            entity_id=str(cr.id),
            actor=request.user,
            metadata={"recipe_id": str(recipe.id), "channel": cr.channel, "created": created},
        )
        return envelope_response(serialize_ops_channel_rule(cr), request, status=201 if created else 200)


class OpsChannelRuleDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "PATCH": "pricing:edit",
        "DELETE": "pricing:edit",
    }

    @extend_schema(tags=["OPS - Pricing"], summary="Kanal kuralı detayını getir")
    def get(self, request: Request, rule_id: str):
        cr = ChannelRule.objects.filter(id=rule_id).first()
        if cr is None:
            raise DomainError("Kanal kuralı bulunamadı.", code="CHANNEL_RULE_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_channel_rule(cr), request)

    @extend_schema(tags=["OPS - Pricing"], summary="Kanal kuralını güncelle", request=OpsChannelRuleUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, rule_id: str):
        cr = ChannelRule.objects.select_for_update().filter(id=rule_id).first()
        if cr is None:
            raise DomainError("Kanal kuralı bulunamadı.", code="CHANNEL_RULE_NOT_FOUND", status_code=404)
        serializer = OpsChannelRuleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        field_map = {
            "profitUnit": "profit_unit",
            "profitValue": "profit_value",
            "discountUnit": "discount_unit",
            "discountValue": "discount_value",
            "servisBedeliUnit": "servis_bedeli_unit",
            "servisBedeliValue": "servis_bedeli_value",
        }
        for api_key, model_field in field_map.items():
            if api_key in d:
                val = d[api_key].strip()[:8] if isinstance(d[api_key], str) else d[api_key]
                setattr(cr, model_field, val)
        cr.save()
        record_audit(
            action="OPS_CHANNEL_RULE_UPDATED",
            entity_type="ChannelRule",
            entity_id=str(cr.id),
            actor=request.user,
            metadata={"recipe_id": str(cr.recipe_id), "channel": cr.channel},
        )
        return envelope_response(serialize_ops_channel_rule(cr), request)

    @extend_schema(tags=["OPS - Pricing"], summary="Kanal kuralını sil")
    @transaction.atomic
    def delete(self, request: Request, rule_id: str):
        cr = ChannelRule.objects.select_for_update().filter(id=rule_id).first()
        if cr is None:
            raise DomainError("Kanal kuralı bulunamadı.", code="CHANNEL_RULE_NOT_FOUND", status_code=404)
        recipe_id = str(cr.recipe_id)
        cr.delete()
        record_audit(
            action="OPS_CHANNEL_RULE_DELETED",
            entity_type="ChannelRule",
            entity_id=str(rule_id),
            actor=request.user,
            metadata={"recipe_id": recipe_id},
        )
        return envelope_response({"id": str(rule_id), "deleted": True}, request)


class OpsPriceQuoteListView(APIView):
    """Strictly read-only audit inspection of immutable PriceQuotes."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:read"

    @extend_schema(tags=["OPS - Pricing"], summary="Oluşturulmuş immutable fiyat tekliflerini listele")
    def get(self, request: Request):
        qs = PriceQuote.objects.select_related("product", "variant", "recipe", "rate_snapshot", "organization")
        parent_sku = (request.query_params.get("parentSku") or "").strip().upper()
        if parent_sku:
            qs = qs.filter(product__parent_sku=parent_sku)
        channel = (request.query_params.get("channel") or "").strip().upper()
        if channel:
            qs = qs.filter(channel=channel)
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        snapshot_id = (request.query_params.get("snapshotId") or "").strip()
        if snapshot_id:
            qs = qs.filter(rate_snapshot__snapshot_code=snapshot_id)

        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "finalPriceTry": "final_price_try"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_price_quote)


class OpsPriceLockListView(APIView):
    """Read-only inspection of B2C 15-minute PriceLocks."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:read"

    @extend_schema(tags=["OPS - Pricing"], summary="B2C fiyat kilitlerini listele")
    def get(self, request: Request):
        qs = PriceLock.objects.select_related("user", "rate_snapshot")
        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        user_id = (request.query_params.get("userId") or "").strip()
        if user_id:
            qs = qs.filter(user_id=user_id)

        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "expiresAt": "expires_at"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_price_lock)

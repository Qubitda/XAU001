from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q
from rest_framework import permissions, serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.authorization.permissions import HasPortalPermission
from apps.catalog.models import ProductModel, ProductVariant
from apps.common.responses import envelope_response
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError
from .models import PricingRecipe
from .services import create_live_quote, evaluate_recipe, publish_recipe, resolve_product_variant


MONEY_Q = Decimal("0.01")
GRAM_Q = Decimal("0.0001")
PCT_Q = Decimal("0.01")


def _dec_str(val: Decimal | None, q: Decimal) -> str | None:
    if val is None:
        return None
    return str(Decimal(val).quantize(q, rounding=ROUND_HALF_UP))


class BuyerQuoteRequestSerializer(serializers.Serializer):
    parentSku = serializers.CharField(max_length=32, required=False, allow_blank=True)
    variantId = serializers.UUIDField(required=False)
    variantSku = serializers.CharField(max_length=64, required=False, allow_blank=True)
    purityCode = serializers.ChoiceField(choices=["8K", "14K", "18K", "22K", "925"], required=False)
    metalColor = serializers.ChoiceField(choices=["Beyaz", "Sarı", "Rose"], required=False)
    channel = serializers.ChoiceField(choices=["B2B", "B2B_API", "B2C_API", "B2C"])
    size = serializers.IntegerField(min_value=0, max_value=70, required=False)

    def validate(self, attrs):
        if not attrs.get("parentSku") and not attrs.get("variantId") and not attrs.get("variantSku"):
            raise serializers.ValidationError(
                "parentSku, variantId veya variantSku alanlarından en az biri zorunludur."
            )
        return attrs


class BuyerQuoteCreateView(APIView):
    """
    Generates an immutable PriceQuote from the live RateSnapshot + published PricingRecipe
    for a specific sellable ProductVariant.
    Strict blind-pool response: zero cost/fire/profit fields. All Decimals serialized as strings.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request: Request):
        serializer = BuyerQuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        channel = d["channel"]

        organization = None
        is_ops = False
        if channel == "B2B":
            ctx = resolve_tenant_context(request, require_organization=True)
            organization = ctx.organization
            is_ops = ctx.is_ops
        elif request.user and request.user.is_authenticated:
            ctx = resolve_tenant_context(request, require_organization=False)
            organization = ctx.organization
            is_ops = ctx.is_ops

        variant_obj: ProductVariant | None = None
        product: ProductModel | None = None

        if d.get("variantId"):
            variant_obj = (
                ProductVariant.objects.select_related("product")
                .filter(id=d["variantId"], is_active=True)
                .first()
            )
            if variant_obj is None:
                raise DomainError("Varyant bulunamadı.", code="VARIANT_NOT_FOUND", status_code=404)
            product = variant_obj.product
        elif d.get("variantSku"):
            variant_obj = (
                ProductVariant.objects.select_related("product")
                .filter(sku__iexact=d["variantSku"].strip(), is_active=True)
                .first()
            )
            if variant_obj is None:
                raise DomainError("Varyant SKU bulunamadı.", code="VARIANT_NOT_FOUND", status_code=404)
            product = variant_obj.product
        else:
            product = ProductModel.objects.filter(
                parent_sku=d["parentSku"].strip().upper()
            ).first()
            if product is None:
                raise DomainError("Ürün bulunamadı.", code="PRODUCT_NOT_FOUND", status_code=404)

        # Catalog ownership visibility guard
        if product.owner_organization_id is not None and not is_ops:
            if organization is None or product.owner_organization_id != organization.id:
                raise DomainError("Bu katalog ürününe erişim yetkiniz bulunmuyor.", code="PRODUCT_NOT_FOUND", status_code=404)

        quote, output = create_live_quote(
            product=product,
            channel=channel,
            variant=variant_obj,
            purity_code=d.get("purityCode"),
            metal_color=d.get("metalColor"),
            organization=organization,
            size=d.get("size"),
        )
        resolved_variant = quote.variant
        resolved_size = d.get("size") or (resolved_variant.size if resolved_variant else product.variant_size)

        return envelope_response(
            {
                "quoteId": str(quote.id),
                "parentSku": product.parent_sku,
                "variantId": str(resolved_variant.id) if resolved_variant else None,
                "variantSku": resolved_variant.sku if resolved_variant else product.parent_sku,
                "purityCode": resolved_variant.purity_code if resolved_variant else product.purity_code,
                "metalColor": resolved_variant.metal_color if resolved_variant else product.metal_color,
                "grossWeightGram": _dec_str(
                    Decimal(str(quote.internal_audit_json.get("gross_weight_gram", product.gross_weight_gram))),
                    GRAM_Q,
                ),
                "channel": quote.channel,
                "size": resolved_size,
                "lcCurrency": quote.lc_currency,
                "listPriceTry": _dec_str(quote.list_price_try, MONEY_Q),
                "finalPriceLc": _dec_str(quote.final_price_lc, MONEY_Q),
                "finalPriceTry": _dec_str(quote.final_price_try, MONEY_Q),
                "effectiveDiscountPct": _dec_str(quote.effective_discount_pct, PCT_Q),
                "snapshotId": quote.rate_snapshot.snapshot_code,
            },
            request,
            status=201,
        )


class OpsRecipeEvaluateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:edit"

    def post(self, request: Request, recipe_id: str):
        recipe = (
            PricingRecipe.objects.filter(id=recipe_id)
            .select_related("product")
            .prefetch_related("cost_lines", "channel_rules", "product__stone_lines")
            .first()
        )
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)

        variant = resolve_product_variant(
            recipe.product,
            variant_id=request.data.get("variantId"),
            variant_sku=request.data.get("variantSku"),
            purity_code=request.data.get("purityCode"),
            metal_color=request.data.get("metalColor"),
        )
        out = evaluate_recipe(recipe, variant=variant)
        return envelope_response(
            {
                "recipeId": str(recipe.id),
                "variantId": str(variant.id) if variant else None,
                "variantSku": variant.sku if variant else None,
                "lcCurrency": out.lc_currency,
                "netMetalGram": _dec_str(out.net_metal_gram, GRAM_Q),
                "fineMetalGram": _dec_str(out.fine_metal_gram, GRAM_Q),
                "fireIncludedFineMetalGram": _dec_str(out.fire_included_fine_metal_gram, GRAM_Q),
                "isCaratWithinMountRange": out.is_carat_within_mount_range,
                "totalCostLc": _dec_str(out.total_cost_lc, MONEY_Q),
                "lines": {
                    k: {
                        "fcCurrency": v.fc_currency,
                        "fcPrice": _dec_str(v.fc_price, GRAM_Q),
                        "effectiveRate": _dec_str(v.effective_rate, GRAM_Q),
                        "isRateOverridden": v.is_rate_overridden,
                        "lcPrice": _dec_str(v.lc_price, MONEY_Q),
                    }
                    for k, v in out.lines.items()
                },
                "channels": {
                    k: {
                        "profitLc": _dec_str(c.profit_lc, MONEY_Q),
                        "discountLc": _dec_str(c.discount_lc, MONEY_Q),
                        "netSatisLc": _dec_str(c.net_satis_lc, MONEY_Q),
                        "servisBedeliLc": _dec_str(c.servis_bedeli_lc, MONEY_Q),
                        "nihaiFiyatLc": _dec_str(c.nihai_fiyat_lc, MONEY_Q),
                        "nihaiFiyatTry": _dec_str(c.nihai_fiyat_try, MONEY_Q),
                        "listeFiyatiTry": _dec_str(c.liste_fiyati_try, MONEY_Q),
                    }
                    for k, c in out.channels.items()
                },
            },
            request,
        )


class OpsRecipePublishView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:edit"

    def post(self, request: Request, recipe_id: str):
        recipe = (
            PricingRecipe.objects.filter(id=recipe_id)
            .select_related("product")
            .prefetch_related("cost_lines", "channel_rules", "product__stone_lines")
            .first()
        )
        if recipe is None:
            raise DomainError("Fiyat reçetesi bulunamadı.", code="RECIPE_NOT_FOUND", status_code=404)
        published, out = publish_recipe(recipe, actor=request.user)
        return envelope_response(
            {
                "recipeId": str(published.id),
                "status": published.status,
                "version": published.version,
                "totalCostLc": _dec_str(out.total_cost_lc, MONEY_Q),
                "b2bFinalTry": _dec_str(published.cached_b2b_try, MONEY_Q),
                "b2cFinalTry": _dec_str(published.cached_b2c_try, MONEY_Q),
            },
            request,
        )

"""Pricing recipe draft/clone/sync for product ledger updates."""
from decimal import Decimal

from apps.pricing.models import ChannelRule, CostLine, PricingRecipe
from apps.pricing.services import publish_recipe
from apps.catalog.models import ProductModel

def _clone_recipe_as_draft(source: PricingRecipe) -> PricingRecipe:
    """Immutable publish trail: clone published/archived recipe into a new DRAFT version."""
    from django.db.models import Max

    max_version = (
        PricingRecipe.objects.filter(product_id=source.product_id).aggregate(v=Max("version"))["v"] or 0
    )
    draft = PricingRecipe.objects.create(
        product=source.product,
        version=max_version + 1,
        status=PricingRecipe.Status.DRAFT,
        pricing_mode=source.pricing_mode,
        lc_currency=source.lc_currency,
    )
    CostLine.objects.bulk_create(
        [
            CostLine(
                recipe=draft,
                line_type=cl.line_type,
                fc_currency=cl.fc_currency,
                fc_price=cl.fc_price,
                fc_price_manual=cl.fc_price_manual,
                rate_override=cl.rate_override,
            )
            for cl in source.cost_lines.all()
        ]
    )
    ChannelRule.objects.bulk_create(
        [
            ChannelRule(
                recipe=draft,
                channel=cr.channel,
                profit_unit=cr.profit_unit,
                profit_value=cr.profit_value,
                discount_unit=cr.discount_unit,
                discount_value=cr.discount_value,
                servis_bedeli_unit=cr.servis_bedeli_unit,
                servis_bedeli_value=cr.servis_bedeli_value,
            )
            for cr in source.channel_rules.all()
        ]
    )
    return draft


def _editable_recipe_for_product(product: ProductModel, *, pricing_mode: str | None) -> PricingRecipe:
    """
    Never mutate a PUBLISHED recipe in place.
    Prefer an existing DRAFT; otherwise clone the published recipe into a new version.
    """
    draft = (
        PricingRecipe.objects.filter(product=product, status=PricingRecipe.Status.DRAFT)
        .prefetch_related("cost_lines", "channel_rules")
        .order_by("-version")
        .first()
    )
    if draft is not None:
        return draft

    published = (
        PricingRecipe.objects.filter(product=product, status=PricingRecipe.Status.PUBLISHED)
        .prefetch_related("cost_lines", "channel_rules")
        .first()
    )
    if published is not None:
        return _clone_recipe_as_draft(published)

    return PricingRecipe.objects.create(
        product=product,
        version=1,
        status=PricingRecipe.Status.DRAFT,
        pricing_mode=pricing_mode or "1",
    )


def _sync_recipe_from_ledger(*, product: ProductModel, pricing_mode: str | None, ledger: dict | None, actor) -> PricingRecipe:
    recipe = _editable_recipe_for_product(product, pricing_mode=pricing_mode)

    if pricing_mode in ("1", "2"):
        recipe.pricing_mode = pricing_mode
    if ledger:
        if "lcCurrency" in ledger:
            recipe.lc_currency = str(ledger["lcCurrency"]).upper()[:8]
        recipe.save()

        def _upsert_cost(lt: str, cur_key: str, price_key: str | None, rate_key: str, manual_key: str | None = None):
            defaults: dict = {}
            if cur_key in ledger:
                defaults["fc_currency"] = str(ledger[cur_key]).upper()[:8]
            if rate_key in ledger:
                defaults["rate_override"] = ledger[rate_key]
            if price_key is not None and price_key in ledger:
                defaults["fc_price"] = ledger[price_key] if ledger[price_key] is not None else Decimal("0")
            if manual_key is not None and manual_key in ledger:
                defaults["fc_price_manual"] = ledger[manual_key]
            if not defaults:
                return
            existing = CostLine.objects.filter(recipe=recipe, line_type=lt).first()
            if existing is None and "fc_currency" not in defaults:
                defaults["fc_currency"] = "USD"
            CostLine.objects.update_or_create(recipe=recipe, line_type=lt, defaults=defaults)

        _upsert_cost(CostLine.LineType.MADEN, "metalCurrency", None, "metalRateOverride", "metalFcManual")
        _upsert_cost(CostLine.LineType.ISCILIK, "laborCurrency", "laborFcPrice", "laborRateOverride")
        _upsert_cost(CostLine.LineType.TAS, "stoneCurrency", "stoneFcPrice", "stoneRateOverride")
        _upsert_cost(CostLine.LineType.MONTUR, "mountingCurrency", "mountingFcPrice", "mountingRateOverride")
        _upsert_cost(CostLine.LineType.DIGER, "otherCostCurrency", "otherCostFcPrice", "otherCostRateOverride")
        _upsert_cost(CostLine.LineType.TEDARIKCI, "supplierCurrency", "supplierFcPrice", "supplierRateOverride")

        incoming_rules = ledger.get("channelRules")
        if isinstance(incoming_rules, list) and len(incoming_rules) > 0:
            recipe.channel_rules.all().delete()
            seen_channels: set[str] = set()
            for r in incoming_rules:
                ch = str(r.get("channel", "")).upper()
                if ch == "B2C":
                    ch = "B2C_API"
                if ch not in ("B2B", "B2B_API", "B2C_API") or ch in seen_channels:
                    continue
                seen_channels.add(ch)
                profit = r.get("profit") or {}
                discount = r.get("discount") or {}
                fee = r.get("platformFee") or r.get("servisBedeli") or {}
                ChannelRule.objects.create(
                    recipe=recipe,
                    channel=ch,
                    profit_unit=str(profit.get("unit", "%"))[:8],
                    profit_value=profit.get("value") if profit.get("value") is not None else Decimal("0"),
                    discount_unit=str(discount.get("unit", "%"))[:8],
                    discount_value=discount.get("value") if discount.get("value") is not None else Decimal("0"),
                    servis_bedeli_unit=str(fee.get("unit", "%"))[:8],
                    servis_bedeli_value=fee.get("value") if fee.get("value") is not None else Decimal("0"),
                )
    else:
        recipe.save()

    return recipe

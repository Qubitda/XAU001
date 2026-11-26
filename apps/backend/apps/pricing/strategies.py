"""
Type-based pricing strategies when PRICING_READ_FROM_DETAILS is enabled.

FINISHED  → (weight × fineness × has) + labor + fixed stone USD
MOUNTING  → (net_weight × fineness × has) + labor
LOOSE_STONE → net_cost_usd × USD rate (+ channel margins via ChannelRule)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.catalog.models import FinishedDetail, LooseStoneDetail, MountingDetail, ProductModel
from apps.catalog.product_kinds import FINISHED, LOOSE_STONE, MOUNTING, normalize_product_kind
from apps.pricing.engine import (
    CostLineInput,
    MountRangeInput,
    PricingEngineInput,
    PURITY_FINENESS,
    ZERO,
)

ONE = Decimal("1")


def _labor_fc(labor_type: str, labor_value: Decimal, weight_gr: Decimal) -> Decimal:
    if labor_type == ProductModel.LaborCostType.PER_GRAM:
        return max(ZERO, weight_gr * labor_value)
    return max(ZERO, labor_value)


def build_input_from_details(
    product: ProductModel,
    *,
    base: PricingEngineInput,
) -> tuple[PricingEngineInput, dict[str, Any]]:
    """
    Rewrite PricingEngineInput using type detail tables.
    Returns (input, extras) where extras may include pureGoldEquivalent / laborOnlyUsd.
    """
    kind = normalize_product_kind(product.product_kind)
    extras: dict[str, Any] = {"productKind": kind}

    if kind == FINISHED:
        detail = FinishedDetail.objects.filter(product=product).first()
        if detail is None:
            return base, extras
        weight = detail.base_weight_gr
        purity = detail.purity_code
        fineness = detail.fineness or PURITY_FINENESS.get(purity, Decimal("0.585"))
        labor_fc = _labor_fc(detail.labor_cost_type, detail.labor_cost_value, weight)
        pure = weight * fineness
        extras["pureGoldEquivalent"] = pure
        extras["laborOnlyUsd"] = labor_fc
        extras["fineness"] = fineness

        cost_lines = [
            CostLineInput(line_type="MADEN", fc_currency="USD", fc_price=ZERO),
            CostLineInput(line_type="ISCILIK", fc_currency="USD", fc_price=labor_fc),
            CostLineInput(
                line_type="TAS",
                fc_currency="USD",
                fc_price=detail.fixed_stone_cost_usd or ZERO,
            ),
            CostLineInput(line_type="MONTUR", fc_currency="USD", fc_price=ZERO),
            CostLineInput(line_type="DIGER", fc_currency="TRY", fc_price=ZERO),
        ]
        # Keep TEDARIKCI if Mode 2
        if base.pricing_mode == "2":
            cost_lines = list(base.cost_lines)

        return (
            PricingEngineInput(
                pricing_mode=base.pricing_mode,
                lc_currency=base.lc_currency,
                purity_code=purity,
                gross_weight_gram=weight,
                fire_rate_pct=detail.fire_rate_pct,
                has_gold_try_per_gram=base.has_gold_try_per_gram,
                fx_base_rates=base.fx_base_rates,
                stone_lines=base.stone_lines,
                cost_lines=cost_lines if base.pricing_mode == "1" else base.cost_lines,
                channel_rules=base.channel_rules,
                mount_range=base.mount_range,
                enforce_mount_range=base.enforce_mount_range,
            ),
            extras,
        )

    if kind == MOUNTING:
        detail = MountingDetail.objects.filter(product=product).first()
        if detail is None:
            return base, extras
        weight = detail.net_weight_gr
        purity = detail.purity_code
        fineness = detail.fineness or PURITY_FINENESS.get(purity, Decimal("0.585"))
        labor_fc = _labor_fc(detail.labor_cost_type, detail.labor_cost_value, weight)
        pure = weight * fineness
        extras["pureGoldEquivalent"] = pure
        extras["laborOnlyUsd"] = labor_fc
        extras["fineness"] = fineness
        mount_range = MountRangeInput(
            structure=detail.mount_structure,  # type: ignore[arg-type]
            allowed_carat_min=detail.min_carat or Decimal("0"),
            allowed_carat_max=detail.max_carat or Decimal("99"),
        )
        cost_lines = [
            CostLineInput(line_type="MADEN", fc_currency="USD", fc_price=ZERO),
            CostLineInput(line_type="ISCILIK", fc_currency="USD", fc_price=labor_fc),
            CostLineInput(line_type="TAS", fc_currency="USD", fc_price=ZERO),
            CostLineInput(line_type="MONTUR", fc_currency="USD", fc_price=ZERO),
            CostLineInput(line_type="DIGER", fc_currency="TRY", fc_price=ZERO),
        ]
        return (
            PricingEngineInput(
                pricing_mode="1" if base.pricing_mode == "1" else base.pricing_mode,
                lc_currency=base.lc_currency,
                purity_code=purity,
                gross_weight_gram=weight,
                fire_rate_pct=ZERO,
                has_gold_try_per_gram=base.has_gold_try_per_gram,
                fx_base_rates=base.fx_base_rates,
                stone_lines=(),
                cost_lines=cost_lines if base.pricing_mode == "1" else base.cost_lines,
                channel_rules=base.channel_rules,
                mount_range=mount_range,
                enforce_mount_range=base.enforce_mount_range,
            ),
            extras,
        )

    # LOOSE_STONE
    detail = LooseStoneDetail.objects.filter(product=product).first()
    if detail is None:
        return base, extras
    extras["laborOnlyUsd"] = ZERO
    extras["pureGoldEquivalent"] = ZERO
    stone_cost = detail.net_cost_usd or ZERO
    # Mode 2 single-line supplier price in USD
    cost_lines = [
        CostLineInput(line_type="TEDARIKCI", fc_currency="USD", fc_price=stone_cost),
    ]
    return (
        PricingEngineInput(
            pricing_mode="2",
            lc_currency=base.lc_currency,
            purity_code=base.purity_code or "14K",
            gross_weight_gram=ONE,
            fire_rate_pct=ZERO,
            has_gold_try_per_gram=base.has_gold_try_per_gram,
            fx_base_rates=base.fx_base_rates,
            stone_lines=(),
            cost_lines=cost_lines,
            channel_rules=base.channel_rules,
            mount_range=None,
            enforce_mount_range=False,
        ),
        extras,
    )

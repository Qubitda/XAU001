from decimal import Decimal

from django.test import SimpleTestCase

from apps.pricing.engine import (
    AdjustmentInput,
    ChannelRuleInput,
    CostLineInput,
    PricingEngineInput,
    calculate_pricing,
)


class DyoBundlePricingCompositionTests(SimpleTestCase):
    """Pure engine check: TEDARIKCI base = mount+stone+setting composed TRY."""

    def test_composed_base_applies_all_channels(self):
        base = Decimal("10000.00")
        out = calculate_pricing(
            PricingEngineInput(
                pricing_mode="2",
                lc_currency="TRY",
                purity_code="14K",
                gross_weight_gram=Decimal("1"),
                fire_rate_pct=Decimal("0"),
                has_gold_try_per_gram=Decimal("3000"),
                fx_base_rates={"TRY": Decimal("1"), "USD": Decimal("34")},
                stone_lines=(),
                cost_lines=[CostLineInput(line_type="TEDARIKCI", fc_currency="TRY", fc_price=base)],
                channel_rules=[
                    ChannelRuleInput(
                        channel="B2B",
                        profit=AdjustmentInput("%", Decimal("10")),
                        discount=AdjustmentInput("%", Decimal("0")),
                        servis_bedeli=AdjustmentInput("%", Decimal("0")),
                    ),
                    ChannelRuleInput(
                        channel="B2B_API",
                        profit=AdjustmentInput("%", Decimal("12")),
                        discount=AdjustmentInput("%", Decimal("0")),
                        servis_bedeli=AdjustmentInput("%", Decimal("0")),
                    ),
                    ChannelRuleInput(
                        channel="B2C_API",
                        profit=AdjustmentInput("%", Decimal("40")),
                        discount=AdjustmentInput("%", Decimal("0")),
                        servis_bedeli=AdjustmentInput("%", Decimal("2")),
                    ),
                ],
            )
        )
        self.assertEqual(out.total_cost_lc, base)
        self.assertEqual(out.resolve_channel("B2B").nihai_fiyat_try, Decimal("11000.00"))
        self.assertEqual(out.resolve_channel("B2B_API").nihai_fiyat_try, Decimal("11200.00"))
        # 10000 * 1.40 + 10000 * 0.02 = 14200
        self.assertEqual(out.resolve_channel("B2C_API").nihai_fiyat_try, Decimal("14200.00"))

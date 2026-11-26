from decimal import Decimal
import unittest
from apps.pricing.engine import (
    AdjustmentInput,
    ChannelRuleInput,
    CostLineInput,
    MissingRateError,
    MountCaratRangeError,
    MountRangeInput,
    PricingEngineInput,
    StoneLineInput,
    calculate_pricing,
)

BASE_FX: dict[str, Decimal] = {
    "TRY": Decimal("1"),
    "USD": Decimal("42.00"),
    "EUR": Decimal("48.50"),
    "JPY": Decimal("0.28"),
    "GBP": Decimal("56.00"),
    "CNY": Decimal("5.80"),
    "AUD": Decimal("27.30"),
    "CAD": Decimal("30.40"),
    "CHF": Decimal("52.00"),
    "XAU": Decimal("168000.00"),
    "XAG": Decimal("1470.00"),
    "XPT": Decimal("42000.00"),
    "XPD": Decimal("44100.00"),
}


class PricingEngineTests(unittest.TestCase):
    def test_se009_detailed_mode_multi_stone_count_and_channels(self):
        out = calculate_pricing(
            PricingEngineInput(
                pricing_mode="1",
                lc_currency="TRY",
                purity_code="14K",
                gross_weight_gram=Decimal("3.12"),
                fire_rate_pct=Decimal("2"),
                has_gold_try_per_gram=Decimal("5401.32"),
                fx_base_rates=BASE_FX,
                stone_lines=[
                    StoneLineInput("MERKEZ", "Pırlanta", "ct", 1, Decimal("0.50")),
                    StoneLineInput("PAVE", "Pırlanta", "ct", 10, Decimal("0.01")),
                ],
                mount_range=MountRangeInput("HEAD_BAND", Decimal("0.40"), Decimal("0.75")),
                enforce_mount_range=True,
                cost_lines=[
                    CostLineInput("MADEN", "USD", fc_price_manual=None),
                    CostLineInput("ISCILIK", "EUR", fc_price=Decimal("15")),
                    CostLineInput("TAS", "USD", fc_price=Decimal("400")),
                ],
                channel_rules=[
                    ChannelRuleInput(
                        channel="B2B",
                        profit=AdjustmentInput("%", Decimal("15")),
                        discount=AdjustmentInput("TRY", Decimal("101.29")),
                        servis_bedeli=AdjustmentInput("%", Decimal("1")),
                    ),
                    ChannelRuleInput(
                        channel="B2C_API",
                        profit=AdjustmentInput("TRY", Decimal("20000")),
                        discount=AdjustmentInput("%", Decimal("8")),
                        servis_bedeli=AdjustmentInput("%", Decimal("2")),
                    ),
                ],
            )
        )
        # 1 * 0.50 + 10 * 0.01 = 0.60 ct; tare = 0.60 * 0.2 = 0.12 g
        self.assertEqual(out.fineness, Decimal("0.585"))
        self.assertEqual(out.total_stone_carat, Decimal("0.6000"))
        self.assertEqual(out.stone_tare_gram, Decimal("0.1200"))
        self.assertEqual(out.net_metal_gram, Decimal("3.0000"))
        self.assertEqual(out.fire_included_fine_metal_gram, Decimal("1.7901"))
        self.assertTrue(out.is_carat_within_mount_range)
        self.assertIsNotNone(out.resolve_channel("B2B"))
        self.assertIsNotNone(out.resolve_channel("B2C"))

    def test_mount_carat_out_of_range_blocks_when_enforced(self):
        inp = PricingEngineInput(
            pricing_mode="1",
            lc_currency="TRY",
            purity_code="14K",
            gross_weight_gram=Decimal("3.50"),
            fire_rate_pct=Decimal("2"),
            has_gold_try_per_gram=Decimal("5400"),
            fx_base_rates=BASE_FX,
            stone_lines=[
                StoneLineInput("MERKEZ", "Pırlanta", "ct", 2, Decimal("0.50")),  # 1.00 ct > max 0.75
            ],
            mount_range=MountRangeInput("HEAD_BAND", Decimal("0.40"), Decimal("0.75")),
            enforce_mount_range=True,
            cost_lines=[CostLineInput("MADEN", "USD", fc_price_manual=None)],
            channel_rules=[],
        )
        with self.assertRaises(MountCaratRangeError):
            calculate_pricing(inp)

    def test_scoped_fail_closed_ignores_unused_missing_currencies(self):
        minimal_fx = {"TRY": Decimal("1"), "USD": Decimal("42")}
        out = calculate_pricing(
            PricingEngineInput(
                pricing_mode="2",
                lc_currency="TRY",
                purity_code="14K",
                gross_weight_gram=Decimal("3.00"),
                fire_rate_pct=Decimal("0"),
                has_gold_try_per_gram=Decimal("5400"),
                fx_base_rates=minimal_fx,
                stone_lines=[],
                cost_lines=[CostLineInput("TEDARIKCI", "USD", fc_price=Decimal("100"))],
                channel_rules=[
                    ChannelRuleInput(
                        channel="B2B_API",
                        profit=AdjustmentInput("%", Decimal("10")),
                        discount=AdjustmentInput("%", Decimal("0")),
                        servis_bedeli=AdjustmentInput("%", Decimal("2")),
                    )
                ],
            )
        )
        self.assertEqual(out.total_cost_lc, Decimal("4200.00"))
        self.assertEqual(out.resolve_channel("B2B_API").nihai_fiyat_try, Decimal("4704.00"))

        with self.assertRaises(MissingRateError):
            calculate_pricing(
                PricingEngineInput(
                    pricing_mode="2",
                    lc_currency="TRY",
                    purity_code="14K",
                    gross_weight_gram=Decimal("3.00"),
                    fire_rate_pct=Decimal("0"),
                    has_gold_try_per_gram=Decimal("5400"),
                    fx_base_rates={"TRY": Decimal("1")},  # USD missing
                    stone_lines=[],
                    cost_lines=[CostLineInput("TEDARIKCI", "USD", fc_price=Decimal("100"))],
                    channel_rules=[],
                )
            )

    def test_same_model_variants_produce_distinct_prices(self):
        """
        Same ProductModel with 3 real jewelry variants:
        - 14K Sarı 2.80g
        - 14K Rose 2.95g
        - 18K Beyaz 3.20g
        Must produce 3 strictly ordered, distinct Decimal prices.
        """
        variant_specs = [
            ("14K", Decimal("2.8000")),
            ("14K", Decimal("2.9500")),
            ("18K", Decimal("3.2000")),
        ]
        prices: list[Decimal] = []
        for purity, weight in variant_specs:
            out = calculate_pricing(
                PricingEngineInput(
                    pricing_mode="1",
                    lc_currency="TRY",
                    purity_code=purity,
                    gross_weight_gram=weight,
                    fire_rate_pct=Decimal("2.00"),
                    has_gold_try_per_gram=Decimal("5401.32"),
                    fx_base_rates=BASE_FX,
                    stone_lines=[StoneLineInput("MERKEZ", "Pırlanta", "ct", 1, Decimal("0.50"))],
                    mount_range=MountRangeInput("FULL", Decimal("0.30"), Decimal("1.00")),
                    enforce_mount_range=True,
                    cost_lines=[
                        CostLineInput("MADEN", "USD", fc_price_manual=None),
                        CostLineInput("ISCILIK", "EUR", fc_price=Decimal("15")),
                        CostLineInput("TAS", "USD", fc_price=Decimal("400")),
                    ],
                    channel_rules=[
                        ChannelRuleInput(
                            channel="B2C_API",
                            profit=AdjustmentInput("%", Decimal("40")),
                            discount=AdjustmentInput("%", Decimal("0")),
                            servis_bedeli=AdjustmentInput("%", Decimal("2")),
                        )
                    ],
                )
            )
            prices.append(out.resolve_channel("B2C").nihai_fiyat_try)

        self.assertLess(prices[0], prices[1])
        self.assertLess(prices[1], prices[2])


if __name__ == "__main__":
    unittest.main()

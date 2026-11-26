from decimal import Decimal

from django.test import TestCase, override_settings

from apps.catalog.models import FinishedDetail, LooseStoneDetail, MountingDetail, ProductModel
from apps.catalog.product_kinds import FINISHED, LOOSE_STONE, MOUNTING
from apps.pricing.engine import (
    AdjustmentInput,
    ChannelRuleInput,
    CostLineInput,
    PricingEngineInput,
    calculate_pricing,
)
from apps.pricing.strategies import build_input_from_details


def _base_input(**overrides) -> PricingEngineInput:
    data = dict(
        pricing_mode="1",
        lc_currency="TRY",
        purity_code="14K",
        gross_weight_gram=Decimal("3.0000"),
        fire_rate_pct=Decimal("0"),
        has_gold_try_per_gram=Decimal("3000"),
        fx_base_rates={
            "TRY": Decimal("1"),
            "USD": Decimal("34"),
            "EUR": Decimal("37"),
        },
        stone_lines=(),
        cost_lines=[
            CostLineInput(line_type="MADEN", fc_currency="USD"),
            CostLineInput(line_type="ISCILIK", fc_currency="USD", fc_price=Decimal("10")),
            CostLineInput(line_type="TAS", fc_currency="USD", fc_price=Decimal("0")),
            CostLineInput(line_type="MONTUR", fc_currency="USD", fc_price=Decimal("0")),
            CostLineInput(line_type="DIGER", fc_currency="TRY", fc_price=Decimal("0")),
        ],
        channel_rules=[
            ChannelRuleInput(
                channel="B2B",
                profit=AdjustmentInput(unit="%", value=Decimal("10")),
                discount=AdjustmentInput(unit="%", value=Decimal("0")),
                servis_bedeli=AdjustmentInput(unit="%", value=Decimal("0")),
            ),
            ChannelRuleInput(
                channel="B2B_API",
                profit=AdjustmentInput(unit="%", value=Decimal("12")),
                discount=AdjustmentInput(unit="%", value=Decimal("0")),
                servis_bedeli=AdjustmentInput(unit="%", value=Decimal("0")),
            ),
            ChannelRuleInput(
                channel="B2C_API",
                profit=AdjustmentInput(unit="%", value=Decimal("40")),
                discount=AdjustmentInput(unit="%", value=Decimal("0")),
                servis_bedeli=AdjustmentInput(unit="%", value=Decimal("0")),
            ),
        ],
    )
    data.update(overrides)
    return PricingEngineInput(**data)


class StrategyPricingTests(TestCase):
    def _product(self, kind: str, sku: str) -> ProductModel:
        return ProductModel.objects.create(
            parent_sku=sku,
            product_kind=kind,
            title=f"Test {sku}",
            collection="Yeni Koleksiyon",
            category="Yüzük",
            purity_code="14K",
            metal_color="Sarı",
            seo_slug=f"test-{sku.lower()}",
            gross_weight_gram=Decimal("2.0000"),
        )

    def test_finished_strategy_channels(self):
        p = self._product(FINISHED, "FIN-001")
        FinishedDetail.objects.create(
            product=p,
            metal_name="Altın",
            purity_code="14K",
            metal_color="Sarı",
            fineness=Decimal("0.5850"),
            base_weight_gr=Decimal("2.0000"),
            fire_rate_pct=Decimal("0"),
            labor_cost_type="FIXED",
            labor_cost_value=Decimal("20"),
            fixed_stone_cost_usd=Decimal("100"),
        )
        inp, extras = build_input_from_details(p, base=_base_input())
        out = calculate_pricing(inp)
        self.assertEqual(extras["productKind"], FINISHED)
        self.assertIsNotNone(out.resolve_channel("B2B"))
        self.assertIsNotNone(out.resolve_channel("B2B_API"))
        self.assertIsNotNone(out.resolve_channel("B2C_API"))
        self.assertGreater(out.total_cost_lc, 0)

    def test_mounting_strategy_pure_gold(self):
        p = self._product(MOUNTING, "MNT-001")
        MountingDetail.objects.create(
            product=p,
            metal_name="Altın",
            purity_code="18K",
            metal_color="Beyaz",
            fineness=Decimal("0.7500"),
            net_weight_gr=Decimal("4.0000"),
            labor_cost_type="PER_GRAM",
            labor_cost_value=Decimal("5"),
            min_carat=Decimal("0.30"),
            max_carat=Decimal("1.20"),
        )
        inp, extras = build_input_from_details(p, base=_base_input())
        self.assertEqual(extras["pureGoldEquivalent"], Decimal("3.0000"))
        out = calculate_pricing(inp)
        self.assertGreater(out.resolve_channel("B2B").nihai_fiyat_try, 0)

    def test_loose_stone_mode2(self):
        p = self._product(LOOSE_STONE, "STN-001")
        LooseStoneDetail.objects.create(
            product=p,
            stone_category="Pırlanta",
            shape="Oval",
            carat=Decimal("0.700"),
            color="F",
            clarity="VS1",
            net_cost_usd=Decimal("1200"),
        )
        inp, extras = build_input_from_details(p, base=_base_input())
        self.assertEqual(inp.pricing_mode, "2")
        out = calculate_pricing(inp)
        # 1200 USD * 34 TRY = 40800 base before channel margin
        self.assertEqual(out.total_cost_lc, Decimal("40800.00"))
        b2c = out.resolve_channel("B2C_API")
        self.assertGreater(b2c.nihai_fiyat_try, out.total_cost_lc)

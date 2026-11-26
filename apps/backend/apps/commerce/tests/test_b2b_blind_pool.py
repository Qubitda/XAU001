"""B2B dealer serializers must not expose fire / labor-stone cost internals."""

from decimal import Decimal
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.commerce.api import _serialize_b2b_line, _serialize_b2b_order


def _line(**overrides):
    line = MagicMock()
    line.id = "22222222-2222-2222-2222-222222222222"
    line.variant_id = None
    line.sku = "YZ045-W14"
    line.parent_sku = "YZ045"
    line.title = "Test"
    line.category = "Yüzük"
    line.metal_color = "Beyaz"
    line.purity_code = "14K"
    line.size = 14
    line.size_unit_label = "Numara"
    line.qty = 2
    line.supply_type = "STOCK"
    line.dealer_stamp_note = ""
    line.unit_gross_gram = Decimal("4.2")
    line.unit_net_metal_gram = Decimal("3.9")
    line.unit_fire_included_fine_gram = Decimal("2.4")
    line.unit_labor_and_stone_usd = Decimal("120")
    line.unit_wholesale_usd = Decimal("350")
    line.unit_wholesale_try = Decimal("14700")
    line.pricing_currency = "USD"
    line.snapshot_code = "SNAP"
    line.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    for k, v in overrides.items():
        setattr(line, k, v)
    return line


class B2bBlindPoolTests(SimpleTestCase):
    def test_dealer_line_hides_internals(self):
        data = _serialize_b2b_line(_line(), for_ops=False)
        self.assertNotIn("unitFireIncludedFineGram", data)
        self.assertNotIn("unitLaborAndStoneUsd", data)
        self.assertNotIn("unitNetMetalGram", data)
        self.assertEqual(data["unitWholesaleUsd"], "350.00")

    def test_ops_line_keeps_internals(self):
        data = _serialize_b2b_line(_line(), for_ops=True)
        self.assertEqual(data["unitFireIncludedFineGram"], "2.4000")
        self.assertEqual(data["unitLaborAndStoneUsd"], "120.00")

    def test_dealer_order_hides_has_totals(self):
        order = MagicMock()
        order.order_no = "B2B-1"
        order.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        order.rate_snapshot.snapshot_code = "SNAP"
        order.usd_try_rate = Decimal("42")
        order.gold_rate_try_per_gram = Decimal("5400")
        order.organization_id = "org"
        order.branch_id = None
        order.branch = None
        order.created_by_id = "u1"
        order.created_by.full_name = "Ops"
        order.organization.code = "D1"
        order.organization.name = "Dealer"
        order.organization.tax_office_and_no = "X"
        order.contact_person = "Ali"
        order.settlement_method = "FX_CASH"
        order.rate_lock_mode = "LOCK_ON_ORDER"
        order.consignment_days = None
        order.delivery_method = "BRINKS_INSURED"
        order.order_note = ""
        order.accepted_weight_tolerance = True
        order.lines.all.return_value = [_line()]
        order.total_pieces = 2
        order.total_gross_gram = Decimal("8.4")
        order.total_has_gold_gram = Decimal("4.8")
        order.total_labor_and_stone_usd = Decimal("240")
        order.total_wholesale_usd = Decimal("700")
        order.total_wholesale_try = Decimal("29400")
        order.status = "PROFORMA_ONAYLANDI"

        dealer = _serialize_b2b_order(order, for_ops=False)
        self.assertNotIn("totalHasGoldGram", dealer)
        self.assertNotIn("totalLaborAndStoneUsd", dealer)
        self.assertNotIn("unitFireIncludedFineGram", dealer["lines"][0])

        ops = _serialize_b2b_order(order, for_ops=True)
        self.assertIn("totalHasGoldGram", ops)
        self.assertIn("unitFireIncludedFineGram", ops["lines"][0])

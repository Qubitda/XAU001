"""Blind-pool: B2C/B2B serializers must not leak cost, fire, owner, ERP, or stock qty."""

from decimal import Decimal

from django.test import SimpleTestCase
from unittest.mock import MagicMock

from apps.catalog.api import serialize_b2b_product, serialize_ops_product, serialize_storefront_product
from apps.catalog.models import ProductModel
from apps.catalog.product_details import (
    serialize_finished_detail,
    serialize_loose_stone_detail,
    serialize_mounting_detail,
)


FORBIDDEN_BUYER_KEYS = {
    "ownerOrganizationId",
    "erpCode",
    "stockQty",
    "salesChannels",
    "pricingBreakdown",
    "supplierName",
    "warehouseLocation",
    "fireRatePct",
    "ledger",
}


def _mock_rates():
    rates = MagicMock()
    rates.snapshot_code = "SNAP-TEST"
    return rates


def _mock_product(**overrides):
    product = MagicMock(spec=ProductModel)
    product.parent_sku = "YZ045"
    product.owner_organization_id = "11111111-1111-1111-1111-111111111111"
    product.barcode = "P1"
    product.visual_type = "solitaire_ring"
    product.title = "Test"
    product.description = "Desc"
    product.product_type = "Kuyum (Bitmiş Ürün)"
    product.erp_code = "ERP-SECRET"
    product.collection = "Yeni"
    product.category = "Yüzük"
    product.sub_category = "Tektaş"
    product.style_technique = "Modern"
    product.occasion = "Evlilik"
    product.age_group = "Yetişkin"
    product.metal_name = "Altın"
    product.purity_code = "14K"
    product.metal_color = "Beyaz"
    product.available_colors = ["Beyaz"]
    product.gross_weight_gram = Decimal("4.0")
    product.stock_status = ProductModel.StockStatus.IN_STOCK
    product.stock_qty = 12
    product.catalog_status = ProductModel.CatalogStatus.ACTIVE
    product.lead_time_days = 2
    product.sales_channels = ["B2B", "B2C_API"]
    product.stone_type = "Pırlanta"
    product.stone_measure_unit = "ct"
    product.stone_clarity = "VS1"
    product.stone_color_grade = "F"
    product.stone_cut_grade = "EX"
    product.stone_cut_shape = "ROUND"
    product.stone_origin = "DOGAL"
    product.setting_type = "Prong"
    product.certificate_agency = "GIA"
    product.certificate_number = "CERT1"
    product.variant_size = 14
    product.available_sizes = [14]
    product.width_mm = Decimal("2")
    product.thickness_mm = Decimal("1")
    product.height_mm = Decimal("5")
    product.chain_type = ""
    product.clasp_type = ""
    product.is_resizable = True
    product.warranty_months = 24
    product.insured_shipping_info = "Sigortalı"
    product.return_policy_text = "14 gün"
    product.seo_slug = "yz045"
    product.meta_title = "YZ045"
    product.supplier_name = "INTERNAL"
    product.warehouse_location = "MERKEZ"
    product.ownership_type = "Öz Mal"
    product.fire_rate_pct = Decimal("5")
    product.product_kind = "FINISHED"
    product.mount_structure = "FULL"
    product.allowed_carat_min = Decimal("0.3")
    product.allowed_carat_max = Decimal("1.0")
    product.head_code = ""
    product.band_code = ""
    product.head_weight_gram = Decimal("0")
    product.band_weight_gram = Decimal("0")
    product.variants.all.return_value = []
    product.media_items.all.return_value = []
    product.stone_lines.all.return_value = []
    # related details missing → serialize_product_details returns nulls
    type(product).finished_detail = property(lambda self: (_ for _ in ()).throw(Exception("no")))
    type(product).mounting_detail = property(lambda self: (_ for _ in ()).throw(Exception("no")))
    type(product).loose_stone_detail = property(lambda self: (_ for _ in ()).throw(Exception("no")))
    for k, v in overrides.items():
        setattr(product, k, v)
    return product


class BlindPoolSerializerTests(SimpleTestCase):
    def test_storefront_excludes_internal_keys(self):
        data = serialize_storefront_product(_mock_product(), None, _mock_rates())
        for key in FORBIDDEN_BUYER_KEYS:
            self.assertNotIn(key, data, key)
        self.assertNotIn("fireIncludedFineMetalGram", data.get("metalSummary", {}))
        self.assertIn("inStock", data)
        self.assertTrue(data["inStock"])

    def test_b2b_excludes_cost_and_fire_breakdown(self):
        data = serialize_b2b_product(_mock_product(), None, _mock_rates())
        for key in FORBIDDEN_BUYER_KEYS:
            self.assertNotIn(key, data, key)
        self.assertNotIn("pricingBreakdown", data)
        self.assertNotIn("fireIncludedFineMetalGram", data.get("metalSummary", {}))

    def test_ops_includes_internal_keys(self):
        data = serialize_ops_product(_mock_product(), None, _mock_rates())
        self.assertEqual(data["erpCode"], "ERP-SECRET")
        self.assertEqual(data["stockQty"], 12)
        self.assertIn("salesChannels", data)
        self.assertIn("fireIncludedFineMetalGram", data["metalSummary"])

    def test_detail_serializers_strip_costs_for_buyers(self):
        finished = MagicMock()
        finished.metal_name = "Altın"
        finished.purity_code = "14K"
        finished.metal_color = "Beyaz"
        finished.fineness = Decimal("0.585")
        finished.base_weight_gr = Decimal("4")
        finished.fire_rate_pct = Decimal("5")
        finished.labor_cost_type = "FIXED"
        finished.labor_cost_value = Decimal("10")
        finished.stone_summary = {}
        finished.fixed_stone_cost_usd = Decimal("100")
        pub = serialize_finished_detail(finished, for_ops=False)
        self.assertNotIn("fireRatePct", pub)
        self.assertNotIn("laborCostValue", pub)
        self.assertNotIn("fixedStoneCostUsd", pub)
        ops = serialize_finished_detail(finished, for_ops=True)
        self.assertIn("fireRatePct", ops)

        stone = MagicMock()
        stone.stone_category = "Pırlanta"
        stone.shape = "ROUND"
        stone.carat = Decimal("1")
        stone.color = "F"
        stone.clarity = "VS1"
        stone.cut_grade = "EX"
        stone.cert_lab = "GIA"
        stone.cert_number = "X"
        stone.cert_url = ""
        stone.measurements_mm = ""
        stone.length_mm = None
        stone.width_mm = None
        stone.depth_mm = None
        stone.rapaport_price_usd = Decimal("5000")
        stone.discount_percent = Decimal("10")
        stone.net_cost_usd = Decimal("4000")
        stone.supplier_id = "SUP-1"
        pub_s = serialize_loose_stone_detail(stone, for_ops=False)
        self.assertNotIn("netCostUsd", pub_s)
        self.assertNotIn("supplierId", pub_s)
        ops_s = serialize_loose_stone_detail(stone, for_ops=True)
        self.assertEqual(ops_s["netCostUsd"], 4000.0)

        mount = MagicMock()
        mount.metal_name = "Altın"
        mount.purity_code = "14K"
        mount.metal_color = "Beyaz"
        mount.fineness = Decimal("0.585")
        mount.net_weight_gr = Decimal("3")
        mount.labor_cost_type = "FIXED"
        mount.labor_cost_value = Decimal("20")
        mount.mount_structure = "FULL"
        mount.compatible_shapes = ["ROUND"]
        mount.min_carat = Decimal("0.3")
        mount.max_carat = Decimal("1")
        mount.min_length_mm = None
        mount.max_length_mm = None
        mount.min_width_mm = None
        mount.max_width_mm = None
        mount.setting_labor_usd = Decimal("15")
        mount.setting_type_code = ""
        mount.head_code = ""
        mount.band_code = ""
        mount.head_weight_gram = None
        mount.band_weight_gram = None
        pub_m = serialize_mounting_detail(mount, for_ops=False)
        self.assertNotIn("settingLaborUsd", pub_m)
        self.assertNotIn("laborCostValue", pub_m)

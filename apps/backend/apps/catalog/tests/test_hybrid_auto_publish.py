"""Tests for Hybrid Recipe Auto-Publish (Option C) on OPS product PATCH."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductModel, ProductVariant
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import ChannelRule, CostLine, PricingRecipe
from apps.pricing.services import publish_recipe

User = get_user_model()


class HybridAutoPublishTests(TestCase):
    def setUp(self) -> None:
        get_current_rate_snapshot()
        self.platform_org = Organization.objects.create(
            code="HYB-PLAT",
            name="Tara OPS",
            org_type=Organization.OrgType.DEALER,
        )
        self.ops_user = User.objects.create_user(
            email="hyb-ops@tara.local", password="pw", is_staff=True
        )
        OrganizationMembership.objects.create(
            user=self.ops_user,
            organization=self.platform_org,
            role_key="SUPER_ADMIN",
        )

        self.product = ProductModel.objects.create(
            parent_sku="HYB-01",
            title="Hibrit Test Yüzük",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            fire_rate_pct=Decimal("2.00"),
            seo_slug="hyb-01",
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2B", "B2C_API"],
        )
        self.v_default = ProductVariant.objects.create(
            product=self.product,
            sku="HYB-01-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.00"),
            is_default=True,
            is_active=True,
        )
        self.v_second = ProductVariant.objects.create(
            product=self.product,
            sku="HYB-01-14K-SAR-16",
            purity_code="14K",
            metal_color="Sarı",
            size=16,
            gross_weight_gram=Decimal("4.50"),
            is_default=False,
            is_active=True,
        )
        recipe = PricingRecipe.objects.create(
            product=self.product,
            version=1,
            status=PricingRecipe.Status.DRAFT,
        )
        CostLine.objects.create(
            recipe=recipe,
            line_type=CostLine.LineType.MADEN,
            fc_currency="USD",
            fc_price_manual=None,
        )
        CostLine.objects.create(
            recipe=recipe,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="USD",
            fc_price=Decimal("25.00"),
        )
        ChannelRule.objects.create(
            recipe=recipe, channel="B2B", profit_unit="%", profit_value=Decimal("15")
        )
        ChannelRule.objects.create(
            recipe=recipe, channel="B2C_API", profit_unit="%", profit_value=Decimal("30")
        )
        self.published_recipe, _ = publish_recipe(recipe, actor=self.ops_user)

        self.client = APIClient()
        self.client.force_authenticate(user=self.ops_user)

    def test_price_affecting_field_triggers_auto_publish(self) -> None:
        old_b2c = self.published_recipe.cached_b2c_try

        # 1. Physical field change (grossWeightGram) refreshes published recipe immediately
        res_weight = self.client.patch(
            f"/api/v1/ops/products/{self.product.parent_sku}",
            {"grossWeightGram": "6.00"},
            format="json",
        )
        self.assertEqual(res_weight.status_code, 200)
        data_weight = res_weight.json()["data"]
        self.assertTrue(data_weight["priceUpdated"])
        self.assertIsNotNone(data_weight["newPrice"])
        self.published_recipe.refresh_from_db()
        self.assertGreater(self.published_recipe.cached_b2c_try, old_b2c)
        self.assertFalse(
            PricingRecipe.objects.filter(
                product=self.product, status=PricingRecipe.Status.DRAFT
            ).exists()
        )

        # 2. Ledger change creates new version and auto-publishes it (no leftover DRAFT)
        res_ledger = self.client.patch(
            f"/api/v1/ops/products/{self.product.parent_sku}",
            {"ledger": {"laborFcPrice": "80.00"}},
            format="json",
        )
        self.assertEqual(res_ledger.status_code, 200)
        data_ledger = res_ledger.json()["data"]
        self.assertTrue(data_ledger["priceUpdated"])
        self.assertFalse(
            PricingRecipe.objects.filter(
                product=self.product, status=PricingRecipe.Status.DRAFT
            ).exists()
        )
        latest_pub = PricingRecipe.objects.filter(
            product=self.product, status=PricingRecipe.Status.PUBLISHED
        ).first()
        self.assertIsNotNone(latest_pub)
        self.assertEqual(latest_pub.version, 2)

    def test_non_price_field_does_not_publish(self) -> None:
        old_b2c = self.published_recipe.cached_b2c_try
        initial_count = PricingRecipe.objects.filter(product=self.product).count()

        res = self.client.patch(
            f"/api/v1/ops/products/{self.product.parent_sku}",
            {"title": "Güncel Başlık", "description": "Sadece açıklama değişti"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertFalse(data["priceUpdated"])
        self.assertIsNone(data["newPrice"])
        self.assertEqual(
            PricingRecipe.objects.filter(product=self.product).count(), initial_count
        )
        self.assertFalse(
            PricingRecipe.objects.filter(
                product=self.product, status=PricingRecipe.Status.DRAFT
            ).exists()
        )
        self.published_recipe.refresh_from_db()
        self.assertEqual(self.published_recipe.cached_b2c_try, old_b2c)

    def test_response_includes_priceUpdated(self) -> None:
        res = self.client.patch(
            f"/api/v1/ops/products/{self.product.parent_sku}",
            {"fireRatePct": "5.00"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertTrue(data["priceUpdated"])
        new_price = data["newPrice"]
        self.assertIsInstance(new_price, dict)
        self.assertEqual(new_price["defaultVariantSku"], self.v_default.sku)
        self.assertIn("b2cTry", new_price)
        self.assertIn("b2bTry", new_price)
        self.assertIn("b2bLc", new_price)
        self.assertEqual(new_price["lcCurrency"], "TRY")
        self.assertEqual(len(new_price["variants"]), 2)
        skus = {v["sku"] for v in new_price["variants"]}
        self.assertEqual(skus, {self.v_default.sku, self.v_second.sku})
        for v in new_price["variants"]:
            self.assertIn("b2cTry", v)
            self.assertIn("b2bTry", v)

    def test_price_history_visible(self) -> None:
        self.client.patch(
            f"/api/v1/ops/products/{self.product.parent_sku}",
            {"grossWeightGram": "5.50"},
            format="json",
        )
        res = self.client.get(f"/api/v1/ops/products/{self.product.parent_sku}")
        self.assertEqual(res.status_code, 200)
        history = res.json()["data"]["priceHistory"]
        self.assertGreaterEqual(len(history), 2)
        latest = history[0]
        self.assertIsNotNone(latest["newB2cTry"])
        self.assertIsNotNone(latest["oldB2cTry"])
        self.assertNotEqual(latest["newB2cTry"], latest["oldB2cTry"])
        self.assertEqual(latest["changedBy"], self.ops_user.email)
        self.assertTrue(latest["changedAt"])

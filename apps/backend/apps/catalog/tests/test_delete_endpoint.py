"""Regression tests for OPS product DELETE (hard delete, cascade, archive, and 403)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductModel, ProductVariant
from apps.commerce.models import B2cOrder, B2cOrderItem
from apps.customers.models import Customer
from apps.inventory.models import StockMovement
from apps.inventory.services import get_or_create_default_warehouse, set_variant_warehouse_stock
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import ChannelRule, CostLine, PriceQuote, PricingRecipe
from apps.pricing.services import create_live_quote, publish_recipe

User = get_user_model()


class OpsProductDeleteEndpointTests(TestCase):
    def setUp(self) -> None:
        self.snap = get_current_rate_snapshot()
        self.wh = get_or_create_default_warehouse()
        self.platform_org = Organization.objects.create(
            code="DEL-PLAT",
            name="Tara OPS",
            org_type=Organization.OrgType.DEALER,
        )
        self.deleter = User.objects.create_user(email="del-ok@tara.local", password="pw", is_staff=True)
        OrganizationMembership.objects.create(
            user=self.deleter,
            organization=self.platform_org,
            role_key="SUPER_ADMIN",
        )
        self.no_delete_user = User.objects.create_user(email="del-no@tara.local", password="pw", is_staff=True)
        OrganizationMembership.objects.create(
            user=self.no_delete_user,
            organization=self.platform_org,
            role_key="OPS",
            denied_permissions=["catalog:delete"],
        )
        self.client = APIClient()

    def _mk_draft_product(self, sku: str) -> tuple[ProductModel, ProductVariant]:
        p = ProductModel.objects.create(
            parent_sku=sku,
            title=f"Test {sku}",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            seo_slug=sku.lower(),
            catalog_status=ProductModel.CatalogStatus.DRAFT,
            sales_channels=["B2C_API"],
        )
        v = ProductVariant.objects.create(
            product=p,
            sku=f"{sku}-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.00"),
            is_default=True,
            is_active=True,
        )
        return p, v

    def test_draft_product_without_refs_hard_deletes(self) -> None:
        self._mk_draft_product("DEL-HARD-01")
        self.client.force_authenticate(user=self.deleter)
        resp = self.client.delete("/api/v1/ops/products/DEL-HARD-01")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"], {"parentSku": "DEL-HARD-01", "deleted": True, "archived": False})
        self.assertFalse(ProductModel.objects.filter(parent_sku="DEL-HARD-01").exists())

    def test_draft_product_with_price_quote_hard_deletes_and_preserves_quote_sku(self) -> None:
        p, v = self._mk_draft_product("DEL-PQ-01")
        recipe = PricingRecipe.objects.create(product=p, version=1, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(recipe=recipe, line_type=CostLine.LineType.ISCILIK, fc_currency="USD", fc_price=Decimal("20.00"))
        ChannelRule.objects.create(recipe=recipe, channel="B2C_API", profit_unit="%", profit_value=Decimal("20"))
        publish_recipe(recipe, actor=self.deleter)
        quote, _ = create_live_quote(product=p, channel="B2C", variant=v, snapshot=self.snap, size=14)

        self.client.force_authenticate(user=self.deleter)
        resp = self.client.delete("/api/v1/ops/products/DEL-PQ-01")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"], {"parentSku": "DEL-PQ-01", "deleted": True, "archived": False})
        self.assertFalse(ProductModel.objects.filter(parent_sku="DEL-PQ-01").exists())
        quote.refresh_from_db()
        self.assertIsNone(quote.product)
        self.assertEqual(quote.product_sku, "DEL-PQ-01")

    def test_stock_movement_cascades_on_draft_product_delete(self) -> None:
        _, v = self._mk_draft_product("DEL-STK-01")
        set_variant_warehouse_stock(variant=v, warehouse=self.wh, quantity=5, reference_no="INIT-DEL-STK-01")
        self.assertEqual(StockMovement.objects.filter(product__parent_sku="DEL-STK-01").count(), 1)

        self.client.force_authenticate(user=self.deleter)
        resp = self.client.delete("/api/v1/ops/products/DEL-STK-01")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["data"]["deleted"])
        self.assertFalse(ProductModel.objects.filter(parent_sku="DEL-STK-01").exists())
        self.assertEqual(StockMovement.objects.filter(reference_no="INIT-DEL-STK-01").count(), 0)

    def test_draft_with_order_ref_archives_instead_of_hard_delete(self) -> None:
        p, v = self._mk_draft_product("DEL-ORD-01")
        cust = Customer.objects.create(email="del-cust@tara.local", full_name="Test Müşteri")
        order = B2cOrder.objects.create(
            order_no="ORD-DEL-01",
            customer=cust,
            rate_snapshot=self.snap,
            gold_rate_try_per_gram=Decimal("3000"),
            payment_method="BANK_TRANSFER",
            subtotal_list_try=Decimal("5000.00"),
            grand_total_try=Decimal("5000.00"),
        )
        B2cOrderItem.objects.create(
            order=order,
            variant=v,
            sku=v.sku,
            parent_sku=p.parent_sku,
            title=p.title,
            category=p.category,
            metal_color="Beyaz",
            purity_code="14K",
            qty=1,
            gross_weight_gram=Decimal("3.0000"),
            unit_list_price_try=Decimal("5000.00"),
            unit_final_price_try=Decimal("5000.00"),
            snapshot_code=self.snap.snapshot_code,
        )

        self.client.force_authenticate(user=self.deleter)
        resp = self.client.delete("/api/v1/ops/products/DEL-ORD-01")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"], {"parentSku": "DEL-ORD-01", "deleted": False, "archived": True})
        p.refresh_from_db()
        self.assertEqual(p.catalog_status, ProductModel.CatalogStatus.ARCHIVED)

    def test_delete_requires_catalog_delete_permission(self) -> None:
        self._mk_draft_product("DEL-PERM-01")
        self.client.force_authenticate(user=self.no_delete_user)
        resp = self.client.delete("/api/v1/ops/products/DEL-PERM-01")
        self.assertEqual(resp.status_code, 403)

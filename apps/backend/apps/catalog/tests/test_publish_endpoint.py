"""Regression tests for OPS product /publish and /unpublish endpoints."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductMedia, ProductModel, ProductVariant
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import ChannelRule, CostLine, PricingRecipe
from apps.pricing.services import publish_recipe

User = get_user_model()


class OpsProductPublishEndpointTests(TestCase):
    def setUp(self) -> None:
        get_current_rate_snapshot()
        self.platform_org = Organization.objects.create(
            code="PUB-PLAT",
            name="Tara OPS",
            org_type=Organization.OrgType.DEALER,
        )
        self.publisher = User.objects.create_user(email="pub-ok@tara.local", password="pw", is_staff=True)
        OrganizationMembership.objects.create(
            user=self.publisher,
            organization=self.platform_org,
            role_key="SUPER_ADMIN",
        )
        self.no_publish_user = User.objects.create_user(email="pub-no@tara.local", password="pw", is_staff=True)
        OrganizationMembership.objects.create(
            user=self.no_publish_user,
            organization=self.platform_org,
            role_key="OPS",
            denied_permissions=["catalog:publish"],
        )

        self.product = ProductModel.objects.create(
            parent_sku="PUB-REG-01",
            title="Publish Test Yüzük",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.20"),
            seo_slug="pub-reg-01",
            catalog_status=ProductModel.CatalogStatus.DRAFT,
            sales_channels=["B2C_API"],
        )
        ProductVariant.objects.create(
            product=self.product,
            sku="PUB-REG-01-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.20"),
            is_default=True,
            is_active=True,
        )
        ProductMedia.objects.create(
            product=self.product,
            role=ProductMedia.MediaRole.GALLERY_MAIN,
            url="https://cdn.example.com/pub-reg-01.jpg",
            sort_order=1,
        )
        recipe = PricingRecipe.objects.create(product=self.product, version=1, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(
            recipe=recipe,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="USD",
            fc_price=Decimal("25.00"),
        )
        ChannelRule.objects.create(recipe=recipe, channel="B2C_API", profit_unit="%", profit_value=Decimal("30"))
        publish_recipe(recipe, actor=self.publisher)
        self.client = APIClient()

    def test_publish_returns_catalog_status(self) -> None:
        self.client.force_authenticate(user=self.publisher)
        resp = self.client.post(f"/api/v1/ops/products/{self.product.parent_sku}/publish")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["parentSku"], self.product.parent_sku)
        self.assertEqual(data["catalogStatus"], "ACTIVE")

    def test_publish_requires_catalog_publish_permission(self) -> None:
        self.client.force_authenticate(user=self.no_publish_user)
        resp = self.client.post(f"/api/v1/ops/products/{self.product.parent_sku}/publish")
        self.assertEqual(resp.status_code, 403)

    def test_unpublish_returns_catalog_status(self) -> None:
        self.client.force_authenticate(user=self.publisher)
        self.assertEqual(self.client.post(f"/api/v1/ops/products/{self.product.parent_sku}/publish").status_code, 200)
        resp = self.client.post(f"/api/v1/ops/products/{self.product.parent_sku}/unpublish")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["parentSku"], self.product.parent_sku)
        self.assertEqual(data["catalogStatus"], "DRAFT")

    def test_publish_then_list_reflects_status(self) -> None:
        self.client.force_authenticate(user=self.publisher)
        self.assertEqual(self.client.post(f"/api/v1/ops/products/{self.product.parent_sku}/publish").status_code, 200)
        list_resp = self.client.get("/api/v1/ops/products")
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.json()["data"]
        row = next((x for x in items if x["parentSku"] == self.product.parent_sku), None)
        self.assertIsNotNone(row)
        self.assertEqual(row["catalogStatus"], "ACTIVE")

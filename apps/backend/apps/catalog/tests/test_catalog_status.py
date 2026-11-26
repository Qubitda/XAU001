from django.test import TestCase
from rest_framework.test import APIRequestFactory
from apps.catalog.api import StorefrontProductListView
from apps.catalog.models import ProductModel
from apps.pricing.models import PricingRecipe


class CatalogStatusFilterTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.active = ProductModel.objects.create(
            parent_sku="ACT-001",
            title="Active Product",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug="act-001",
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            available_colors=["Beyaz"],
            available_sizes=[14],
        )
        PricingRecipe.objects.create(
            product=self.active,
            version=1,
            status=PricingRecipe.Status.PUBLISHED,
        )
        self.draft = ProductModel.objects.create(
            parent_sku="DFT-001",
            title="Draft Product",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug="dft-001",
            catalog_status=ProductModel.CatalogStatus.DRAFT,
            available_colors=["Beyaz"],
            available_sizes=[14],
        )
        PricingRecipe.objects.create(
            product=self.draft,
            version=1,
            status=PricingRecipe.Status.PUBLISHED,
        )

    def test_storefront_hides_draft_products(self):
        request = self.factory.get("/api/v1/storefront/products")
        response = StorefrontProductListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        skus = [row["parentSku"] for row in response.data["data"]]
        self.assertIn("ACT-001", skus)
        self.assertNotIn("DFT-001", skus)

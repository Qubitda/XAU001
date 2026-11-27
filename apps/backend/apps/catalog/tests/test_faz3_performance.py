from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductModel, ProductVariant
from apps.market.models import RateSnapshot
from apps.pricing.models import PricingRecipe


class Faz3PaginationAndPerfTests(TestCase):
    def setUp(self):
        cache.clear()
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-FAZ3",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        for i in range(5):
            p = ProductModel.objects.create(
                parent_sku=f"PERF-{i:02d}",
                title=f"Perf Ürün {i}",
                category="Yüzük",
                collection="Test",
                purity_code="14K",
                metal_color="Beyaz",
                seo_slug=f"perf-{i:02d}",
                catalog_status=ProductModel.CatalogStatus.ACTIVE,
                sales_channels=["B2C_API"],
            )
            ProductVariant.objects.create(
                product=p,
                sku=f"PERF-{i:02d}-14K-BYZ-14",
                purity_code="14K",
                metal_color="Beyaz",
                gross_weight_gram=Decimal("3.0"),
                is_default=True,
            )
            PricingRecipe.objects.create(product=p, version=1, status=PricingRecipe.Status.PUBLISHED)
        self.client = APIClient()

    def test_storefront_pagination_and_query_count(self):
        res = self.client.get("/api/v1/storefront/products?page=1&page_size=2&ordering=parentSku")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["data"]), 2)
        self.assertEqual(body["meta"]["pagination"]["total"], 5)
        self.assertEqual(body["meta"]["pagination"]["totalPages"], 3)
        self.assertTrue(body["meta"]["pagination"]["hasNext"])

        # Cached second call executes 0 product queries (<= 2 queries for rate snapshot only)
        with self.assertNumQueries(1):
            cached_res = self.client.get("/api/v1/storefront/products?page=1&page_size=2&ordering=parentSku")
        self.assertEqual(cached_res.status_code, 200)

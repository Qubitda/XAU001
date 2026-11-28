"""Tests for PriceQuote SET_NULL + product_sku preservation and immutability."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.catalog.models import ProductModel, ProductVariant
from apps.market.services import get_current_rate_snapshot
from apps.pricing.models import ChannelRule, CostLine, PriceQuote, PricingRecipe
from apps.pricing.ops_api import serialize_ops_price_quote
from apps.pricing.services import create_live_quote, publish_recipe


class PriceQuoteProductSetNullTests(TestCase):
    def setUp(self) -> None:
        self.snap = get_current_rate_snapshot()
        self.product = ProductModel.objects.create(
            parent_sku="PQ-DEL-01",
            title="PriceQuote Test Yüzük",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            seo_slug="pq-del-01",
            catalog_status=ProductModel.CatalogStatus.DRAFT,
            sales_channels=["B2C_API"],
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="PQ-DEL-01-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.00"),
            is_default=True,
            is_active=True,
        )
        recipe = PricingRecipe.objects.create(product=self.product, version=1, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(
            recipe=recipe,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="USD",
            fc_price=Decimal("20.00"),
        )
        ChannelRule.objects.create(recipe=recipe, channel="B2C_API", profit_unit="%", profit_value=Decimal("25"))
        publish_recipe(recipe)
        self.quote, _ = create_live_quote(
            product=self.product,
            channel="B2C",
            variant=self.variant,
            snapshot=self.snap,
            size=14,
        )

    def test_price_quote_immutability_preserved_after_set_null(self) -> None:
        self.assertEqual(self.quote.product_sku, "PQ-DEL-01")
        self.product.delete()
        self.quote.refresh_from_db()
        self.assertIsNone(self.quote.product)
        self.assertIsNone(self.quote.variant)
        self.assertIsNone(self.quote.recipe)
        self.assertEqual(self.quote.product_sku, "PQ-DEL-01")
        self.assertIn("PQ-DEL-01", str(self.quote))
        serialized = serialize_ops_price_quote(self.quote)
        self.assertEqual(serialized["parentSku"], "PQ-DEL-01")
        self.assertIsNone(serialized["productId"])

        with self.assertRaises(ValidationError):
            PriceQuote.objects.filter(id=self.quote.id).delete()
        with self.assertRaises(ValidationError):
            self.quote.delete()

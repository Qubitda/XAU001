from decimal import Decimal
from django.test import TestCase
from unittest.mock import patch
from apps.catalog.api import _sync_recipe_from_ledger
from apps.catalog.models import ProductModel
from apps.pricing.models import CostLine, PricingRecipe


class SyncRecipeVersioningTests(TestCase):
    def setUp(self):
        self.product = ProductModel.objects.create(
            parent_sku="SYNC-001",
            title="Sync Version Ring",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug="sync-001",
            available_colors=["Beyaz"],
            available_sizes=[14],
        )
        self.published = PricingRecipe.objects.create(
            product=self.product,
            version=1,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode="1",
            lc_currency="TRY",
        )
        CostLine.objects.create(
            recipe=self.published,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="EUR",
            fc_price=Decimal("10.00"),
        )
        # Flip to published after cost lines exist (mirrors publish_recipe path)
        PricingRecipe.objects.filter(id=self.published.id).update(
            status=PricingRecipe.Status.PUBLISHED
        )
        self.published.refresh_from_db()

    @patch("apps.catalog.api.recipe_sync.publish_recipe")
    def test_sync_does_not_mutate_published_recipe(self, mock_publish):
        draft = PricingRecipe.objects.create(
            product=self.product,
            version=2,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode="1",
        )
        mock_publish.side_effect = lambda recipe, actor=None: (recipe, None)

        result = _sync_recipe_from_ledger(
            product=self.product,
            pricing_mode="1",
            ledger={
                "lcCurrency": "TRY",
                "laborCurrency": "EUR",
                "laborFcPrice": "15.00",
                "laborRateOverride": None,
                "metalCurrency": "USD",
                "metalRateOverride": None,
                "metalFcManual": None,
                "stoneCurrency": "USD",
                "stoneFcPrice": "0",
                "stoneRateOverride": None,
                "mountingCurrency": "USD",
                "mountingFcPrice": "0",
                "mountingRateOverride": None,
                "otherCostCurrency": "TRY",
                "otherCostFcPrice": "0",
                "otherCostRateOverride": None,
                "supplierCurrency": "USD",
                "supplierFcPrice": "0",
                "supplierRateOverride": None,
            },
            actor=None,
        )

        self.published.refresh_from_db()
        self.assertEqual(self.published.status, PricingRecipe.Status.PUBLISHED)
        # Original published cost line must remain untouched (immutable)
        original = CostLine.objects.get(recipe=self.published, line_type=CostLine.LineType.ISCILIK)
        self.assertEqual(original.fc_price, Decimal("10.00"))
        # Edits land on draft version
        draft.refresh_from_db()
        edited = CostLine.objects.get(recipe=draft, line_type=CostLine.LineType.ISCILIK)
        self.assertEqual(edited.fc_price, Decimal("15.00"))
        self.assertEqual(result.id, draft.id)

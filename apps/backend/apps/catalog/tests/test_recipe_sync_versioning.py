from decimal import Decimal
from django.test import TestCase
from unittest.mock import patch
from apps.catalog.api import _sync_recipe_from_ledger
from apps.catalog.models import ProductModel, ProductVariant, StoneLine
from apps.catalog.services import sync_default_variant_center_carat
from apps.pricing.models import CostLine, PricingRecipe
from apps.pricing.services import publish_recipe


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

    def test_publishing_new_recipe_deprecates_previous_published_version(self):
        v2 = PricingRecipe.objects.create(
            product=self.product,
            version=2,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode="1",
            lc_currency="TRY",
        )
        CostLine.objects.create(
            recipe=v2,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="EUR",
            fc_price=Decimal("25.00"),
        )
        published_v2, prev = publish_recipe(v2)
        self.published.refresh_from_db()

        self.assertEqual(published_v2.status, PricingRecipe.Status.PUBLISHED)
        self.assertIsNotNone(prev)
        self.assertNotEqual(self.published.status, PricingRecipe.Status.PUBLISHED)
        self.assertEqual(
            PricingRecipe.objects.filter(product=self.product, status=PricingRecipe.Status.PUBLISHED).count(),
            1,
        )

    def test_sync_default_variant_center_carat_empty_and_multiple_merkez_lines(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            sku="SYNC-001-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            center_stone_carat=Decimal("0.500"),
            gross_weight_gram=Decimal("3.20"),
            is_default=True,
            is_active=True,
        )

        # Edge case 1: empty stone_lines resets center_stone_carat to 0.000
        total_empty = sync_default_variant_center_carat(self.product)
        variant.refresh_from_db()
        self.assertEqual(total_empty, Decimal("0.000"))
        self.assertEqual(variant.center_stone_carat, Decimal("0.000"))

        # Edge case 2: multiple MERKEZ rows sum (count * carat), ignoring YAN rows
        StoneLine.objects.create(
            product=self.product, role=StoneLine.Role.MERKEZ, stone_type="Pırlanta", count=1, carat=Decimal("0.400")
        )
        StoneLine.objects.create(
            product=self.product, role=StoneLine.Role.MERKEZ, stone_type="Pırlanta", count=2, carat=Decimal("0.150")
        )
        StoneLine.objects.create(
            product=self.product, role=StoneLine.Role.YAN, stone_type="Pırlanta", count=4, carat=Decimal("0.050")
        )
        total_multi = sync_default_variant_center_carat(self.product)
        variant.refresh_from_db()
        self.assertEqual(total_multi, Decimal("0.700"))
        self.assertEqual(variant.center_stone_carat, Decimal("0.700"))

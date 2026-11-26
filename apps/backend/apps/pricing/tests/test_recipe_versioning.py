from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from apps.catalog.models import ProductModel
from apps.pricing.models import ChannelRule, CostLine, PricingRecipe


class RecipeVersioningTests(TestCase):
    def setUp(self):
        self.product = ProductModel.objects.create(
            parent_sku="VER-001",
            title="Version Test Ring",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug="ver-001-test",
            available_colors=["Beyaz"],
            available_sizes=[14],
        )

    def test_published_cost_line_is_immutable(self):
        recipe = PricingRecipe.objects.create(
            product=self.product,
            version=1,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode="1",
        )
        line = CostLine.objects.create(
            recipe=recipe,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="EUR",
            fc_price=Decimal("10.00"),
        )
        PricingRecipe.objects.filter(id=recipe.id).update(status=PricingRecipe.Status.PUBLISHED)
        line.fc_price = Decimal("12.00")
        with self.assertRaises(ValidationError):
            line.save()

    def test_published_channel_rule_delete_blocked(self):
        recipe = PricingRecipe.objects.create(
            product=self.product,
            version=1,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode="1",
        )
        rule = ChannelRule.objects.create(
            recipe=recipe,
            channel=ChannelRule.Channel.B2B,
            profit_value=Decimal("5"),
        )
        PricingRecipe.objects.filter(id=recipe.id).update(status=PricingRecipe.Status.PUBLISHED)
        with self.assertRaises(ValidationError):
            rule.delete()

    def test_draft_cost_line_can_be_edited(self):
        recipe = PricingRecipe.objects.create(
            product=self.product,
            version=1,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode="1",
        )
        line = CostLine.objects.create(
            recipe=recipe,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="EUR",
            fc_price=Decimal("10.00"),
        )
        line.fc_price = Decimal("12.00")
        line.save()
        line.refresh_from_db()
        self.assertEqual(line.fc_price, Decimal("12.00"))

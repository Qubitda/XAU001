from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from apps.accounts.models import User
from apps.catalog.api import StorefrontProductListView
from apps.catalog.models import ProductMedia, ProductModel, ProductVariant
from apps.catalog.services import validate_publishable
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import CostLine, PricingRecipe


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
            sales_channels=["B2C_API"],
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


class CatalogPublishGatesAndTransitionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ops_org = Organization.objects.create(
            code="ORG-OPS-STAT",
            name="OPS Org Status",
            org_type=Organization.OrgType.PLATFORM_OWNER,
        )
        self.ops_user = User.objects.create_user(email="cat-status-ops@taragold.com", password="pass")
        OrganizationMembership.objects.create(
            user=self.ops_user,
            organization=self.ops_org,
            role_key=OrganizationMembership.RoleKey.OPS,
        )
        self.client.force_authenticate(user=self.ops_user)

    def _make_complete_draft(self, sku: str = "GATE-001") -> ProductModel:
        product = ProductModel.objects.create(
            parent_sku=sku,
            title="Tamamlanmış Tektaş Yüzük",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.50"),
            seo_slug=sku.lower(),
            catalog_status=ProductModel.CatalogStatus.DRAFT,
            sales_channels=["B2C_API"],
        )
        ProductVariant.objects.create(
            product=product,
            sku=f"{sku}-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.50"),
            is_default=True,
            is_active=True,
        )
        recipe = PricingRecipe.objects.create(product=product, version=1, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(recipe=recipe, line_type=CostLine.LineType.ISCILIK, fc_currency="USD", fc_price=Decimal("20.00"))
        PricingRecipe.objects.filter(id=recipe.id).update(status=PricingRecipe.Status.PUBLISHED)
        ProductMedia.objects.create(
            product=product,
            metal_color="Beyaz",
            role=ProductMedia.MediaRole.GALLERY_MAIN,
            url="https://cdn.example.com/main.jpg",
            sort_order=1,
        )
        return product

    def test_validate_publishable_triggers_every_missing_condition(self):
        # 1. TITLE_REQUIRED
        p1 = self._make_complete_draft("MISS-TITLE")
        p1.title = "AB"
        p1.save(update_fields=["title"])
        self.assertEqual(validate_publishable(p1), ["TITLE_REQUIRED"])

        # 2. CATEGORY_REQUIRED
        p2 = self._make_complete_draft("MISS-CAT")
        p2.category = ""
        p2.save(update_fields=["category"])
        self.assertEqual(validate_publishable(p2), ["CATEGORY_REQUIRED"])

        # 3. GROSS_WEIGHT_REQUIRED
        p3 = self._make_complete_draft("MISS-WT")
        p3.gross_weight_gram = Decimal("0.00")
        p3.save(update_fields=["gross_weight_gram"])
        self.assertEqual(validate_publishable(p3), ["GROSS_WEIGHT_REQUIRED"])

        # 4. PUBLISHED_RECIPE_REQUIRED
        p4 = self._make_complete_draft("MISS-REC")
        PricingRecipe.objects.filter(product=p4).update(status=PricingRecipe.Status.DRAFT)
        self.assertEqual(validate_publishable(p4), ["PUBLISHED_RECIPE_REQUIRED"])

        # 5. ACTIVE_VARIANT_REQUIRED
        p5 = self._make_complete_draft("MISS-VAR")
        ProductVariant.objects.filter(product=p5).update(is_active=False)
        self.assertEqual(validate_publishable(p5), ["ACTIVE_VARIANT_REQUIRED"])

        # 6. SALES_CHANNEL_REQUIRED
        p6 = self._make_complete_draft("MISS-CH")
        p6.sales_channels = []
        p6.save(update_fields=["sales_channels"])
        self.assertEqual(validate_publishable(p6), ["SALES_CHANNEL_REQUIRED"])

        # 7. GALLERY_MAIN_MEDIA_REQUIRED
        p7 = self._make_complete_draft("MISS-MED")
        ProductMedia.objects.filter(product=p7).delete()
        self.assertEqual(validate_publishable(p7), ["GALLERY_MAIN_MEDIA_REQUIRED"])

    def test_draft_active_archived_active_transitions(self):
        product = self._make_complete_draft("TRANS-001")

        # DRAFT -> ACTIVE via /publish
        pub1 = self.client.post(f"/api/v1/ops/products/{product.parent_sku}/publish")
        self.assertEqual(pub1.status_code, 200)
        self.assertEqual(pub1.json()["data"]["catalogStatus"], "ACTIVE")

        # ACTIVE -> ARCHIVED via PATCH
        arch = self.client.patch(
            f"/api/v1/ops/products/{product.parent_sku}",
            {"catalogStatus": "ARCHIVED"},
            format="json",
        )
        self.assertEqual(arch.status_code, 200)
        self.assertEqual(arch.json()["data"]["catalogStatus"], "ARCHIVED")

        # ARCHIVED -> ACTIVE via /publish
        pub2 = self.client.post(f"/api/v1/ops/products/{product.parent_sku}/publish")
        self.assertEqual(pub2.status_code, 200)
        self.assertEqual(pub2.json()["data"]["catalogStatus"], "ACTIVE")

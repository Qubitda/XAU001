"""Cross-organization isolation regression tests across B2B & non-OPS endpoints."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductModel, ProductVariant
from apps.commerce.models import B2bDraftLine, B2bOrder
from apps.finance.models import DealerLedgerEntry
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Branch, Organization, OrganizationMembership
from apps.pricing.models import ChannelRule, CostLine, PricingRecipe
from apps.social_commerce.models import SocialCampaign

User = get_user_model()


class CrossOrganizationIsolationTests(TestCase):
    def setUp(self) -> None:
        self.snap = get_current_rate_snapshot()
        self.org_a = Organization.objects.create(code="ISO-A", name="Org A", org_type=Organization.OrgType.DEALER)
        self.org_b = Organization.objects.create(code="ISO-B", name="Org B", org_type=Organization.OrgType.DEALER)
        self.br_a = Branch.objects.create(organization=self.org_a, code="ISO-A1", name="Şube A1")
        self.br_b = Branch.objects.create(organization=self.org_b, code="ISO-B1", name="Şube B1")

        self.user_a = User.objects.create_user(email="iso-a@tara.local", password="pw")
        self.user_b = User.objects.create_user(email="iso-b@tara.local", password="pw")

        self.m_a = OrganizationMembership.objects.create(
            user=self.user_a,
            organization=self.org_a,
            role_key=OrganizationMembership.RoleKey.ORG_ADMIN,
            default_branch=self.br_a,
        )
        self.m_a.branches.add(self.br_a)

        self.m_b = OrganizationMembership.objects.create(
            user=self.user_b,
            organization=self.org_b,
            role_key=OrganizationMembership.RoleKey.ORG_ADMIN,
            default_branch=self.br_b,
        )
        self.m_b.branches.add(self.br_b)

        self.prod_a = ProductModel.objects.create(
            parent_sku="ISO-PRIV-A",
            title="Org A Özel Yüzük",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            seo_slug="iso-priv-a",
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2B", "B2B_API"],
            owner_organization=self.org_a,
        )
        self.var_a = ProductVariant.objects.create(
            product=self.prod_a,
            sku="ISO-PRIV-A-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.00"),
            is_default=True,
            is_active=True,
        )
        recipe = PricingRecipe.objects.create(product=self.prod_a, version=1, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(recipe=recipe, line_type=CostLine.LineType.ISCILIK, fc_currency="USD", fc_price=Decimal("20.00"))
        ChannelRule.objects.create(recipe=recipe, channel="B2B", profit_unit="%", profit_value=Decimal("10"))
        PricingRecipe.objects.filter(id=recipe.id).update(status=PricingRecipe.Status.PUBLISHED)

        self.draft_a = B2bDraftLine.objects.create(
            organization=self.org_a,
            created_by=self.user_a,
            variant=self.var_a,
            sku=self.var_a.sku,
            parent_sku=self.prod_a.parent_sku,
            title=self.prod_a.title,
            category=self.prod_a.category,
            metal_color="Beyaz",
            purity_code="14K",
            size=14,
            qty=1,
            unit_gross_gram=Decimal("3.0000"),
            unit_net_metal_gram=Decimal("2.8000"),
            unit_fire_included_fine_gram=Decimal("1.7000"),
            unit_labor_and_stone_usd=Decimal("20.00"),
            unit_wholesale_usd=Decimal("100.00"),
            unit_wholesale_try=Decimal("3400.00"),
            rate_snapshot=self.snap,
            snapshot_code=self.snap.snapshot_code,
        )
        self.order_a = B2bOrder.objects.create(
            order_no="ORD-ISO-A1",
            organization=self.org_a,
            branch=self.br_a,
            created_by=self.user_a,
            rate_snapshot=self.snap,
            gold_rate_try_per_gram=Decimal("3000"),
            usd_try_rate=Decimal("34"),
            total_pieces=1,
            total_gross_gram=Decimal("3"),
            total_has_gold_gram=Decimal("1.7"),
            total_labor_and_stone_usd=Decimal("20"),
            total_wholesale_usd=Decimal("100"),
            total_wholesale_try=Decimal("3400"),
        )
        self.ledger_a = DealerLedgerEntry.objects.create(
            organization=self.org_a,
            entry_type=DealerLedgerEntry.EntryType.ORDER_DEBIT,
            reference_no="ORD-ISO-A1",
            amount_usd=Decimal("100.00"),
            has_gold_gram=Decimal("1.7000"),
            created_by=self.user_a,
        )
        self.campaign_a = SocialCampaign.objects.create(
            name="Org A Özel Kampanya",
            code="ISO_CAMP_A",
            audience="B2B",
            organization=self.org_a,
            is_active=True,
        )
        self.client = APIClient()

    def test_cross_organization_access_blocked_across_endpoints(self) -> None:
        self.client.force_authenticate(user=self.user_b)

        detail_cases = [
            ("GET", f"/api/v1/b2b/products/{self.prod_a.parent_sku}", None, {404}),
            ("GET", f"/api/v1/b2b/orders/{self.order_a.order_no}/proforma.pdf", None, {403, 404}),
            ("POST", f"/api/v1/b2b/orders/{self.order_a.order_no}/reorder", {}, {403, 404}),
            ("PATCH", f"/api/v1/b2b/draft/lines/{self.draft_a.id}", {"qty": 2}, {403, 404}),
            ("PATCH", f"/api/v1/b2b/organization/users/{self.m_a.id}", {"jobTitle": "Hack"}, {403, 404}),
            ("GET", f"/api/v1/b2b/social/share/{self.prod_a.parent_sku}", None, {404}),
            ("POST", "/api/v1/storefront/favorites/toggle", {"parentSku": self.prod_a.parent_sku}, {404}),
        ]
        for method, url, payload, expected_statuses in detail_cases:
            with self.subTest(endpoint=f"{method} {url}"):
                fn = getattr(self.client, method.lower())
                resp = fn(url, data=payload, format="json") if payload is not None else fn(url)
                self.assertIn(resp.status_code, expected_statuses)

        list_cases = [
            ("/api/v1/b2b/products", "ISO-PRIV-A"),
            ("/api/v1/b2b/orders", "ORD-ISO-A1"),
            ("/api/v1/b2b/organization/users", "iso-a@tara.local"),
            ("/api/v1/b2b/ledger", "ORD-ISO-A1"),
            ("/api/v1/b2b/social/campaigns/", "ISO_CAMP_A"),
        ]
        for url, forbidden_marker in list_cases:
            with self.subTest(list_endpoint=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertNotIn(forbidden_marker, resp.content.decode("utf-8"))

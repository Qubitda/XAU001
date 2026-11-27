from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductModel
from apps.market.models import RateSnapshot
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import CostLine, PricingRecipe

User = get_user_model()


class Faz1CatalogIntegrityTests(TestCase):
    def setUp(self):
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-FAZ1",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        self.org_a = Organization.objects.create(code="ORG-A", name="Bayi A")
        self.org_b = Organization.objects.create(code="ORG-B", name="Bayi B")

        self.ops_user = User.objects.create_user(email="ops1@tara.local", password="p", full_name="OPS")
        OrganizationMembership.objects.create(
            user=self.ops_user, organization=self.org_a, role_key=OrganizationMembership.RoleKey.OPS
        )

        self.buyer_b = User.objects.create_user(email="buyerb@tara.local", password="p", full_name="Buyer B")
        OrganizationMembership.objects.create(
            user=self.buyer_b, organization=self.org_b, role_key=OrganizationMembership.RoleKey.B2B_BUYER
        )
        self.client = APIClient()

    def _make_product(self, sku: str, *, channels, owner=None, cert_agency="", cert_no=""):
        p = ProductModel.objects.create(
            parent_sku=sku,
            title=f"Ürün {sku}",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug=sku.lower(),
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=channels,
            owner_organization=owner,
            certificate_agency=cert_agency,
            certificate_number=cert_no,
        )
        PricingRecipe.objects.create(product=p, version=1, status=PricingRecipe.Status.PUBLISHED)
        return p

    def test_sales_channels_filtering_and_b2b_org_isolation(self):
        self._make_product("B2B-ONLY", channels=["B2B"])
        self._make_product("B2C-ONLY", channels=["B2C_API"])
        self._make_product("NO-CH", channels=[])
        self._make_product("ORG-A-PRIV", channels=["B2B"], owner=self.org_a)

        # Storefront sees ONLY B2C_API
        sf_list = self.client.get("/api/v1/storefront/products")
        self.assertEqual(sf_list.status_code, 200)
        sf_skus = [r["parentSku"] for r in sf_list.json()["data"]]
        self.assertEqual(sf_skus, ["B2C-ONLY"])
        self.assertEqual(self.client.get("/api/v1/storefront/products/B2B-ONLY").status_code, 404)

        # B2B buyer in org_b sees B2B-ONLY, NOT B2C-ONLY, NOT NO-CH, NOT ORG-A-PRIV
        self.client.force_authenticate(user=self.buyer_b)
        b2b_list = self.client.get("/api/v1/b2b/products")
        self.assertEqual(b2b_list.status_code, 200)
        b2b_skus = [r["parentSku"] for r in b2b_list.json()["data"]]
        self.assertEqual(b2b_skus, ["B2B-ONLY"])
        self.assertEqual(self.client.get("/api/v1/b2b/products/ORG-A-PRIV").status_code, 404)

    def test_partial_ledger_patch_preserves_other_costs_and_rejects_nan(self):
        self.client.force_authenticate(user=self.ops_user)
        p = ProductModel.objects.create(
            parent_sku="LED-01",
            title="Ürün LED-01",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug="led-01",
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2C_API"],
        )
        pub = PricingRecipe.objects.create(product=p, version=1, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(recipe=pub, line_type=CostLine.LineType.TAS, fc_currency="USD", fc_price=Decimal("250.00"))
        CostLine.objects.create(recipe=pub, line_type=CostLine.LineType.ISCILIK, fc_currency="EUR", fc_price=Decimal("20.00"))
        PricingRecipe.objects.filter(id=pub.id).update(status=PricingRecipe.Status.PUBLISHED)
        pub.refresh_from_db()

        # NaN / negative must return 400
        bad = self.client.patch(
            "/api/v1/ops/products/LED-01",
            data=json.dumps({"ledger": {"laborFcPrice": "NaN"}}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)

        # Partial ledger PATCH only updating laborFcPrice preserves stone cost & currency and stays DRAFT
        ok = self.client.patch(
            "/api/v1/ops/products/LED-01",
            data=json.dumps({"ledger": {"laborFcPrice": "35.00"}}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        pub.refresh_from_db()
        self.assertEqual(pub.status, PricingRecipe.Status.PUBLISHED)
        draft = PricingRecipe.objects.filter(product=p, status=PricingRecipe.Status.DRAFT).first()
        self.assertIsNotNone(draft)
        stone = CostLine.objects.get(recipe=draft, line_type=CostLine.LineType.TAS)
        labor = CostLine.objects.get(recipe=draft, line_type=CostLine.LineType.ISCILIK)
        self.assertEqual(stone.fc_price, Decimal("250.00"))
        self.assertEqual(stone.fc_currency, "USD")
        self.assertEqual(labor.fc_price, Decimal("35.00"))
        self.assertEqual(labor.fc_currency, "EUR")

    def test_certificate_defaults_and_has_certificate(self):
        p = self._make_product("CERT-01", channels=["B2C_API"])
        self.assertEqual(p.certificate_agency, "")
        self.assertEqual(p.stone_clarity, "")
        self.assertEqual(p.stock_qty, 0)
        res = self.client.get("/api/v1/storefront/products/CERT-01")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["data"]["hasCertificate"])

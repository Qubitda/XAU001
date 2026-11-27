from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductMedia, ProductModel, ProductVariant
from apps.market.models import RateSnapshot
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import PricingRecipe

User = get_user_model()


class Faz2WorkflowAndPermissionsTests(TestCase):
    def setUp(self):
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-FAZ2",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        self.org = Organization.objects.create(code="OPS-ORG2", name="Ops Org")

        # OPS user with full OPS role
        self.ops_user = User.objects.create_user(email="ops2@tara.local", password="p", full_name="OPS 2")
        OrganizationMembership.objects.create(
            user=self.ops_user, organization=self.org, role_key=OrganizationMembership.RoleKey.OPS
        )

        # Restricted OPS user with ONLY catalog:read + catalog:write (denied pricing:edit, inventory:manage, catalog:publish)
        self.limited_ops = User.objects.create_user(email="lim@tara.local", password="p", full_name="Limited OPS")
        OrganizationMembership.objects.create(
            user=self.limited_ops,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.OPS,
            denied_permissions=["pricing:edit", "inventory:manage", "catalog:publish"],
        )
        self.client = APIClient()

    def test_draft_create_and_publish_gates(self):
        self.client.force_authenticate(user=self.ops_user)
        res = self.client.post(
            "/api/v1/ops/products",
            data=json.dumps(
                {
                    "parentSku": "PUB-01",
                    "title": "Yayın Test Yüzük",
                    "category": "Yüzük",
                    "purityCode": "14K",
                    "metalColor": "Beyaz",
                    "grossWeightGram": "3.50",
                    "salesChannels": ["B2C_API"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["data"]["catalogStatus"], "DRAFT")

        # Cannot set ACTIVE via PATCH
        bad_patch = self.client.patch(
            "/api/v1/ops/products/PUB-01",
            data=json.dumps({"catalogStatus": "ACTIVE"}),
            content_type="application/json",
        )
        self.assertEqual(bad_patch.status_code, 400)

        # Publish fails with 422 because recipe is DRAFT and GALLERY_MAIN is missing
        fail_pub = self.client.post("/api/v1/ops/products/PUB-01/publish")
        self.assertEqual(fail_pub.status_code, 422)
        missing = fail_pub.json()["data"]["missing"]
        self.assertIn("PUBLISHED_RECIPE_REQUIRED", missing)
        self.assertIn("GALLERY_MAIN_MEDIA_REQUIRED", missing)

        # Publish recipe + add GALLERY_MAIN media -> publish succeeds
        rec_pub = self.client.post("/api/v1/ops/products/PUB-01/recipe/publish")
        self.assertEqual(rec_pub.status_code, 200)
        p = ProductModel.objects.get(parent_sku="PUB-01")
        ProductMedia.objects.create(
            product=p,
            role=ProductMedia.MediaRole.GALLERY_MAIN,
            url="https://cdn.taradiamond.com.tr/pub-01.jpg",
        )
        ok_pub = self.client.post("/api/v1/ops/products/PUB-01/publish")
        self.assertEqual(ok_pub.status_code, 200)
        self.assertEqual(ok_pub.json()["data"]["catalogStatus"], "ACTIVE")

        # OPS without catalog:delete gets 403; SUPER_ADMIN archives ACTIVE product
        self.assertEqual(self.client.delete("/api/v1/ops/products/PUB-01").status_code, 403)
        super_u = User.objects.create_user(email="sup2@tara.local", password="p", full_name="Sup", is_superuser=True)
        OrganizationMembership.objects.create(
            user=super_u, organization=self.org, role_key=OrganizationMembership.RoleKey.SUPER_ADMIN
        )
        self.client.force_authenticate(user=super_u)
        del_res = self.client.delete("/api/v1/ops/products/PUB-01")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["data"]["archived"])
        self.assertEqual(self.client.get("/api/v1/storefront/products/PUB-01").status_code, 404)

    def test_field_level_permissions_on_patch(self):
        p = ProductModel.objects.create(
            parent_sku="FLD-01",
            title="Field Perm",
            category="Yüzük",
            collection="Test",
            purity_code="14K",
            metal_color="Beyaz",
            seo_slug="fld-01",
        )
        ProductVariant.objects.create(
            product=p, sku="FLD-01-14K-BYZ-14", purity_code="14K", metal_color="Beyaz", gross_weight_gram=Decimal("3.0")
        )

        self.client.force_authenticate(user=self.limited_ops)
        for bad_payload in (
            {"ledger": {"laborFcPrice": "10.00"}},
            {"fireRatePct": "3.00"},
            {"salesChannels": ["B2C_API"]},
        ):
            r = self.client.patch(
                "/api/v1/ops/products/FLD-01",
                data=json.dumps(bad_payload),
                content_type="application/json",
            )
            self.assertEqual(r.status_code, 403, f"Expected 403 for {bad_payload}")

        # Allowed field (title) succeeds for limited_ops
        ok = self.client.patch(
            "/api/v1/ops/products/FLD-01",
            data=json.dumps({"title": "Updated Title"}),
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)

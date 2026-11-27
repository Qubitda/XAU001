"""FAZ 4 tests: unified serializer validation, https media, stone-line carat sync, dec_str details, admin dual-write."""
from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.admin import ProductModelAdmin
from apps.catalog.models import FinishedDetail, ProductModel, ProductVariant, StoneLine
from apps.catalog.product_details import resolve_fineness, serialize_finished_detail
from apps.market.models import RateSnapshot
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class Faz4ValidationTests(TestCase):
    def setUp(self):
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-FAZ4",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        self.ops_org = Organization.objects.create(
            code="ORG-OPS-F4",
            name="OPS Org F4",
            org_type=Organization.OrgType.PLATFORM_OWNER,
            is_active=True,
        )
        self.ops_user = User.objects.create_user(
            email="ops_f4@example.com",
            password="pw",
            full_name="OPS F4",
            is_staff=True,
        )
        OrganizationMembership.objects.create(
            user=self.ops_user,
            organization=self.ops_org,
            role_key=OrganizationMembership.RoleKey.OPS,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.ops_user)

    def _base_payload(self, sku: str = "F4-RING-001") -> dict:
        return {
            "parentSku": sku,
            "title": "Faz 4 Solitaire",
            "category": "Yüzük",
            "subCategory": "Tektaş",
            "collection": "Klasik",
            "purityCode": "14K",
            "metalColor": "Beyaz",
            "stoneType": "Pırlanta",
            "stoneMeasureUnit": "CARAT",
            "grossWeightGram": "4.25",
            "fireRatePct": "5.00",
            "stockStatus": "Stokta",
            "ownershipType": "Öz Mal",
            "description": "Test description",
        }

    def test_http_media_url_rejected_and_gallery_max_20(self):
        bad_payload = self._base_payload("F4-HTTP-001")
        bad_payload["reelsVideoUrl"] = "http://insecure.example.com/v.mp4"
        res = self.client.post("/api/v1/ops/products", bad_payload, format="json")
        self.assertEqual(res.status_code, 400)

        too_many = self._base_payload("F4-GALLERY-001")
        too_many["galleryImages"] = [f"https://cdn.example.com/{i}.jpg" for i in range(21)]
        res2 = self.client.post("/api/v1/ops/products", too_many, format="json")
        self.assertEqual(res2.status_code, 400)

    def test_patch_stock_qty_rejected_with_use_inventory_api(self):
        res = self.client.post("/api/v1/ops/products", self._base_payload("F4-STK-001"), format="json")
        self.assertEqual(res.status_code, 201)

        patch_res = self.client.patch(
            "/api/v1/ops/products/F4-STK-001",
            {"stockQty": 10},
            format="json",
        )
        self.assertEqual(patch_res.status_code, 400)
        self.assertEqual(patch_res.json()["code"], "USE_INVENTORY_API")

    def test_stone_line_crud_syncs_default_variant_center_carat(self):
        res = self.client.post("/api/v1/ops/products", self._base_payload("F4-STN-001"), format="json")
        self.assertEqual(res.status_code, 201)
        product = ProductModel.objects.get(parent_sku="F4-STN-001")
        variant = product.variants.get(is_default=True)
        self.assertEqual(variant.center_stone_carat, Decimal("0"))

        create_res = self.client.post(
            "/api/v1/ops/stone-lines",
            {
                "parentSku": "F4-STN-001",
                "role": "MERKEZ",
                "stoneType": "Pırlanta",
                "measureUnit": "ct",
                "count": 2,
                "carat": "0.500",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        stone_id = create_res.json()["data"]["id"]
        variant.refresh_from_db()
        self.assertEqual(variant.center_stone_carat, Decimal("1.000"))

        patch_res = self.client.patch(
            f"/api/v1/ops/stone-lines/{stone_id}",
            {"carat": "0.750"},
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        variant.refresh_from_db()
        self.assertEqual(variant.center_stone_carat, Decimal("1.500"))

        del_res = self.client.delete(f"/api/v1/ops/stone-lines/{stone_id}")
        self.assertEqual(del_res.status_code, 200)
        variant.refresh_from_db()
        self.assertEqual(variant.center_stone_carat, Decimal("0.000"))

    def test_product_details_uses_dec_str_and_admin_dual_writes(self):
        product = ProductModel.objects.create(
            parent_sku="F4-ADM-001",
            title="Admin Dual Write",
            category="Yüzük",
            sub_category="Tektaş",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            stone_type="Pırlanta",
            stone_measure_unit="CARAT",
            gross_weight_gram=Decimal("3.50"),
            fire_rate_pct=Decimal("4.50"),
            stock_status=ProductModel.StockStatus.IN_STOCK,
            ownership_type=ProductModel.OwnershipType.OWNED,
            description="Admin test",
        )
        admin_obj = ProductModelAdmin(ProductModel, AdminSite())
        admin_obj.save_model(MagicMock(user=self.ops_user), product, MagicMock(), change=False)

        detail = FinishedDetail.objects.get(product=product)
        serialized = serialize_finished_detail(detail, for_ops=True)
        self.assertIsInstance(serialized["fineness"], str)
        self.assertIsInstance(serialized["baseWeightGr"], str)
        self.assertEqual(serialized["baseWeightGr"], "3.5000")
        self.assertEqual(serialized["fireRatePct"], "4.50")

        self.assertEqual(resolve_fineness("14K"), Decimal("0.5850"))
        call_command("cleanup_legacy_product_columns")

"""FAZ 5 tests: SupplierOffer lifecycle, tenant isolation, OPS identity gating, and blind-pool buyer cards."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductModel, ProductVariant, SupplierOffer
from apps.market.models import RateSnapshot
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import CostLine, PricingRecipe

User = get_user_model()


class Faz5SupplierOffersTests(TestCase):
    def setUp(self):
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-FAZ5",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        self.ops_org = Organization.objects.create(
            code="ORG-OPS-F5",
            name="OPS Org",
            org_type=Organization.OrgType.PLATFORM_OWNER,
            is_active=True,
        )
        self.sup_org_a = Organization.objects.create(
            code="SUP-A",
            name="Tedarikçi A A.Ş.",
            org_type=Organization.OrgType.SUPPLIER,
            is_active=True,
        )
        self.sup_org_b = Organization.objects.create(
            code="SUP-B",
            name="Tedarikçi B Ltd.",
            org_type=Organization.OrgType.SUPPLIER,
            is_active=True,
        )
        self.ops_user = User.objects.create_user(email="ops_f5@tara.local", password="pw", full_name="OPS F5")
        OrganizationMembership.objects.create(
            user=self.ops_user, organization=self.ops_org, role_key=OrganizationMembership.RoleKey.OPS
        )

        self.masked_ops = User.objects.create_user(
            email="masked_ops@tara.local", password="pw", full_name="Masked OPS"
        )
        OrganizationMembership.objects.create(
            user=self.masked_ops,
            organization=self.ops_org,
            role_key=OrganizationMembership.RoleKey.OPS,
            denied_permissions=["supplier_identity:view"],
        )

        self.sup_admin_a = User.objects.create_user(
            email="supa_admin@tara.local", password="pw", full_name="Sup A Admin"
        )
        OrganizationMembership.objects.create(
            user=self.sup_admin_a,
            organization=self.sup_org_a,
            role_key=OrganizationMembership.RoleKey.SUPPLIER_ADMIN,
        )

        self.sup_user_a = User.objects.create_user(
            email="supa_user@tara.local", password="pw", full_name="Sup A User"
        )
        OrganizationMembership.objects.create(
            user=self.sup_user_a,
            organization=self.sup_org_a,
            role_key=OrganizationMembership.RoleKey.SUPPLIER_USER,
        )

        self.sup_admin_b = User.objects.create_user(
            email="supb_admin@tara.local", password="pw", full_name="Sup B Admin"
        )
        OrganizationMembership.objects.create(
            user=self.sup_admin_b,
            organization=self.sup_org_b,
            role_key=OrganizationMembership.RoleKey.SUPPLIER_ADMIN,
        )

        self.product = ProductModel.objects.create(
            parent_sku="SUP-RING-001",
            title="Supplier Solitaire",
            category="Yüzük",
            sub_category="Tektaş",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            stone_type="Pırlanta",
            stone_measure_unit="ct",
            gross_weight_gram=Decimal("3.80"),
            fire_rate_pct=Decimal("5.00"),
            stock_status=ProductModel.StockStatus.IN_STOCK,
            ownership_type=ProductModel.OwnershipType.OWNED,
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2C_API", "B2B"],
            description="Test",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="SUP-RING-001-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.80"),
            stock_qty=2,
            is_default=True,
        )
        recipe = PricingRecipe.objects.create(
            product=self.product,
            version=1,
            status=PricingRecipe.Status.DRAFT,
            pricing_mode="1",
        )
        CostLine.objects.create(
            recipe=recipe,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="USD",
            fc_price=Decimal("25.00"),
        )
        recipe.status = PricingRecipe.Status.PUBLISHED
        recipe.save(update_fields=["status", "updated_at"])
        self.client = APIClient()

    def test_supplier_offer_crud_permissions_and_tenant_isolation(self):
        # SUPPLIER_USER can read products but cannot create offers (403)
        self.client.force_authenticate(user=self.sup_user_a)
        prod_res = self.client.get("/api/v1/supplier/products")
        self.assertEqual(prod_res.status_code, 200)
        self.assertEqual(len(prod_res.json()["data"]), 1)

        forbid_res = self.client.post(
            "/api/v1/supplier/offers",
            {"parentSku": "SUP-RING-001", "costAmount": "450.00", "availableQty": 5},
            format="json",
        )
        self.assertEqual(forbid_res.status_code, 403)

        # SUPPLIER_ADMIN A creates offer
        self.client.force_authenticate(user=self.sup_admin_a)
        create_res = self.client.post(
            "/api/v1/supplier/offers",
            {
                "parentSku": "SUP-RING-001",
                "variantId": str(self.variant.id),
                "supplierSku": "SECRET-SUP-A-SKU",
                "costAmount": "420.00",
                "currency": "USD",
                "leadTimeDays": 4,
                "availableQty": 8,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201)
        offer_id = create_res.json()["data"]["id"]

        # SUPPLIER_ADMIN B cannot see or mutate A's offer (404)
        self.client.force_authenticate(user=self.sup_admin_b)
        list_b = self.client.get("/api/v1/supplier/offers")
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(len(list_b.json()["data"]), 0)

        get_b = self.client.get(f"/api/v1/supplier/offers/{offer_id}")
        self.assertEqual(get_b.status_code, 404)
        patch_b = self.client.patch(f"/api/v1/supplier/offers/{offer_id}", {"costAmount": "100.00"}, format="json")
        self.assertEqual(patch_b.status_code, 404)

    def test_ops_identity_gating_and_blind_pool_buyer_cards(self):
        offer = SupplierOffer.objects.create(
            product=self.product,
            variant=self.variant,
            supplier_organization=self.sup_org_a,
            supplier_sku="SECRET-SUP-A-SKU",
            cost_amount=Decimal("410.00"),
            currency="USD",
            lead_time_days=5,
            available_qty=6,
            status=SupplierOffer.Status.SUBMITTED,
        )

        # Masked OPS (without supplier_identity:view) sees cost/leadTime but NOT supplier identity
        self.client.force_authenticate(user=self.masked_ops)
        masked_res = self.client.get("/api/v1/ops/products/SUP-RING-001/offers")
        self.assertEqual(masked_res.status_code, 200)
        masked_item = masked_res.json()["data"]["offers"][0]
        self.assertEqual(masked_item["supplierLabel"], "Tedarikçi #1")
        self.assertNotIn("supplierName", masked_item)
        self.assertNotIn("supplierOrganizationId", masked_item)
        self.assertNotIn("supplierSku", masked_item)

        # Full OPS sees supplier identity and approves offer
        self.client.force_authenticate(user=self.ops_user)
        full_res = self.client.get("/api/v1/ops/products/SUP-RING-001/offers")
        self.assertEqual(full_res.status_code, 200)
        full_item = full_res.json()["data"]["offers"][0]
        self.assertEqual(full_item["supplierName"], "Tedarikçi A A.Ş.")
        self.assertEqual(full_item["supplierSku"], "SECRET-SUP-A-SKU")

        dec_res = self.client.post(
            f"/api/v1/ops/offers/{offer.id}/decision",
            {"decision": "APPROVED"},
            format="json",
        )
        self.assertEqual(dec_res.status_code, 200)
        self.assertEqual(dec_res.json()["data"]["status"], "APPROVED")

        # Storefront buyer sees anonymous offerRef card ONLY (no supplier identity, no cost, no exact qty)
        self.client.force_authenticate(user=None)
        sf_res = self.client.get("/api/v1/storefront/products/SUP-RING-001")
        self.assertEqual(sf_res.status_code, 200)
        sf_data = sf_res.json()["data"]
        self.assertEqual(len(sf_data["offers"]), 1)
        card = sf_data["offers"][0]
        self.assertEqual(set(card.keys()), {"offerRef", "leadTimeDays", "inStock", "variantId"})
        self.assertEqual(card["offerRef"], str(offer.offer_ref))
        self.assertEqual(card["leadTimeDays"], 5)
        self.assertTrue(card["inStock"])

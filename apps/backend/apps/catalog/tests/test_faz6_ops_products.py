"""FAZ 6 tests: OPS product & variant CRUD, axis unique constraint 409, and validate_publishable publish/unpublish."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import ProductMedia, ProductModel, ProductVariant
from apps.market.models import RateSnapshot
from apps.organizations.models import Organization, OrganizationMembership
from apps.pricing.models import CostLine, PricingRecipe

User = get_user_model()


class Faz6OpsProductsAndVariantsTests(TestCase):
    def setUp(self) -> None:
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-FAZ6",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        self.ops_org = Organization.objects.create(
            code="ORG-OPS-F6",
            name="OPS Org F6",
            org_type=Organization.OrgType.PLATFORM_OWNER,
        )
        self.ops_user = User.objects.create_user(email="ops_f6@tara.local", password="pw", full_name="OPS F6")
        OrganizationMembership.objects.create(
            user=self.ops_user,
            organization=self.ops_org,
            role_key=OrganizationMembership.RoleKey.OPS,
        )

        self.super_user = User.objects.create_user(
            email="super_f6@tara.local", password="pw", full_name="Super F6", is_superuser=True
        )
        OrganizationMembership.objects.create(
            user=self.super_user,
            organization=self.ops_org,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
        )

        self.readonly_ops = User.objects.create_user(
            email="ro_ops_f6@tara.local", password="pw", full_name="RO OPS F6"
        )
        OrganizationMembership.objects.create(
            user=self.readonly_ops,
            organization=self.ops_org,
            role_key=OrganizationMembership.RoleKey.OPS,
            denied_permissions=["catalog:write", "catalog:publish", "inventory:manage"],
        )

        self.b2b_user = User.objects.create_user(email="b2b_f6@tara.local", password="pw", full_name="B2B F6")
        OrganizationMembership.objects.create(
            user=self.b2b_user,
            organization=self.ops_org,
            role_key=OrganizationMembership.RoleKey.ORG_ADMIN,
        )
        self.client = APIClient()

    def _create_product_payload(self, sku: str = "F6-PROD-001") -> dict:
        return {
            "parentSku": sku,
            "title": "Faz 6 Test Yüzük",
            "category": "Yüzük",
            "subCategory": "Tektaş",
            "collection": "Klasik",
            "purityCode": "14K",
            "metalColor": "Beyaz",
            "grossWeightGram": "4.10",
            "fireRatePct": "5.00",
            "stockStatus": "Stokta",
            "ownershipType": "Öz Mal",
            "description": "Faz 6 test ürünü",
        }

    def test_ops_product_crud_and_permission_gates(self) -> None:
        # B2B user cannot access OPS product endpoints
        self.client.force_authenticate(user=self.b2b_user)
        self.assertEqual(self.client.get("/api/v1/ops/products").status_code, 403)

        # OPS without catalog:write can read but cannot create/update
        self.client.force_authenticate(user=self.readonly_ops)
        self.assertEqual(self.client.get("/api/v1/ops/products").status_code, 200)
        self.assertEqual(
            self.client.post("/api/v1/ops/products", self._create_product_payload(), format="json").status_code,
            403,
        )

        # Full OPS creates product, duplicate SKU returns 409, PATCH updates title
        self.client.force_authenticate(user=self.ops_user)
        create_res = self.client.post("/api/v1/ops/products", self._create_product_payload(), format="json")
        self.assertEqual(create_res.status_code, 201)
        self.assertEqual(create_res.json()["data"]["catalogStatus"], "DRAFT")

        dup_res = self.client.post("/api/v1/ops/products", self._create_product_payload(), format="json")
        self.assertEqual(dup_res.status_code, 409)
        self.assertEqual(dup_res.json()["code"], "DUPLICATE_SKU")

        patch_res = self.client.patch(
            "/api/v1/ops/products/F6-PROD-001",
            {"title": "Güncellenmiş Yüzük"},
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["data"]["title"], "Güncellenmiş Yüzük")

        # OPS lacks catalog:delete (403); SUPER_ADMIN deletes DRAFT without refs
        self.assertEqual(self.client.delete("/api/v1/ops/products/F6-PROD-001").status_code, 403)
        self.client.force_authenticate(user=self.super_user)
        del_res = self.client.delete("/api/v1/ops/products/F6-PROD-001")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["data"]["deleted"])

    def test_ops_variant_crud_and_axis_unique_constraint_409(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        prod_res = self.client.post("/api/v1/ops/products", self._create_product_payload("F6-VAR-001"), format="json")
        self.assertEqual(prod_res.status_code, 201)

        # Default variant already occupies (14K, Beyaz, size=0, center_stone_carat=0.000)
        dup_axis_res = self.client.post(
            "/api/v1/ops/variants",
            {
                "parentSku": "F6-VAR-001",
                "sku": "F6-VAR-001-DUP-AXIS",
                "purityCode": "14K",
                "metalColor": "Beyaz",
                "size": 0,
                "centerStoneCarat": "0.000",
                "grossWeightGram": "4.10",
            },
            format="json",
        )
        self.assertEqual(dup_axis_res.status_code, 409)
        self.assertEqual(dup_axis_res.json()["code"], "DUPLICATE_VARIANT_AXES")

        # Different size succeeds
        ok_var = self.client.post(
            "/api/v1/ops/variants",
            {
                "parentSku": "F6-VAR-001",
                "sku": "F6-VAR-001-14K-BYZ-16",
                "purityCode": "14K",
                "metalColor": "Beyaz",
                "size": 16,
                "centerStoneCarat": "0.000",
                "grossWeightGram": "4.35",
            },
            format="json",
        )
        self.assertEqual(ok_var.status_code, 201)
        var_id = ok_var.json()["data"]["id"]

        # Duplicate SKU returns 409 DUPLICATE_VARIANT_SKU
        dup_sku = self.client.post(
            "/api/v1/ops/variants",
            {
                "parentSku": "F6-VAR-001",
                "sku": "F6-VAR-001-14K-BYZ-16",
                "purityCode": "18K",
                "metalColor": "Sarı",
                "size": 16,
                "centerStoneCarat": "0.000",
                "grossWeightGram": "4.50",
            },
            format="json",
        )
        self.assertEqual(dup_sku.status_code, 409)
        self.assertEqual(dup_sku.json()["code"], "DUPLICATE_VARIANT_SKU")

        # PATCH colliding with default variant axes also returns 409 DUPLICATE_VARIANT_AXES
        patch_dup = self.client.patch(
            f"/api/v1/ops/variants/{var_id}",
            {"size": 0},
            format="json",
        )
        self.assertEqual(patch_dup.status_code, 409)
        self.assertEqual(patch_dup.json()["code"], "DUPLICATE_VARIANT_AXES")

        # Soft-deactivate variant requires catalog:delete
        self.assertEqual(self.client.delete(f"/api/v1/ops/variants/{var_id}").status_code, 403)
        self.client.force_authenticate(user=self.super_user)
        del_var = self.client.delete(f"/api/v1/ops/variants/{var_id}")
        self.assertEqual(del_var.status_code, 200)
        self.assertFalse(del_var.json()["data"]["isActive"])

    def test_validate_publishable_publish_and_unpublish_flow(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        res = self.client.post("/api/v1/ops/products", self._create_product_payload("F6-PUB-001"), format="json")
        self.assertEqual(res.status_code, 201)
        product = ProductModel.objects.get(parent_sku="F6-PUB-001")
        product.sales_channels = []
        product.save(update_fields=["sales_channels"])

        # Initially missing PUBLISHED_RECIPE_REQUIRED, SALES_CHANNEL_REQUIRED, GALLERY_MAIN_MEDIA_REQUIRED
        fail_pub = self.client.post("/api/v1/ops/products/F6-PUB-001/publish")
        self.assertEqual(fail_pub.status_code, 422)
        self.assertEqual(
            set(fail_pub.json()["data"]["missing"]),
            {"PUBLISHED_RECIPE_REQUIRED", "SALES_CHANNEL_REQUIRED", "GALLERY_MAIN_MEDIA_REQUIRED"},
        )

        # Add cost line to DRAFT recipe & publish recipe
        draft_recipe = PricingRecipe.objects.get(product=product, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(
            recipe=draft_recipe,
            line_type=CostLine.LineType.ISCILIK,
            fc_currency="USD",
            fc_price=Decimal("30.00"),
        )
        rec_pub = self.client.post("/api/v1/ops/products/F6-PUB-001/recipe/publish")
        self.assertEqual(rec_pub.status_code, 200)

        # Enable salesChannels and add GALLERY_MAIN media
        self.client.patch(
            "/api/v1/ops/products/F6-PUB-001",
            {"salesChannels": ["B2C_API"], "galleryImages": ["https://cdn.example.com/main.jpg"]},
            format="json",
        )
        self.assertTrue(product.media_items.filter(role=ProductMedia.MediaRole.GALLERY_MAIN).exists())

        # Now publish succeeds and storefront serves the product
        ok_pub = self.client.post("/api/v1/ops/products/F6-PUB-001/publish")
        self.assertEqual(ok_pub.status_code, 200)
        self.assertEqual(ok_pub.json()["data"]["catalogStatus"], "ACTIVE")

        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/v1/storefront/products/F6-PUB-001").status_code, 200)

        # Unpublish back to DRAFT hides from storefront
        self.client.force_authenticate(user=self.ops_user)
        unpub = self.client.patch(
            "/api/v1/ops/products/F6-PUB-001",
            {"catalogStatus": "DRAFT"},
            format="json",
        )
        self.assertEqual(unpub.status_code, 200)
        self.assertEqual(unpub.json()["data"]["catalogStatus"], "DRAFT")

        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/v1/storefront/products/F6-PUB-001").status_code, 404)

    def test_patch_active_product_allows_field_updates_without_publish_error(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        self.client.post("/api/v1/ops/products", self._create_product_payload("F6-ACT-001"), format="json")
        product = ProductModel.objects.get(parent_sku="F6-ACT-001")
        product.catalog_status = ProductModel.CatalogStatus.ACTIVE
        product.save(update_fields=["catalog_status"])

        # Updating an already-ACTIVE product with catalogStatus='ACTIVE' in payload must succeed
        res = self.client.patch(
            "/api/v1/ops/products/F6-ACT-001",
            {"title": "Güncel Aktif Ürün", "catalogStatus": "ACTIVE"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["title"], "Güncel Aktif Ürün")

        # Transitioning DRAFT -> ACTIVE via PATCH must still require /publish
        product.catalog_status = ProductModel.CatalogStatus.DRAFT
        product.save(update_fields=["catalog_status"])
        fail_res = self.client.patch(
            "/api/v1/ops/products/F6-ACT-001",
            {"catalogStatus": "ACTIVE"},
            format="json",
        )
        self.assertEqual(fail_res.status_code, 400)
        self.assertEqual(fail_res.json()["code"], "USE_PUBLISH_ENDPOINT")

    def test_public_catalog_media_serving_and_traversal_guard(self) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(user=self.ops_user)
        upload = SimpleUploadedFile("ring.png", b"\x89PNG\r\n\x1a\nfake", content_type="image/png")
        up_res = self.client.post(
            "/api/v1/ops/catalog/media-upload",
            {"file": upload, "kind": "image"},
            format="multipart",
        )
        self.assertEqual(up_res.status_code, 201)
        rel_path = up_res.json()["data"]["path"]
        self.assertTrue(rel_path.startswith("/media/catalog/"))

        # Anonymous storefront visitor can fetch uploaded catalog media with nosniff header
        self.client.force_authenticate(user=None)
        media_res = self.client.get(rel_path)
        self.assertEqual(media_res.status_code, 200)
        self.assertEqual(media_res["X-Content-Type-Options"], "nosniff")
        self.assertEqual(b"".join(media_res.streaming_content), b"\x89PNG\r\n\x1a\nfake")

        # Traversal and private prefixes remain 404
        self.assertEqual(self.client.get("/media/catalog/../settings.py").status_code, 404)
        self.assertEqual(self.client.get("/media/organizations/secret.pdf").status_code, 404)

    def test_create_cannot_force_active_and_unpublish_endpoint_works(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        payload = self._create_product_payload("F6-NOACT-001")
        payload["catalogStatus"] = "ACTIVE"
        res = self.client.post("/api/v1/ops/products", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "USE_PUBLISH_ENDPOINT")

        # Create as DRAFT with initial stockQty=5
        payload["catalogStatus"] = "DRAFT"
        payload["stockQty"] = 5
        ok_res = self.client.post("/api/v1/ops/products", payload, format="json")
        self.assertEqual(ok_res.status_code, 201)
        self.assertEqual(ok_res.json()["data"]["catalogStatus"], "DRAFT")
        self.assertEqual(ok_res.json()["data"]["stockQty"], 5)

        # Unpublish endpoint transitions ACTIVE -> DRAFT
        product = ProductModel.objects.get(parent_sku="F6-NOACT-001")
        product.catalog_status = ProductModel.CatalogStatus.ACTIVE
        product.save(update_fields=["catalog_status"])
        unpub = self.client.post("/api/v1/ops/products/F6-NOACT-001/unpublish")
        self.assertEqual(unpub.status_code, 200)
        self.assertEqual(unpub.json()["data"]["catalogStatus"], "DRAFT")

    def test_bulk_variant_matrix_and_safe_delete_or_deactivate(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        self.client.post("/api/v1/ops/products", self._create_product_payload("F6-MAT-001"), format="json")

        bulk_res = self.client.post(
            "/api/v1/ops/variants/bulk",
            {
                "parentSku": "F6-MAT-001",
                "purities": ["14K", "18K"],
                "colors": ["Beyaz", "Rose"],
                "sizes": [14, 16],
                "grossWeightGram": "4.20",
                "initialStockQty": 0,
            },
            format="json",
        )
        self.assertEqual(bulk_res.status_code, 201)
        self.assertEqual(bulk_res.json()["data"]["createdCount"], 8)

        # Re-running same matrix skips duplicates
        dup_res = self.client.post(
            "/api/v1/ops/variants/bulk",
            {
                "parentSku": "F6-MAT-001",
                "purities": ["14K"],
                "colors": ["Beyaz"],
                "sizes": [14],
                "grossWeightGram": "4.20",
            },
            format="json",
        )
        self.assertEqual(dup_res.status_code, 201)
        self.assertEqual(dup_res.json()["data"]["createdCount"], 0)
        self.assertEqual(dup_res.json()["data"]["skippedCount"], 1)

        # Variant without stock/order refs is physically deleted
        self.client.force_authenticate(user=self.super_user)
        v_id = bulk_res.json()["data"]["items"][0]["id"]
        del_res = self.client.delete(f"/api/v1/ops/variants/{v_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["data"]["deleted"])

    def test_seo_warranty_and_color_media_roundtrip_and_blind_pool(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        payload = self._create_product_payload("F6-SEO-001")
        payload.update(
            {
                "marketplaceCategory": "Takı > Yüzük",
                "sizeGuideUrl": "https://cdn.example.com/size-guide",
                "metaDescription": "Özel pırlanta yüzük açıklaması",
                "ogImage": "https://cdn.example.com/og.jpg",
                "canonicalUrl": "https://taradiamond.com.tr/urun/f6-seo-001",
                "robots": "index,follow",
                "keywords": "pırlanta, yüzük",
                "lifetimeMaintenance": "Evet (Ücretsiz)",
                "mediaItems": [
                    {
                        "url": "/media/catalog/sample-white.jpg",
                        "metalColor": "Beyaz",
                        "role": "GALLERY_MAIN",
                        "sortOrder": 1,
                    },
                    {
                        "url": "/media/catalog/sample-rose.jpg",
                        "metalColor": "Rose",
                        "role": "ON_HAND",
                        "sortOrder": 2,
                    },
                ],
            }
        )
        res = self.client.post("/api/v1/ops/products", payload, format="json")
        self.assertEqual(res.status_code, 201)
        d = res.json()["data"]
        self.assertEqual(d["marketplaceCategory"], "Takı > Yüzük")
        self.assertEqual(d["metaDescription"], "Özel pırlanta yüzük açıklaması")
        self.assertEqual(d["lifetimeMaintenance"], "Evet (Ücretsiz)")
        self.assertEqual(d["robots"], "index,follow")
        self.assertEqual(len(d["mediaItems"]), 2)
        self.assertEqual(d["mediaItems"][1]["metalColor"], "Rose")

        # Make active with published recipe + B2C_API channel and verify blind-pool on storefront
        product = ProductModel.objects.get(parent_sku="F6-SEO-001")
        product.sales_channels = ["B2C_API"]
        product.catalog_status = ProductModel.CatalogStatus.ACTIVE
        product.save(update_fields=["sales_channels", "catalog_status"])
        PricingRecipe.objects.filter(product=product).update(status=PricingRecipe.Status.PUBLISHED)
        self.client.force_authenticate(user=None)
        sf = self.client.get("/api/v1/storefront/products/F6-SEO-001")
        self.assertEqual(sf.status_code, 200)
        sf_data = sf.json()["data"]
        self.assertNotIn("stockQty", sf_data)
        self.assertNotIn("ownerOrganizationId", sf_data)
        self.assertNotIn("erpCode", sf_data)
        self.assertEqual(sf_data["metaDescription"], "Özel pırlanta yüzük açıklaması")

    def test_partial_patch_preserves_omitted_fields_and_recipe_versioning(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        payload = self._create_product_payload("F6-PATCH-001")
        payload.update(
            {
                "metaDescription": "Korunması gereken meta açıklama",
                "lifetimeMaintenance": "Ömür boyu ücretsiz bakım",
                "mediaItems": [
                    {"url": "/media/catalog/keep.jpg", "metalColor": "Beyaz", "role": "GALLERY_MAIN", "sortOrder": 1}
                ],
            }
        )
        self.client.post("/api/v1/ops/products", payload, format="json")
        product = ProductModel.objects.get(parent_sku="F6-PATCH-001")
        PricingRecipe.objects.filter(product=product).update(status=PricingRecipe.Status.PUBLISHED)
        product.catalog_status = ProductModel.CatalogStatus.ACTIVE
        product.save(update_fields=["catalog_status"])

        # Partial PATCH only changing title must preserve SEO, warranty, media, and keep PUBLISHED recipe intact
        res = self.client.patch(
            "/api/v1/ops/products/F6-PATCH-001",
            {"title": "Kısmi Güncellenmiş Başlık"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        d = res.json()["data"]
        self.assertEqual(d["title"], "Kısmi Güncellenmiş Başlık")
        self.assertEqual(d["metaDescription"], "Korunması gereken meta açıklama")
        self.assertEqual(d["lifetimeMaintenance"], "Ömür boyu ücretsiz bakım")
        self.assertEqual(len(d["mediaItems"]), 1)
        self.assertTrue(PricingRecipe.objects.filter(product=product, status=PricingRecipe.Status.PUBLISHED).exists())

    def test_publish_unpublish_permissions_and_idempotent_stock_movement(self) -> None:
        from apps.accounts.models import User
        from apps.inventory.models import Warehouse

        self.client.force_authenticate(user=self.ops_user)
        payload = self._create_product_payload("F6-PERM-001")
        payload["stockQty"] = 2
        self.client.post("/api/v1/ops/products", payload, format="json")

        # Unauthenticated / non-OPS user cannot publish or unpublish
        b2c_user = User.objects.create_user(email="b2c-audit@taragold.com", password="pass")
        self.client.force_authenticate(user=b2c_user)
        self.assertEqual(self.client.post("/api/v1/ops/products/F6-PERM-001/publish").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/ops/products/F6-PERM-001/unpublish").status_code, 403)

        # Idempotent stock movement: duplicate referenceNo does not double-count
        self.client.force_authenticate(user=self.super_user)
        wh = Warehouse.objects.filter(is_active=True).first()
        variant = ProductModel.objects.get(parent_sku="F6-PERM-001").variants.first()
        mv1 = self.client.post(
            "/api/v1/ops/stock-movements",
            {
                "variantId": str(variant.id),
                "warehouseId": str(wh.id),
                "movementType": "INBOUND",
                "quantity": 3,
                "referenceNo": "IDEMP-AUDIT-001",
            },
            format="json",
        )
        self.assertEqual(mv1.status_code, 201)
        mv2 = self.client.post(
            "/api/v1/ops/stock-movements",
            {
                "variantId": str(variant.id),
                "warehouseId": str(wh.id),
                "movementType": "INBOUND",
                "quantity": 3,
                "referenceNo": "IDEMP-AUDIT-001",
            },
            format="json",
        )
        self.assertEqual(mv2.status_code, 201)
        variant.refresh_from_db()
        self.assertEqual(variant.stock_qty, 5)

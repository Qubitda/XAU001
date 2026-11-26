"""
DYO Faz 2 integration: compatible-stones, soft-lock race, cart guards, checkout.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from decimal import Decimal
from unittest import skipIf

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import LooseStoneDetail, MountingDetail, ProductModel, ProductVariant
from apps.catalog.product_kinds import LOOSE_STONE, MOUNTING
from apps.commerce.dyo import calculate_dyo_bundle, release_expired_stone_locks
from apps.commerce.models import B2cCartItem, CustomBundle, StoneSoftLock
from apps.commerce.services import submit_b2c_order
from apps.commerce.tasks import release_expired_stone_locks_task
from apps.inventory.models import Warehouse, WarehouseStock
from apps.market.services import create_rate_snapshot
from apps.pricing.models import PriceLock


LOC_MEM_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dyo-tests"}
}


def _product(*, kind: str, sku: str, stock_qty: int = 1) -> ProductModel:
    return ProductModel.objects.create(
        parent_sku=sku,
        product_kind=kind,
        title=f"Test {sku}",
        collection="DYO Test",
        category="Yüzük",
        purity_code="14K",
        metal_color="Beyaz",
        seo_slug=f"dyo-{sku.lower()}",
        stock_status=ProductModel.StockStatus.IN_STOCK,
        stock_qty=stock_qty,
        gross_weight_gram=Decimal("3.0000"),
        sales_channels=["B2B", "B2B_API", "B2C_API"],
    )


def _variant(product: ProductModel, *, sku_suffix: str = "V1") -> ProductVariant:
    return ProductVariant.objects.create(
        product=product,
        sku=f"{product.parent_sku}-{sku_suffix}",
        purity_code=product.purity_code,
        metal_color=product.metal_color,
        size=product.variant_size,
        gross_weight_gram=product.gross_weight_gram,
        stock_qty=product.stock_qty,
        is_default=True,
        is_active=True,
    )


def _seed_warehouse_stock(variant: ProductVariant, qty: int = 1) -> WarehouseStock:
    wh, _ = Warehouse.objects.get_or_create(code="DYO-WH", defaults={"name": "DYO Test WH", "is_active": True})
    return WarehouseStock.objects.create(variant=variant, warehouse=wh, quantity=qty, reserved_qty=0)


@override_settings(
    CACHES=LOC_MEM_CACHE,
    PRICING_READ_FROM_DETAILS=True,
    DYO_STONE_LOCK_TTL_SECONDS=900,
)
class DyoCompatibleStonesApiTests(TestCase):
    def setUp(self):
        create_rate_snapshot(
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
            live_has_gold_try_sell=Decimal("3000"),
        )
        self.user = User.objects.create_user(
            email="dyo-buyer@test.local", password="pass-1234", full_name="DYO Buyer"
        )
        self.other = User.objects.create_user(
            email="dyo-other@test.local", password="pass-1234", full_name="Other Buyer"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.mount = _product(kind=MOUNTING, sku="MNT-DYO-01")
        _variant(self.mount)
        MountingDetail.objects.create(
            product=self.mount,
            metal_name="Altın",
            purity_code="14K",
            metal_color="Beyaz",
            fineness=Decimal("0.5850"),
            net_weight_gr=Decimal("3.0000"),
            labor_cost_type=ProductModel.LaborCostType.FIXED,
            labor_cost_value=Decimal("10"),
            compatible_shapes=["ROUND", "OVAL"],
            min_carat=Decimal("0.300"),
            max_carat=Decimal("1.000"),
            min_length_mm=Decimal("5.000"),
            max_length_mm=Decimal("7.000"),
            min_width_mm=Decimal("5.000"),
            max_width_mm=Decimal("7.000"),
            setting_labor_usd=Decimal("45.00"),
        )

        self.match = self._stone("STN-MATCH", shape="ROUND", carat="0.500", length="6.000", width="6.000")
        self.wrong_shape = self._stone("STN-SHAPE", shape="PRINCESS", carat="0.500", length="6.000", width="6.000")
        self.wrong_carat = self._stone("STN-CARAT", shape="ROUND", carat="1.500", length="6.000", width="6.000")
        self.wrong_mm = self._stone("STN-MM", shape="ROUND", carat="0.500", length="9.500", width="6.000")
        self.locked = self._stone("STN-LOCKED", shape="OVAL", carat="0.700", length="6.200", width="5.800")

        StoneSoftLock.objects.create(
            stone_product=self.locked,
            user=self.other,
            bundle=None,
            expires_at=timezone.now() + timedelta(minutes=10),
            status=StoneSoftLock.Status.ACTIVE,
        )

    def _stone(self, sku, *, shape, carat, length, width) -> ProductModel:
        p = _product(kind=LOOSE_STONE, sku=sku)
        _variant(p)
        LooseStoneDetail.objects.create(
            product=p,
            stone_category="Pırlanta",
            shape=shape,
            carat=Decimal(carat),
            color="F",
            clarity="VS1",
            length_mm=Decimal(length),
            width_mm=Decimal(width),
            depth_mm=Decimal("3.500"),
            net_cost_usd=Decimal("1200"),
        )
        return p

    def test_compatible_stones_filters_shape_carat_mm_and_active_locks(self):
        res = self.client.get(
            "/api/v1/storefront/dyo/compatible-stones",
            {"mountingSku": self.mount.parent_sku},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        skus = {item["parentSku"] for item in data["items"]}
        self.assertIn(self.match.parent_sku, skus)
        self.assertNotIn(self.wrong_shape.parent_sku, skus)
        self.assertNotIn(self.wrong_carat.parent_sku, skus)
        self.assertNotIn(self.wrong_mm.parent_sku, skus)
        self.assertNotIn(self.locked.parent_sku, skus)
        self.assertEqual(data["filters"]["compatibleShapes"], ["ROUND", "OVAL"])


@override_settings(CACHES=LOC_MEM_CACHE, PRICING_READ_FROM_DETAILS=True, DYO_STONE_LOCK_TTL_SECONDS=900)
class DyoCartGuardAndCheckoutTests(TestCase):
    def setUp(self):
        self.snap = create_rate_snapshot(
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
            live_has_gold_try_sell=Decimal("3000"),
        )
        self.user = User.objects.create_user(
            email="dyo-checkout@test.local", password="pass-1234", full_name="Checkout Buyer"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.mount = _product(kind=MOUNTING, sku="MNT-CHK-01", stock_qty=2)
        self.mount_v = _variant(self.mount)
        MountingDetail.objects.create(
            product=self.mount,
            metal_name="Altın",
            purity_code="14K",
            metal_color="Beyaz",
            fineness=Decimal("0.5850"),
            net_weight_gr=Decimal("4.0000"),
            labor_cost_type=ProductModel.LaborCostType.FIXED,
            labor_cost_value=Decimal("20"),
            compatible_shapes=["ROUND"],
            min_carat=Decimal("0.300"),
            max_carat=Decimal("1.200"),
            setting_labor_usd=Decimal("50.00"),
            setting_type_code="6PRONG",
        )

        self.stone = _product(kind=LOOSE_STONE, sku="STN-CHK-01", stock_qty=1)
        self.stone_v = _variant(self.stone)
        LooseStoneDetail.objects.create(
            product=self.stone,
            stone_category="Pırlanta",
            shape="ROUND",
            carat=Decimal("0.700"),
            color="G",
            clarity="VS2",
            net_cost_usd=Decimal("1000"),
        )
        _seed_warehouse_stock(self.mount_v, qty=2)
        _seed_warehouse_stock(self.stone_v, qty=1)

    def _create_bundle(self):
        res = self.client.post(
            "/api/v1/storefront/dyo/bundles",
            {"mountingSku": self.mount.parent_sku, "stoneSku": self.stone.parent_sku, "addToCart": True},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()["data"]

    def test_cart_line_cannot_delete_or_qty_change_alone(self):
        bundle_data = self._create_bundle()
        bundle_id = bundle_data["id"]
        items = list(B2cCartItem.objects.filter(user=self.user, bundle_id=bundle_id))
        self.assertEqual(len(items), 2)
        line = items[0]

        patch = self.client.patch(
            f"/api/v1/storefront/cart/items/{line.id}",
            {"qty": 2},
            format="json",
        )
        self.assertEqual(patch.status_code, 409)
        self.assertEqual(patch.json()["code"], "BUNDLE_LINE_IMMUTABLE")

        delete = self.client.delete(f"/api/v1/storefront/cart/items/{line.id}")
        self.assertEqual(delete.status_code, 409)
        self.assertEqual(delete.json()["code"], "BUNDLE_LINE_IMMUTABLE")
        self.assertEqual(B2cCartItem.objects.filter(bundle_id=bundle_id).count(), 2)

        # Bundle-level delete releases both lines + soft-lock
        gone = self.client.delete(f"/api/v1/storefront/dyo/bundles/{bundle_id}")
        self.assertEqual(gone.status_code, 200)
        self.assertEqual(B2cCartItem.objects.filter(bundle_id=bundle_id).count(), 0)
        lock = StoneSoftLock.objects.filter(stone_product=self.stone).order_by("-created_at").first()
        self.assertIsNotNone(lock)
        self.assertEqual(lock.status, StoneSoftLock.Status.RELEASED)
        bundle = CustomBundle.objects.get(id=bundle_id)
        self.assertEqual(bundle.status, CustomBundle.Status.CANCELLED)

    def test_calculate_dyo_bundle_channels_and_checkout_consumes_lock(self):
        pricing = calculate_dyo_bundle(mounting=self.mount, stone=self.stone)
        # metal: 4 * 0.585 * 3000 = 7020
        # labor: 20 * 34 = 680
        # stone: 1000 * 34 = 34000
        # setting: 50 * 34 = 1700
        expected_base = Decimal("7020") + Decimal("680") + Decimal("34000") + Decimal("1700")
        self.assertAlmostEqual(Decimal(str(pricing["baseCostTry"])), expected_base, places=2)
        self.assertEqual(pricing["settingLaborUsd"], 50.0)
        self.assertIn("B2B", pricing["channels"])
        self.assertIn("B2C_API", pricing["channels"])
        b2b = Decimal(str(pricing["channels"]["B2B"]["finalPriceTry"]))
        b2c = Decimal(str(pricing["channels"]["B2C_API"]["finalPriceTry"]))
        self.assertGreater(b2b, expected_base)  # +10% default
        self.assertGreater(b2c, b2b)  # B2C margin + service

        bundle_data = self._create_bundle()
        PriceLock.objects.create(
            user=self.user,
            rate_snapshot=self.snap,
            expires_at=timezone.now() + timedelta(minutes=15),
            is_active=True,
        )
        # Align cart lines to active lock snapshot (bundle create already used current snap)
        B2cCartItem.objects.filter(user=self.user).update(
            rate_snapshot=self.snap, snapshot_code=self.snap.snapshot_code
        )

        order = submit_b2c_order(
            user=self.user,
            payload={
                "customerName": "Test Buyer",
                "customerPhone": "+905551112233",
                "customerEmail": "buyer@test.local",
                "shippingCity": "İstanbul",
                "shippingAddress": "Kapalıçarşı No:1",
                "paymentMethod": "CREDIT_CARD",
                "acceptedCustomPolicy": True,
            },
        )
        self.assertIsNotNone(order.order_no)
        self.assertEqual(order.items.count(), 2)
        lock = StoneSoftLock.objects.filter(stone_product=self.stone).order_by("-created_at").first()
        self.assertEqual(lock.status, StoneSoftLock.Status.CONSUMED)
        bundle = CustomBundle.objects.get(id=bundle_data["id"])
        self.assertEqual(bundle.status, CustomBundle.Status.CHECKED_OUT)

        mount_ws = WarehouseStock.objects.get(variant=self.mount_v)
        stone_ws = WarehouseStock.objects.get(variant=self.stone_v)
        self.assertEqual(mount_ws.reserved_qty, 1)
        self.assertEqual(stone_ws.reserved_qty, 1)

    def test_celery_release_expired_stone_locks(self):
        StoneSoftLock.objects.create(
            stone_product=self.stone,
            user=self.user,
            bundle=None,
            expires_at=timezone.now() - timedelta(seconds=5),
            status=StoneSoftLock.Status.ACTIVE,
        )
        result = release_expired_stone_locks_task()
        self.assertGreaterEqual(result["released"], 1)
        lock = StoneSoftLock.objects.filter(stone_product=self.stone, user=self.user).latest("created_at")
        self.assertEqual(lock.status, StoneSoftLock.Status.RELEASED)
        self.assertEqual(release_expired_stone_locks(), 0)


@override_settings(CACHES=LOC_MEM_CACHE, PRICING_READ_FROM_DETAILS=True, DYO_STONE_LOCK_TTL_SECONDS=900)
class DyoSoftLockRaceTests(TransactionTestCase):
    def setUp(self):
        create_rate_snapshot(
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
            live_has_gold_try_sell=Decimal("3000"),
        )
        self.user_a = User.objects.create_user(
            email="race-a@test.local", password="pass-1234", full_name="Race A"
        )
        self.user_b = User.objects.create_user(
            email="race-b@test.local", password="pass-1234", full_name="Race B"
        )
        self.mount = _product(kind=MOUNTING, sku="MNT-RACE-01")
        _variant(self.mount)
        MountingDetail.objects.create(
            product=self.mount,
            metal_name="Altın",
            purity_code="14K",
            metal_color="Beyaz",
            fineness=Decimal("0.5850"),
            net_weight_gr=Decimal("3.0000"),
            labor_cost_type=ProductModel.LaborCostType.FIXED,
            labor_cost_value=Decimal("10"),
            compatible_shapes=["ROUND"],
            min_carat=Decimal("0.300"),
            max_carat=Decimal("1.000"),
            setting_labor_usd=Decimal("40"),
        )
        self.stone = _product(kind=LOOSE_STONE, sku="STN-RACE-01")
        _variant(self.stone)
        LooseStoneDetail.objects.create(
            product=self.stone,
            stone_category="Pırlanta",
            shape="ROUND",
            carat=Decimal("0.550"),
            color="F",
            clarity="VS1",
            net_cost_usd=Decimal("900"),
        )

    def _post_bundle(self, user: User) -> tuple[int, dict]:
        client = APIClient()
        client.force_authenticate(user=user)
        res = client.post(
            "/api/v1/storefront/dyo/bundles",
            {
                "mountingSku": self.mount.parent_sku,
                "stoneSku": self.stone.parent_sku,
                "addToCart": True,
            },
            format="json",
        )
        body = res.json() if res.content else {}
        return res.status_code, body

    def test_second_user_gets_stone_locked_409(self):
        code_a, body_a = self._post_bundle(self.user_a)
        self.assertEqual(code_a, 201, body_a)
        code_b, body_b = self._post_bundle(self.user_b)
        self.assertEqual(code_b, 409, body_b)
        self.assertEqual(body_b.get("code"), "STONE_LOCKED")
        self.assertEqual(
            StoneSoftLock.objects.filter(
                stone_product=self.stone, status=StoneSoftLock.Status.ACTIVE
            ).count(),
            1,
        )

    @skipIf(connection.vendor == "sqlite", "SQLite select_for_update is a no-op; concurrent race needs Postgres")
    def test_concurrent_posts_one_201_one_409(self):
        results: list[tuple[int, dict]] = []

        def run(user):
            return self._post_bundle(user)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, self.user_a), pool.submit(run, self.user_b)]
            for fut in as_completed(futures):
                results.append(fut.result())

        codes = sorted(code for code, _ in results)
        self.assertEqual(codes, [201, 409])
        locked_bodies = [body for code, body in results if code == 409]
        self.assertEqual(locked_bodies[0].get("code"), "STONE_LOCKED")

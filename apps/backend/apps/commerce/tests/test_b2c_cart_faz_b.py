"""Faz B — B2cCart header, events, ingest."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.api_keys.services import create_api_key
from apps.commerce.cart_sync import (
    get_or_create_active_cart,
    mark_cart_converted,
    sync_user_cart,
    upsert_cart_from_external,
)
from apps.commerce.models import B2cCart, B2cCartItem, B2cOrder, CartEvent, CartRecoverySession
from apps.commerce.recovery import process_session, touch_b2c_cart
from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent
from apps.customers.services import get_or_update_customer_for_user
from apps.market.services import create_rate_snapshot
from apps.organizations.models import Organization, OrganizationMembership


def _seed_rates():
    return create_rate_snapshot(
        fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        live_has_gold_try_sell=Decimal("3000"),
    )


def _line(user, *, price="1500.00"):
    snap = _seed_rates()
    return B2cCartItem.objects.create(
        user=user,
        sku="SE009-BYZ-14",
        parent_sku="SE009",
        title="Yüzük",
        category="Yüzük",
        metal_color="Beyaz",
        purity_code="14K",
        size=14,
        qty=1,
        unit_list_price_try=Decimal(price),
        unit_final_price_try=Decimal(price),
        rate_snapshot=snap,
        snapshot_code=snap.snapshot_code,
        stock_status="Stokta",
    )


class B2cCartHeaderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cart-b@test.local", password="pass-1234", full_name="Cart User"
        )
        customer = get_or_update_customer_for_user(
            user=self.user, full_name=self.user.full_name, email=self.user.email
        )
        append_consent(
            customer=customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.OPS,
        )

    def test_sync_creates_header_and_links_items(self):
        item = _line(self.user)
        cart = sync_user_cart(
            user=self.user,
            event_type=CartEvent.EventType.PRODUCT_ADDED,
            payload={"sku": item.sku},
        )
        self.assertIsNotNone(cart)
        self.assertEqual(cart.status, B2cCart.Status.ACTIVE)
        item.refresh_from_db()
        self.assertEqual(item.cart_id, cart.id)
        self.assertEqual(cart.line_count, 1)
        self.assertTrue(
            CartEvent.objects.filter(
                cart=cart, event_type=CartEvent.EventType.PRODUCT_ADDED
            ).exists()
        )

    def test_touch_syncs_header(self):
        _line(self.user)
        touch_b2c_cart(user=self.user)
        self.assertTrue(
            B2cCart.objects.filter(user=self.user, status=B2cCart.Status.ACTIVE).exists()
        )

    def test_abandon_on_t1(self):
        _line(self.user)
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(hours=2)
        session.save(update_fields=["cart_updated_at"])
        process_session(session)
        cart = B2cCart.objects.get(user=self.user)
        self.assertEqual(cart.status, B2cCart.Status.ABANDONED)
        self.assertTrue(
            CartEvent.objects.filter(
                cart=cart, event_type=CartEvent.EventType.CART_ABANDONED
            ).exists()
        )

    def test_convert_marks_order(self):
        _line(self.user)
        cart = sync_user_cart(user=self.user)
        snap = _seed_rates()
        customer = get_or_update_customer_for_user(
            user=self.user, full_name=self.user.full_name, email=self.user.email
        )
        order = B2cOrder.objects.create(
            order_no="TG-B2C-CART-1",
            customer=customer,
            created_by=self.user,
            rate_snapshot=snap,
            gold_rate_try_per_gram=snap.live_has_gold_try_sell,
            payment_method="BANK_TRANSFER",
            shipping_full_name=self.user.full_name,
            shipping_phone="555",
            shipping_email=self.user.email,
            shipping_city="İstanbul",
            shipping_address="Adr",
            subtotal_list_try=Decimal("1500.00"),
            grand_total_try=Decimal("1500.00"),
        )
        mark_cart_converted(user=self.user, order=order)
        cart.refresh_from_db()
        self.assertEqual(cart.status, B2cCart.Status.CONVERTED)
        self.assertEqual(cart.converted_order_id, order.id)


class CartIngestTests(TestCase):
    def setUp(self):
        self.ops = User.objects.create_user(
            email="ops-cart@test.local", password="pass-1234", full_name="Ops", is_staff=True
        )
        self.org = Organization.objects.create(code="CART-ORG", name="Cart Org")
        OrganizationMembership.objects.create(
            user=self.ops,
            organization=None,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            is_active=True,
        )
        _, self.raw_key = create_api_key(
            organization=self.org,
            name="cart-integ",
            created_by=self.ops,
            scopes=["integrations:b2c:write"],
        )
        self.client = APIClient()

    def test_upsert_and_duplicate(self):
        body = {
            "eventId": "cart-evt-1",
            "eventType": "cart.upsert",
            "idempotencyKey": "cart-idem-1",
            "payload": {
                "externalId": "ext-cart-99",
                "email": "guest-cart@test.local",
                "totalTry": "2500.00",
                "lineCount": 2,
                "status": "ACTIVE",
            },
        }
        r1 = self.client.post(
            "/api/v1/integrations/b2c/carts/",
            body,
            format="json",
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertIn(r1.status_code, (200, 201, 202))
        r2 = self.client.post(
            "/api/v1/integrations/b2c/carts/",
            body,
            format="json",
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.data["data"]["duplicate"])
        self.assertEqual(B2cCart.objects.filter(external_id="ext-cart-99").count(), 1)

    def test_external_upsert_helper(self):
        result = upsert_cart_from_external(
            {
                "externalId": "ext-cart-helper",
                "email": "h@test.local",
                "totalTry": "100.00",
            }
        )
        self.assertTrue(result["created"])
        self.assertEqual(B2cCart.objects.get(external_id="ext-cart-helper").total_try, Decimal("100.00"))


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class OpsCartApiTests(TestCase):
    def setUp(self):
        self.ops = User.objects.create_user(
            email="ops-list@test.local", password="pass-1234", full_name="Ops"
        )
        OrganizationMembership.objects.create(
            user=self.ops,
            organization=None,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_login(self.ops)
        self.user = User.objects.create_user(
            email="buyer@test.local", password="pass-1234", full_name="Buyer"
        )
        _line(self.user)
        sync_user_cart(user=self.user)

    def test_list_carts(self):
        res = self.client.get("/api/v1/ops/carts")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data["data"]), 1)

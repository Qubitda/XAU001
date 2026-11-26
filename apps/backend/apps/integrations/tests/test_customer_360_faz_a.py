"""Faz A — Customer 360 & Consent Management acceptance tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.api_keys.services import create_api_key
from apps.commerce.models import (
    B2cCartItem,
    B2cOrder,
    CartRecoveryAttempt,
    CartRecoverySession,
)
from apps.commerce.recovery import process_session, touch_b2c_cart
from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent, has_active_consent
from apps.contracts.models import LegalDocument
from apps.contracts.services import record_order_acceptances
from apps.customers.models import Customer
from apps.customers.services import get_or_update_customer_for_user, upsert_customer_from_external
from apps.integrations.models import IntegrationEvent
from apps.market.services import create_rate_snapshot
from apps.organizations.models import Organization, OrganizationMembership


def _seed_rates():
    return create_rate_snapshot(
        fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        live_has_gold_try_sell=Decimal("3000"),
    )


class CustomerIdentityTests(TestCase):
    def test_get_or_update_does_not_duplicate(self):
        user = User.objects.create_user(
            email="dup@test.local", password="pass-1234", full_name="Ali Veli"
        )
        c1 = get_or_update_customer_for_user(
            user=user, full_name="Ali Veli", email=user.email, phone="555"
        )
        c2 = get_or_update_customer_for_user(
            user=user, full_name="Ali Veli Updated", email=user.email, phone="556"
        )
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(Customer.objects.filter(user=user).count(), 1)
        c2.refresh_from_db()
        self.assertEqual(c2.full_name, "Ali Veli Updated")
        self.assertEqual(c2.phone, "556")

    def test_external_id_upsert(self):
        c, created = upsert_customer_from_external(
            external_id="b2c-ext-1",
            full_name="Ayşe Yılmaz",
            email="ayse@test.local",
        )
        self.assertTrue(created)
        c2, created2 = upsert_customer_from_external(
            external_id="b2c-ext-1",
            full_name="Ayşe Yılmaz 2",
            email="ayse@test.local",
        )
        self.assertFalse(created2)
        self.assertEqual(c.id, c2.id)
        self.assertEqual(Customer.objects.filter(external_id="b2c-ext-1").count(), 1)


class ConsentContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="consent@test.local", password="pass-1234", full_name="Consent User"
        )
        self.customer = get_or_update_customer_for_user(
            user=self.user, full_name=self.user.full_name, email=self.user.email
        )
        LegalDocument.objects.get_or_create(
            code=LegalDocument.Code.DISTANCE_SALES,
            version="1.0",
            defaults={
                "title": "Mesafeli Satış",
                "body_html": "<p>v1</p>",
                "is_published": True,
                "audience": "ALL",
                "effective_from": timezone.now(),
            },
        )
        LegalDocument.objects.get_or_create(
            code=LegalDocument.Code.PRE_INFO,
            version="1.0",
            defaults={
                "title": "Ön Bilgi",
                "body_html": "<p>v1</p>",
                "is_published": True,
                "audience": "ALL",
                "effective_from": timezone.now(),
            },
        )

    def test_consent_append_and_withdraw(self):
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.REGISTER,
        )
        self.assertTrue(
            has_active_consent(
                customer=self.customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel=ConsentChannel.EMAIL,
            )
        )
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.WITHDRAWN,
            source=ConsentSource.OPS,
        )
        self.assertFalse(
            has_active_consent(
                customer=self.customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel=ConsentChannel.EMAIL,
            )
        )

    def test_contract_acceptance_keeps_old_hash_on_version_change(self):
        snap = _seed_rates()
        order = B2cOrder.objects.create(
            order_no="TG-B2C-TEST-001",
            customer=self.customer,
            created_by=self.user,
            rate_snapshot=snap,
            gold_rate_try_per_gram=snap.live_has_gold_try_sell,
            payment_method="BANK_TRANSFER",
            shipping_full_name=self.user.full_name,
            shipping_phone="555",
            shipping_email=self.user.email,
            shipping_city="İstanbul",
            shipping_address="Test",
            subtotal_list_try=Decimal("100.00"),
            grand_total_try=Decimal("100.00"),
        )
        rows = record_order_acceptances(customer=self.customer, order=order)
        self.assertGreaterEqual(len(rows), 1)
        old_hash = rows[0].content_hash
        old_version = rows[0].document_version

        LegalDocument.objects.filter(code=LegalDocument.Code.DISTANCE_SALES, version="1.0").update(
            is_published=False
        )
        LegalDocument.objects.create(
            code=LegalDocument.Code.DISTANCE_SALES,
            version="2.0",
            title="Mesafeli Satış v2",
            body_html="<p>v2 changed</p>",
            is_published=True,
            audience="ALL",
            effective_from=timezone.now(),
        )
        rows[0].refresh_from_db()
        self.assertEqual(rows[0].content_hash, old_hash)
        self.assertEqual(rows[0].document_version, old_version)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CART_RECOVERY_B2C_T1_SECONDS=0,
    CART_RECOVERY_B2C_T2_SECONDS=0,
    CART_RECOVERY_B2C_T3_SECONDS=0,
)
class RecoveryConsentGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="gate@test.local", password="pass-1234", full_name="Gate User"
        )
        self.customer = get_or_update_customer_for_user(
            user=self.user, full_name=self.user.full_name, email=self.user.email
        )
        snap = _seed_rates()
        B2cCartItem.objects.create(
            user=self.user,
            sku="SE009-BYZ-14",
            parent_sku="SE009",
            title="Yüzük",
            category="Yüzük",
            metal_color="Beyaz",
            purity_code="14K",
            size=14,
            qty=1,
            unit_list_price_try=Decimal("1500.00"),
            unit_final_price_try=Decimal("1500.00"),
            rate_snapshot=snap,
            snapshot_code=snap.snapshot_code,
            stock_status="Stokta",
        )

    def test_no_consent_skips_email(self):
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(hours=2)
        session.save(update_fields=["cart_updated_at"])
        process_session(session)
        attempt = CartRecoveryAttempt.objects.get(
            session=session, stage="T1", channel=CartRecoveryAttempt.Channel.EMAIL
        )
        self.assertEqual(attempt.status, CartRecoveryAttempt.Status.SKIPPED)
        self.assertEqual(attempt.skip_reason, "NO_CONSENT")

    def test_withdraw_suppresses_active_session(self):
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.REGISTER,
        )
        session = touch_b2c_cart(user=self.user)
        self.assertEqual(session.status, CartRecoverySession.Status.ACTIVE)
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.WITHDRAWN,
            source=ConsentSource.OPS,
        )
        session.refresh_from_db()
        self.assertEqual(session.status, CartRecoverySession.Status.SUPPRESSED)
        self.assertEqual(
            session.suppress_reason, CartRecoverySession.SuppressReason.CONSENT_WITHDRAWN
        )


class IntegrationInboxTests(TestCase):
    def setUp(self):
        self.ops = User.objects.create_user(
            email="ops-integ@test.local", password="pass-1234", full_name="Ops", is_staff=True
        )
        self.org = Organization.objects.create(
            code="INTEG-ORG",
            name="Integration Org",
            tax_number="9988776655",
        )
        OrganizationMembership.objects.create(
            user=self.ops,
            organization=None,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            is_active=True,
        )
        self.api_key, self.raw_key = create_api_key(
            organization=self.org,
            name="b2c-integ",
            created_by=self.ops,
            scopes=["integrations:b2c:write"],
        )
        self.client = APIClient()

    def _post(self, path, payload, *, key=None):
        return self.client.post(
            path,
            data=payload,
            format="json",
            HTTP_X_API_KEY=key or self.raw_key,
        )

    def test_auth_required(self):
        res = self.client.post(
            "/api/v1/integrations/b2c/events/",
            {"eventType": "customer.upsert", "payload": {"externalId": "x", "fullName": "Y"}},
            format="json",
        )
        self.assertIn(res.status_code, (401, 403))

    def test_customer_upsert_and_duplicate_idempotent(self):
        body = {
            "eventId": "evt-cust-1",
            "eventType": "customer.upsert",
            "idempotencyKey": "idem-cust-1",
            "payload": {
                "externalId": "ext-100",
                "fullName": "Zeynep Kaya",
                "email": "zeynep@test.local",
            },
        }
        r1 = self._post("/api/v1/integrations/b2c/events/", body)
        self.assertIn(r1.status_code, (200, 201, 202))
        r2 = self._post("/api/v1/integrations/b2c/events/", body)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.data["data"]["duplicate"])
        self.assertEqual(IntegrationEvent.objects.filter(event_id="evt-cust-1").count(), 1)
        self.assertEqual(Customer.objects.filter(external_id="ext-100").count(), 1)

    def test_consent_shortcut(self):
        upsert_customer_from_external(
            external_id="ext-consent", full_name="C User", email="cuser@test.local"
        )
        r = self._post(
            "/api/v1/integrations/b2c/consents/",
            {
                "idempotencyKey": "idem-consent-1",
                "externalId": "ext-consent",
                "purpose": "COMMERCIAL_EMAIL",
                "channel": "EMAIL",
                "status": "GRANTED",
            },
        )
        self.assertIn(r.status_code, (200, 201, 202))
        customer = Customer.objects.get(external_id="ext-consent")
        self.assertTrue(
            has_active_consent(
                customer=customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel=ConsentChannel.EMAIL,
            )
        )


class OpsPermissionTests(TestCase):
    def setUp(self):
        self.b2c = User.objects.create_user(
            email="b2c-noops@test.local", password="pass-1234", full_name="B2C"
        )
        OrganizationMembership.objects.create(
            user=self.b2c,
            organization=None,
            role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_login(self.b2c)

    def test_unauthorized_ops_customer_list(self):
        res = self.client.get("/api/v1/ops/customers")
        self.assertEqual(res.status_code, 403)


class StorefrontAddressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="addr@test.local", password="pass-1234", full_name="Addr User"
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=None,
            role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_address_crud(self):
        r = self.client.post(
            "/api/v1/storefront/addresses",
            {
                "title": "Ev",
                "line": "Cadde 1",
                "city": "İstanbul",
                "addressType": "SHIPPING",
                "isDefault": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        addr_id = r.data["data"]["id"]
        r2 = self.client.get("/api/v1/storefront/addresses")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(len(r2.data["data"]), 1)
        r3 = self.client.delete(f"/api/v1/storefront/addresses/{addr_id}")
        self.assertEqual(r3.status_code, 200)
        r4 = self.client.get("/api/v1/storefront/addresses")
        self.assertEqual(len(r4.data["data"]), 0)

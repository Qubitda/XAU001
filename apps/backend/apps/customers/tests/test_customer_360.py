"""OPS Customer 360 aggregation regression tests."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.commerce.models import B2cOrder
from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent
from apps.contracts.models import ContractAcceptance, LegalDocument
from apps.customers.models import Customer
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class Customer360ApiTests(TestCase):
    def setUp(self) -> None:
        self.ops_user = User.objects.create_user(
            email="ops-c360@tara.local",
            password="pw",
            is_staff=True,
            is_superuser=True,
        )
        platform_org = Organization.objects.create(
            code="TARA-OPS-360",
            name="Tara OPS",
        )
        OrganizationMembership.objects.create(
            user=self.ops_user,
            organization=platform_org,
            role_key="SUPER_ADMIN",
        )
        self.b2c_user = User.objects.create_user(
            email="b2c-c360@tara.local",
            password="pw",
            full_name="Elif Yılmaz",
        )
        self.customer = Customer.objects.create(
            user=self.b2c_user,
            email="b2c-c360@tara.local",
            full_name="Elif Yılmaz",
        )
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.REGISTER,
        )
        doc = LegalDocument.objects.create(
            code=LegalDocument.Code.KVKK,
            version="v1",
            title="KVKK Aydınlatma",
            is_published=True,
        )
        snap = get_current_rate_snapshot()
        order = B2cOrder.objects.create(
            order_no="TG-C360-001",
            customer=self.customer,
            created_by=self.b2c_user,
            rate_snapshot=snap,
            gold_rate_try_per_gram=snap.live_has_gold_try_sell,
            payment_method="BANK_TRANSFER",
            subtotal_list_try=Decimal("10000.00"),
            grand_total_try=Decimal("10000.00"),
            shipping_full_name="Elif Yılmaz",
            shipping_phone="05551112233",
            shipping_email="b2c-c360@tara.local",
            shipping_city="İstanbul",
            shipping_address="Test Adres",
        )
        ContractAcceptance.objects.create(
            customer=self.customer,
            order=order,
            document=doc,
            document_code=doc.code,
            document_version=doc.version,
            accepted_at=timezone.now(),
        )
        self.client = APIClient()

    def test_ops_customer_360_merges_orders_consents_and_contracts(self) -> None:
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.get(f"/api/v1/ops/customers/{self.customer.id}/360")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["email"], "b2c-c360@tara.local")
        self.assertTrue(data["consents"]["commercialEmail"])
        self.assertEqual(data["consentLogCount"], 1)
        self.assertEqual(data["contractAcceptanceCount"], 1)

    def test_non_ops_user_cannot_access_customer_360(self) -> None:
        self.client.force_authenticate(user=self.b2c_user)
        resp = self.client.get(f"/api/v1/ops/customers/{self.customer.id}/360")
        self.assertEqual(resp.status_code, 403)

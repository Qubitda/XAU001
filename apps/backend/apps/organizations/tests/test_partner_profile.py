from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationAddress, OrganizationMembership


class BusinessPartnerProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ops-bp@test.local",
            password="test-pass-1234",
            is_staff=True,
            full_name="Ops BP",
        )
        self.org = Organization.objects.create(
            code="BP01",
            name="Bayi Partner",
            org_type=Organization.OrgType.DEALER,
            partner_roles=["BUYER"],
            city="İstanbul",
        )
        self.membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.SUPER_ADMIN,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        session = self.client.session
        session["active_membership_id"] = str(self.membership.id)
        session.save()

    def test_create_org_with_roles(self):
        response = self.client.post(
            "/api/v1/ops/organizations",
            {
                "code": "SUP1",
                "name": "Tedarikçi A",
                "orgType": "SUPPLIER",
                "partnerRoles": ["SUPPLIER", "BUYER"],
                "city": "Ankara",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertIn("SUPPLIER", data["partnerRoles"])
        self.assertTrue(data["isSupplier"])
        self.assertTrue(data["isBuyer"])

    def test_address_crud_soft_delete(self):
        response = self.client.post(
            f"/api/v1/ops/organizations/{self.org.id}/addresses",
            {
                "addressType": "BILLING",
                "title": "Fatura",
                "line": "Örnek Cad. No:1",
                "city": "İstanbul",
                "isDefault": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        addr_id = response.json()["data"]["id"]

        delete = self.client.delete(f"/api/v1/ops/organizations/{self.org.id}/addresses/{addr_id}")
        self.assertEqual(delete.status_code, 200)
        addr = OrganizationAddress.objects.get(id=addr_id)
        self.assertFalse(addr.is_active)

    def test_dossier_includes_finance_ssot(self):
        self.org.credit_limit_usd = 10000
        self.org.used_credit_usd = 2500
        self.org.save(update_fields=["credit_limit_usd", "used_credit_usd", "updated_at"])
        response = self.client.get(f"/api/v1/ops/organizations/{self.org.id}/dossier")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["overview"]["creditLimitUsd"], "10000.00")
        self.assertEqual(data["overview"]["cariBalanceUsd"], "2500.00")
        self.assertEqual(data["overview"]["availableCreditUsd"], "7500.00")
        self.assertIn("addresses", data)
        self.assertIn("activity", data)

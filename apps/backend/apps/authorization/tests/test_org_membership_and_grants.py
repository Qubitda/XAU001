from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.authorization.permissions import resolve_membership_permissions
from apps.common.security import can_grant, sanitize_permissions
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class OrgMembershipAndGrantTests(TestCase):
    def setUp(self) -> None:
        self.org_a = Organization.objects.create(
            code="ORG-A",
            name="Bayi A",
            org_type=Organization.OrgType.DEALER,
        )
        self.org_b = Organization.objects.create(
            code="ORG-B",
            name="Bayi B",
            org_type=Organization.OrgType.DEALER,
        )
        self.sup_org = Organization.objects.create(
            code="SUP-A",
            name="Tedarikçi A",
            org_type=Organization.OrgType.SUPPLIER,
        )

        self.org_admin_a = User.objects.create_user(email="admina@tara.local", password="p", full_name="Admin A")
        self.org_admin_a_mem = OrganizationMembership.objects.create(
            user=self.org_admin_a,
            organization=self.org_a,
            role_key=OrganizationMembership.RoleKey.ORG_ADMIN,
        )

        self.buyer_a = User.objects.create_user(email="buyera@tara.local", password="p", full_name="Buyer A")
        self.buyer_a_mem = OrganizationMembership.objects.create(
            user=self.buyer_a,
            organization=self.org_a,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
        )

        self.buyer_b = User.objects.create_user(email="buyerb@tara.local", password="p", full_name="Buyer B")
        self.buyer_b_mem = OrganizationMembership.objects.create(
            user=self.buyer_b,
            organization=self.org_b,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
        )

        self.sup_admin = User.objects.create_user(email="supadmin@tara.local", password="p", full_name="Sup Admin")
        self.sup_admin_mem = OrganizationMembership.objects.create(
            user=self.sup_admin,
            organization=self.sup_org,
            role_key=OrganizationMembership.RoleKey.SUPPLIER_ADMIN,
        )

        self.extra_user = User.objects.create_user(email="extra@tara.local", password="p", full_name="Extra")
        self.client = APIClient()

    def test_can_grant_blocks_unowned_grant_and_deny_but_allows_super_admin(self) -> None:
        admin_perms = resolve_membership_permissions(self.org_admin_a_mem)
        self.assertFalse(can_grant(admin_perms, ["finance:manage"]))
        self.assertFalse(can_grant(admin_perms, ["catalog:write"]))
        self.assertTrue(can_grant(admin_perms, ["b2b:order"]))
        self.assertTrue(can_grant([], ["finance:manage"], is_super_admin=True))

    def test_supplier_identity_view_blocked_for_customer_and_supplier_roles(self) -> None:
        self.assertEqual(
            sanitize_permissions(["catalog:read", "supplier_identity:view"], role_key="B2B_BUYER"),
            ["catalog:read"],
        )
        self.assertEqual(
            sanitize_permissions(["supplier_products:read", "supplier_identity:view"], role_key="SUPPLIER_ADMIN"),
            ["supplier_products:read"],
        )
        self.buyer_a_mem.custom_permissions = ["supplier_identity:view"]
        self.buyer_a_mem.save(update_fields=["custom_permissions"])
        self.assertNotIn("supplier_identity:view", resolve_membership_permissions(self.buyer_a_mem))

    def test_org_admin_cannot_access_other_organization_member(self) -> None:
        self.client.force_authenticate(user=self.org_admin_a)
        res_get = self.client.get(f"/api/v1/org/memberships/{self.buyer_b_mem.id}")
        self.assertEqual(res_get.status_code, 404)
        res_patch = self.client.patch(
            f"/api/v1/org/memberships/{self.buyer_b_mem.id}",
            {"jobTitle": "Hacked"},
            format="json",
        )
        self.assertEqual(res_patch.status_code, 404)

    def test_org_admin_cannot_change_own_permissions_or_role(self) -> None:
        self.client.force_authenticate(user=self.org_admin_a)
        res_patch = self.client.patch(
            f"/api/v1/org/memberships/{self.org_admin_a_mem.id}",
            {"deniedPermissions": ["b2b:order"]},
            format="json",
        )
        self.assertEqual(res_patch.status_code, 403)
        res_del = self.client.delete(f"/api/v1/org/memberships/{self.org_admin_a_mem.id}")
        self.assertEqual(res_del.status_code, 403)

    def test_org_admin_cannot_assign_ops_or_supplier_roles_or_unowned_permissions(self) -> None:
        self.client.force_authenticate(user=self.org_admin_a)
        for bad_role in ("OPS", "SUPER_ADMIN", "SUPPLIER_ADMIN"):
            res = self.client.post(
                "/api/v1/org/memberships",
                {"userId": str(self.extra_user.id), "roleKey": bad_role},
                format="json",
            )
            self.assertEqual(res.status_code, 403)

        # Cannot grant or deny unowned permission (e.g. finance:manage)
        res_grant = self.client.patch(
            f"/api/v1/org/memberships/{self.buyer_a_mem.id}",
            {"customPermissions": ["finance:manage"]},
            format="json",
        )
        self.assertEqual(res_grant.status_code, 403)
        res_deny = self.client.patch(
            f"/api/v1/org/memberships/{self.buyer_a_mem.id}",
            {"deniedPermissions": ["finance:manage"]},
            format="json",
        )
        self.assertEqual(res_deny.status_code, 403)

        # Valid B2B_BUYER creation + denied_permissions within granter's scope succeeds
        ok_create = self.client.post(
            "/api/v1/org/memberships",
            {
                "userId": str(self.extra_user.id),
                "roleKey": "B2B_BUYER",
                "deniedPermissions": ["b2b:order"],
            },
            format="json",
        )
        self.assertEqual(ok_create.status_code, 201)

    def test_supplier_admin_can_only_assign_supplier_roles_in_own_org(self) -> None:
        self.client.force_authenticate(user=self.sup_admin)
        bad_role = self.client.post(
            "/api/v1/org/memberships",
            {"userId": str(self.extra_user.id), "roleKey": "B2B_BUYER"},
            format="json",
        )
        self.assertEqual(bad_role.status_code, 403)

        ok_sup = self.client.post(
            "/api/v1/org/memberships",
            {"userId": str(self.extra_user.id), "roleKey": "SUPPLIER_USER"},
            format="json",
        )
        self.assertEqual(ok_sup.status_code, 201)

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.api_keys.models import ApiKey
from apps.authorization.constants import (
    ALL_PERMISSIONS,
    B2B_ROLES,
    OPS_ROLES,
    ROLE_PERMISSIONS,
    SUPPLIER_ROLES,
)
from apps.authorization.permissions import (
    HasPortalPermission,
    IsOpsUser,
    IsSuperAdminUser,
    resolve_membership_permissions,
)
from apps.common.security import can_grant, sanitize_permissions
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class _UnconfiguredPortalView(APIView):
    permission_classes = [HasPortalPermission]

    def get(self, request):
        return Response({"ok": True})


class _AllowAnyAuthenticatedView(APIView):
    permission_classes = [HasPortalPermission]
    allow_any_authenticated = True

    def get(self, request):
        return Response({"ok": True})


class _MethodMapPortalView(APIView):
    permission_classes = [HasPortalPermission]
    required_permissions_by_method = {"GET": "catalog:read"}

    def get(self, request):
        return Response({"ok": True})

    def post(self, request):
        return Response({"ok": True})


class _OpsView(APIView):
    permission_classes = [IsOpsUser]

    def get(self, request):
        return Response({"ok": True})


class _SuperAdminView(APIView):
    permission_classes = [IsSuperAdminUser]

    def get(self, request):
        return Response({"ok": True})


class _ScopedApiKeyPortalView(APIView):
    permission_classes = [HasPortalPermission]
    required_permission = "catalog:read"
    api_key_scopes = ("catalog:read",)

    def get(self, request):
        return Response({"ok": True})


class AuthorizationModuleTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.org = Organization.objects.create(code="TEST-ORG", name="Test Kuyumculuk")
        self.sup_org = Organization.objects.create(code="SUP-ORG", name="Tedarikçi A.Ş.")

        self.ops_user = User.objects.create_user(email="ops@tara.local", password="p", full_name="OPS")
        self.ops_mem = OrganizationMembership.objects.create(
            user=self.ops_user, organization=self.org, role_key=OrganizationMembership.RoleKey.OPS
        )

        self.super_user = User.objects.create_user(
            email="super@tara.local", password="p", full_name="Super", is_superuser=True
        )
        self.super_mem = OrganizationMembership.objects.create(
            user=self.super_user, organization=self.org, role_key=OrganizationMembership.RoleKey.SUPER_ADMIN
        )

        self.org_admin = User.objects.create_user(email="orgadmin@tara.local", password="p", full_name="OrgAdmin")
        self.org_admin_mem = OrganizationMembership.objects.create(
            user=self.org_admin, organization=self.org, role_key=OrganizationMembership.RoleKey.ORG_ADMIN
        )

    def test_role_permission_sets_snapshot(self):
        self.assertEqual(OPS_ROLES, frozenset({"SUPER_ADMIN", "OPS"}))
        self.assertEqual(B2B_ROLES, frozenset({"ORG_ADMIN", "B2B_BUYER"}))
        self.assertEqual(SUPPLIER_ROLES, frozenset({"SUPPLIER_ADMIN", "SUPPLIER_USER"}))

        self.assertEqual(ROLE_PERMISSIONS["SUPER_ADMIN"], frozenset(ALL_PERMISSIONS))
        self.assertIn("supplier_identity:view", ROLE_PERMISSIONS["OPS"])
        self.assertIn("supplier_products:write", ROLE_PERMISSIONS["OPS"])
        self.assertIn("users:manage", ROLE_PERMISSIONS["ORG_ADMIN"])
        self.assertIn("quotes:request", ROLE_PERMISSIONS["ORG_ADMIN"])
        self.assertIn("quotes:request", ROLE_PERMISSIONS["B2B_BUYER"])
        self.assertTrue(
            {"catalog:read", "supplier_products:read", "supplier_products:write", "quotes:respond", "users:read", "users:manage", "org:switch"}.issubset(
                ROLE_PERMISSIONS["SUPPLIER_ADMIN"]
            )
        )
        self.assertEqual(
            ROLE_PERMISSIONS["SUPPLIER_USER"],
            frozenset({"supplier_products:read", "quotes:respond", "org:switch"}),
        )
        for role in ("ORG_ADMIN", "B2B_BUYER", "SUPPLIER_ADMIN", "SUPPLIER_USER", "B2C_CUSTOMER"):
            self.assertNotIn("supplier_identity:view", ROLE_PERMISSIONS[role])

    def test_denied_and_custom_permissions_and_ceiling(self):
        m = OrganizationMembership.objects.create(
            user=User.objects.create_user(email="buyer@tara.local", password="p", full_name="Buyer"),
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            custom_permissions=["quotes:respond", "supplier_identity:view", "finance:manage"],
            denied_permissions=["b2b:order"],
        )
        perms = resolve_membership_permissions(m)
        # Role perm b2b:order was denied
        self.assertNotIn("b2b:order", perms)
        # Non-ops custom perm quotes:respond was added
        self.assertIn("quotes:respond", perms)
        # Ops-only perms blocked even if injected into custom_permissions
        self.assertNotIn("supplier_identity:view", perms)
        self.assertNotIn("finance:manage", perms)

    def test_fail_closed_portal_permission_and_method_fallback(self):
        perm = HasPortalPermission()

        # Unconfigured view denies authenticated user (fail-closed)
        req = self.factory.get("/dummy")
        req.session = {}
        force_authenticate(req, user=self.ops_user)
        self.assertFalse(perm.has_permission(Request(req), _UnconfiguredPortalView()))

        # Explicit allow_any_authenticated=True allows authenticated user
        self.assertTrue(perm.has_permission(Request(req), _AllowAnyAuthenticatedView()))

        # Method in dict allowed; method NOT in dict & no required_permission -> denied
        self.assertTrue(perm.has_permission(Request(req), _MethodMapPortalView()))
        post_req = self.factory.post("/dummy")
        post_req.session = {}
        force_authenticate(post_req, user=self.ops_user)
        self.assertFalse(perm.has_permission(Request(post_req), _MethodMapPortalView()))

    def test_api_key_blocked_on_ops_and_super_admin_and_checked_by_scope(self):
        key = ApiKey(
            name="ops-key",
            prefix="tg_live_1",
            key_hash="h",
            created_by=self.super_user,
            organization=self.org,
            scopes=["catalog:read"],
        )

        req_ops = self.factory.get("/ops")
        req_ops.session = {}
        force_authenticate(req_ops, user=self.super_user, token=key)
        drf_req = Request(req_ops)
        drf_req.api_key = key
        self.assertFalse(IsOpsUser().has_permission(drf_req, _OpsView()))
        self.assertFalse(IsSuperAdminUser().has_permission(drf_req, _SuperAdminView()))

        # HasPortalPermission rejects key without api_key_scopes
        self.assertFalse(HasPortalPermission().has_permission(drf_req, _UnconfiguredPortalView()))

        # Matching scope in api_key_scopes passes
        self.assertTrue(HasPortalPermission().has_permission(drf_req, _ScopedApiKeyPortalView()))

    def test_privilege_escalation_can_grant_and_sanitize_ceiling(self):
        org_admin_perms = resolve_membership_permissions(self.org_admin_mem)
        # ORG_ADMIN cannot grant finance:manage or supplier_identity:view
        self.assertFalse(can_grant(org_admin_perms, ["finance:manage"]))
        self.assertFalse(can_grant(org_admin_perms, ["supplier_identity:view"]))
        # ORG_ADMIN can grant catalog:read (which they possess)
        self.assertTrue(can_grant(org_admin_perms, ["catalog:read"]))
        # SUPER_ADMIN can grant any known permission
        self.assertTrue(can_grant([], ["finance:manage"], is_super_admin=True))
        # sanitize_permissions strips supplier_identity:view from customer/supplier roles
        self.assertEqual(
            sanitize_permissions(["catalog:read", "supplier_identity:view"], role_key="B2B_BUYER"),
            ["catalog:read"],
        )
        self.assertEqual(
            sanitize_permissions(["catalog:read", "supplier_identity:view"], role_key="SUPPLIER_ADMIN"),
            ["catalog:read"],
        )

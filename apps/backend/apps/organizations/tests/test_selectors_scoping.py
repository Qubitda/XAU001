"""Unit tests for centralized organization & branch queryset scoping helpers."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import ProductModel
from apps.commerce.models import B2bOrder
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Branch, Organization, OrganizationMembership
from apps.organizations.selectors import (
    TenantContext,
    scope_queryset_to_branch,
    scope_queryset_to_organization,
)

User = get_user_model()


class CentralizedScopingSelectorsTests(TestCase):
    def setUp(self) -> None:
        self.snap = get_current_rate_snapshot()
        self.org_a = Organization.objects.create(code="SCP-A", name="Org A", org_type=Organization.OrgType.DEALER)
        self.org_b = Organization.objects.create(code="SCP-B", name="Org B", org_type=Organization.OrgType.DEALER)
        self.br_a1 = Branch.objects.create(organization=self.org_a, code="A1", name="Şube A1")
        self.br_a2 = Branch.objects.create(organization=self.org_a, code="A2", name="Şube A2")
        self.br_b1 = Branch.objects.create(organization=self.org_b, code="B1", name="Şube B1")

        self.ops_user = User.objects.create_user(email="scp-ops@tara.local", password="pw", is_staff=True)
        self.user_a1 = User.objects.create_user(email="scp-a1@tara.local", password="pw")
        self.user_b1 = User.objects.create_user(email="scp-b1@tara.local", password="pw")

        self.m_ops = OrganizationMembership.objects.create(
            user=self.ops_user, organization=self.org_a, role_key="SUPER_ADMIN"
        )
        self.m_a1 = OrganizationMembership.objects.create(
            user=self.user_a1,
            organization=self.org_a,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            default_branch=self.br_a1,
        )
        self.m_a1.branches.add(self.br_a1)

        self.m_b1 = OrganizationMembership.objects.create(
            user=self.user_b1,
            organization=self.org_b,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            default_branch=self.br_b1,
        )
        self.m_b1.branches.add(self.br_b1)

        self.ctx_ops = TenantContext(
            user=self.ops_user,
            membership=self.m_ops,
            organization=self.org_a,
            branch=None,
            role_key="SUPER_ADMIN",
            permissions=frozenset(),
            is_ops=True,
        )
        self.ctx_a1 = TenantContext(
            user=self.user_a1,
            membership=self.m_a1,
            organization=self.org_a,
            branch=self.br_a1,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            permissions=frozenset(),
            is_ops=False,
        )
        self.ctx_b1 = TenantContext(
            user=self.user_b1,
            membership=self.m_b1,
            organization=self.org_b,
            branch=self.br_b1,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            permissions=frozenset(),
            is_ops=False,
        )
        self.ctx_anon = TenantContext(
            user=None,
            membership=None,
            organization=None,
            branch=None,
            role_key="B2C_CUSTOMER",
            permissions=frozenset(),
            is_ops=False,
        )

        # Shared vs Org-owned products (owner_organization nullable)
        self.prod_shared = ProductModel.objects.create(
            parent_sku="SCP-SHRD",
            title="Ortak Ürün",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            seo_slug="scp-shrd",
            owner_organization=None,
        )
        self.prod_a = ProductModel.objects.create(
            parent_sku="SCP-ORGA",
            title="Org A Ürün",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            seo_slug="scp-orga",
            owner_organization=self.org_a,
        )
        self.prod_b = ProductModel.objects.create(
            parent_sku="SCP-ORGB",
            title="Org B Ürün",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            seo_slug="scp-orgb",
            owner_organization=self.org_b,
        )

        # Orders across branches + unassigned (branch=None)
        def _mk_order(no, org, branch, creator):
            return B2bOrder.objects.create(
                order_no=no,
                organization=org,
                branch=branch,
                created_by=creator,
                rate_snapshot=self.snap,
                gold_rate_try_per_gram=Decimal("3000"),
                usd_try_rate=Decimal("34"),
                total_pieces=1,
                total_gross_gram=Decimal("3"),
                total_has_gold_gram=Decimal("1.8"),
                total_labor_and_stone_usd=Decimal("20"),
                total_wholesale_usd=Decimal("100"),
                total_wholesale_try=Decimal("3400"),
            )

        self.ord_a1 = _mk_order("ORD-SCP-A1", self.org_a, self.br_a1, self.user_a1)
        self.ord_a2 = _mk_order("ORD-SCP-A2", self.org_a, self.br_a2, self.user_a1)
        self.ord_a_unassigned = _mk_order("ORD-SCP-A0", self.org_a, None, self.user_a1)
        self.ord_b1 = _mk_order("ORD-SCP-B1", self.org_b, self.br_b1, self.user_b1)

    def test_scope_queryset_to_organization(self) -> None:
        all_prods = ProductModel.objects.all()
        self.assertEqual(
            set(scope_queryset_to_organization(all_prods, self.ctx_ops, org_field="owner_organization").values_list("parent_sku", flat=True)),
            {"SCP-SHRD", "SCP-ORGA", "SCP-ORGB"},
        )
        # Strict org-only (include_shared=False)
        self.assertEqual(
            set(scope_queryset_to_organization(all_prods, self.ctx_a1, org_field="owner_organization").values_list("parent_sku", flat=True)),
            {"SCP-ORGA"},
        )
        # Shared + own org
        self.assertEqual(
            set(scope_queryset_to_organization(all_prods, self.ctx_a1, org_field="owner_organization", include_shared=True).values_list("parent_sku", flat=True)),
            {"SCP-SHRD", "SCP-ORGA"},
        )
        # Wrong org sees 0 of org A's private records
        self.assertEqual(
            scope_queryset_to_organization(
                ProductModel.objects.filter(owner_organization=self.org_a),
                self.ctx_b1,
                org_field="owner_organization",
            ).count(),
            0,
        )
        # No org -> empty unless include_shared=True
        self.assertEqual(scope_queryset_to_organization(all_prods, self.ctx_anon, org_field="owner_organization").count(), 0)
        self.assertEqual(
            set(scope_queryset_to_organization(all_prods, self.ctx_anon, org_field="owner_organization", include_shared=True).values_list("parent_sku", flat=True)),
            {"SCP-SHRD"},
        )

    def test_scope_queryset_to_branch(self) -> None:
        all_orders = B2bOrder.objects.all()
        self.assertEqual(scope_queryset_to_branch(all_orders, self.ctx_ops).count(), 4)
        # A1 only sees A1 (not A2, not B1, not unassigned when include_unassigned=False)
        self.assertEqual(
            set(scope_queryset_to_branch(all_orders, self.ctx_a1, include_unassigned=False).values_list("order_no", flat=True)),
            {"ORD-SCP-A1"},
        )
        # Combined with org scope + include_unassigned=True: sees A1 and org-wide A0
        org_scoped = scope_queryset_to_organization(all_orders, self.ctx_a1)
        self.assertEqual(
            set(scope_queryset_to_branch(org_scoped, self.ctx_a1, include_unassigned=True).values_list("order_no", flat=True)),
            {"ORD-SCP-A1", "ORD-SCP-A0"},
        )
        # Wrong branch/org sees 0
        self.assertEqual(
            scope_queryset_to_branch(B2bOrder.objects.filter(branch=self.br_a1), self.ctx_b1).count(),
            0,
        )
        # No membership -> empty
        self.assertEqual(scope_queryset_to_branch(all_orders, self.ctx_anon, include_unassigned=True).count(), 0)

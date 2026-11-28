"""Regression tests for B2B branch-level scoping (IDOR prevention) across order/proforma views."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import B2bDraftLine, B2bOrder, B2bOrderLine
from apps.market.models import RateSnapshot
from apps.organizations.models import Branch, Organization, OrganizationMembership

User = get_user_model()


class B2bBranchScopingTests(TestCase):
    def setUp(self) -> None:
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-BR-1",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37"},
        )
        self.org = Organization.objects.create(
            code="BAYI-BR",
            name="Şubeli Bayi A.Ş.",
            org_type=Organization.OrgType.DEALER,
        )
        self.branch_a = Branch.objects.create(organization=self.org, code="SUBE-A", name="Şube A", city="İstanbul")
        self.branch_b = Branch.objects.create(organization=self.org, code="SUBE-B", name="Şube B", city="Ankara")

        self.user_a = User.objects.create_user(email="b2b-a@bayi.local", password="pw")
        m_a = OrganizationMembership.objects.create(
            user=self.user_a,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            default_branch=self.branch_a,
        )
        m_a.branches.add(self.branch_a)

        self.user_b = User.objects.create_user(email="b2b-b@bayi.local", password="pw")
        m_b = OrganizationMembership.objects.create(
            user=self.user_b,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            default_branch=self.branch_b,
        )
        m_b.branches.add(self.branch_b)

        self.user_multi = User.objects.create_user(email="b2b-multi@bayi.local", password="pw")
        m_multi = OrganizationMembership.objects.create(
            user=self.user_multi,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.ORG_ADMIN,
            default_branch=self.branch_a,
        )
        m_multi.branches.add(self.branch_a, self.branch_b)

        self.user_none = User.objects.create_user(email="b2b-none@bayi.local", password="pw")
        OrganizationMembership.objects.create(
            user=self.user_none,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
        )

        self.order_a = self._create_order("B2B-BR-A1", self.branch_a, self.user_a)
        self.order_b = self._create_order("B2B-BR-B1", self.branch_b, self.user_b)

        B2bDraftLine.objects.create(
            organization=self.org,
            created_by=self.user_a,
            sku="SKU-DRAFT-1-14K-BYZ-14",
            parent_sku="SKU-DRAFT-1",
            title="Taslak Yüzük",
            category="Yüzük",
            metal_color="Beyaz",
            purity_code="14K",
            size=14,
            qty=1,
            unit_gross_gram=Decimal("3.0000"),
            unit_net_metal_gram=Decimal("2.8000"),
            unit_fire_included_fine_gram=Decimal("1.7000"),
            unit_labor_and_stone_usd=Decimal("25.00"),
            unit_wholesale_usd=Decimal("200.00"),
            unit_wholesale_try=Decimal("6800.00"),
            snapshot_code=self.snap.snapshot_code,
        )

    def _create_order(self, order_no: str, branch: Branch, actor) -> B2bOrder:
        order = B2bOrder.objects.create(
            order_no=order_no,
            organization=self.org,
            branch=branch,
            created_by=actor,
            rate_snapshot=self.snap,
            usd_try_rate=Decimal("34.0000"),
            gold_rate_try_per_gram=Decimal("3200.0000"),
            contact_person="Test Yetkili",
            settlement_method="PESIN",
            rate_lock_mode="ANLIK",
            delivery_method="KURYE",
            total_pieces=1,
            total_gross_gram=Decimal("3.0000"),
            total_has_gold_gram=Decimal("1.7000"),
            total_labor_and_stone_usd=Decimal("25.00"),
            total_wholesale_usd=Decimal("200.00"),
            total_wholesale_try=Decimal("6800.00"),
        )
        B2bOrderLine.objects.create(
            order=order,
            sku=f"{order_no}-SKU",
            parent_sku="SKU-1",
            title="Test Yüzük",
            category="Yüzük",
            metal_color="Beyaz",
            purity_code="14K",
            size=14,
            qty=1,
            unit_gross_gram=Decimal("3.0000"),
            unit_net_metal_gram=Decimal("2.8000"),
            unit_fire_included_fine_gram=Decimal("1.7000"),
            unit_labor_and_stone_usd=Decimal("25.00"),
            unit_wholesale_usd=Decimal("200.00"),
            unit_wholesale_try=Decimal("6800.00"),
            snapshot_code=self.snap.snapshot_code,
        )
        return order

    def test_b2b_orders_list_scoped_to_authorized_branches(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        res_a = client.get("/api/v1/b2b/orders")
        self.assertEqual(res_a.status_code, 200)
        nos_a = [o["orderNo"] for o in res_a.json()["data"]]
        self.assertEqual(nos_a, ["B2B-BR-A1"])

        # Multi-branch user sees both authorized branches
        client.force_authenticate(user=self.user_multi)
        res_m = client.get("/api/v1/b2b/orders")
        self.assertEqual(res_m.status_code, 200)
        nos_m = {o["orderNo"] for o in res_m.json()["data"]}
        self.assertEqual(nos_m, {"B2B-BR-A1", "B2B-BR-B1"})

    def test_b2b_reorder_and_order_proforma_reject_unauthorized_branch(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user_a)

        # User A cannot reorder Branch B's order
        reorder_res = client.post(f"/api/v1/b2b/orders/{self.order_b.order_no}/reorder")
        self.assertEqual(reorder_res.status_code, 403)
        self.assertEqual(reorder_res.json()["code"], "BRANCH_ACCESS_DENIED")

        # User A cannot download Branch B's proforma PDF
        pdf_b = client.get(f"/api/v1/b2b/orders/{self.order_b.order_no}/proforma.pdf")
        self.assertEqual(pdf_b.status_code, 403)
        self.assertEqual(pdf_b.json()["code"], "BRANCH_ACCESS_DENIED")

        # User A can download their own branch's proforma PDF
        pdf_a = client.get(f"/api/v1/b2b/orders/{self.order_a.order_no}/proforma.pdf")
        self.assertEqual(pdf_a.status_code, 200)

    def test_b2b_draft_proforma_requires_authorized_branch_when_org_has_branches(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user_none)
        res_denied = client.get("/api/v1/b2b/draft/proforma.pdf")
        self.assertEqual(res_denied.status_code, 403)
        self.assertEqual(res_denied.json()["code"], "BRANCH_ACCESS_DENIED")

        client.force_authenticate(user=self.user_a)
        res_ok = client.get("/api/v1/b2b/draft/proforma.pdf")
        self.assertEqual(res_ok.status_code, 200)

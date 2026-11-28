"""Dealer finance limit reservation & idempotency regression tests."""

from decimal import Decimal

from django.test import TestCase

from apps.finance.models import DealerLedgerEntry
from apps.finance.services import reserve_organization_limits
from apps.organizations.models import Organization
from config.exceptions import DomainError


class DealerLimitTests(TestCase):
    def setUp(self) -> None:
        self.org = Organization.objects.create(
            code="FIN-TST",
            name="Finans Test Bayi",
            org_type=Organization.OrgType.DEALER,
            credit_limit_usd=Decimal("1000.00"),
            has_limit_gram=Decimal("50.0000"),
        )

    def test_reserve_organization_limits_is_idempotent(self) -> None:
        reserve_organization_limits(
            organization_id=self.org.id,
            settlement_method="OPEN_ACCOUNT",
            total_has_gold_gram=Decimal("5.0000"),
            total_labor_and_stone_usd=Decimal("100.00"),
            total_wholesale_usd=Decimal("400.00"),
            reference_no="ORD-FIN-001",
        )
        # Second call with same reference_no must NOT double-deduct
        reserve_organization_limits(
            organization_id=self.org.id,
            settlement_method="OPEN_ACCOUNT",
            total_has_gold_gram=Decimal("5.0000"),
            total_labor_and_stone_usd=Decimal("100.00"),
            total_wholesale_usd=Decimal("400.00"),
            reference_no="ORD-FIN-001",
        )
        self.org.refresh_from_db()
        self.assertEqual(self.org.used_credit_usd, Decimal("400.00"))
        self.assertEqual(
            DealerLedgerEntry.objects.filter(organization=self.org, reference_no="ORD-FIN-001").count(),
            1,
        )

    def test_reserve_organization_limits_rejects_credit_overflow(self) -> None:
        with self.assertRaises(DomainError) as ctx:
            reserve_organization_limits(
                organization_id=self.org.id,
                settlement_method="OPEN_ACCOUNT",
                total_has_gold_gram=Decimal("1.0000"),
                total_labor_and_stone_usd=Decimal("50.00"),
                total_wholesale_usd=Decimal("1500.00"),
                reference_no="ORD-FIN-OVER",
            )
        self.assertEqual(ctx.exception.error_code, "CREDIT_LIMIT_EXCEEDED")

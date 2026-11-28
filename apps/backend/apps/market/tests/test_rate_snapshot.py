"""RateSnapshot lifecycle & get_current_rate_snapshot() regression tests."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.market.models import RateSnapshot
from apps.market.services import create_rate_snapshot, get_current_rate_snapshot


class RateSnapshotTests(TestCase):
    def test_get_current_rate_snapshot_bootstraps_default_when_empty(self) -> None:
        self.assertEqual(RateSnapshot.objects.count(), 0)
        snap = get_current_rate_snapshot()
        self.assertIsNotNone(snap)
        self.assertTrue(snap.is_current)
        self.assertGreater(snap.live_has_gold_try_sell, Decimal("0"))
        self.assertGreater(snap.live_usd_sell, Decimal("0"))

    def test_create_rate_snapshot_marks_previous_not_current_and_stays_immutable(self) -> None:
        first = create_rate_snapshot(
            fx_base_rates={"TRY": "1", "USD": "35.00", "EUR": "38.00", "XAU": "100000.00"},
            source_mode=RateSnapshot.SourceMode.MANUAL,
        )
        second = create_rate_snapshot(
            fx_base_rates={"TRY": "1", "USD": "36.00", "EUR": "39.00", "XAU": "105000.00"},
            source_mode=RateSnapshot.SourceMode.MANUAL,
        )
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(get_current_rate_snapshot().id, second.id)

        with self.assertRaises(ValidationError):
            second.delete()
        with self.assertRaises(ValidationError):
            second.live_usd_sell = Decimal("99.00")
            second.save()

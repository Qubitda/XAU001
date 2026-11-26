from django.test import TestCase

from apps.idempotency.services import (
    PENDING_STATUS,
    abandon_idempotency_claim,
    claim_idempotency_slot,
    finalize_idempotency_record,
)


class IdempotencyClaimTests(TestCase):
    def test_second_claim_loses(self):
        first, claimed1 = claim_idempotency_slot(scope="s", key="k1", request_hash="h1")
        self.assertTrue(claimed1)
        self.assertEqual(first.response_status, PENDING_STATUS)

        second, claimed2 = claim_idempotency_slot(scope="s", key="k1", request_hash="h1")
        self.assertFalse(claimed2)
        self.assertEqual(second.id, first.id)

    def test_finalize_allows_replay(self):
        record, _ = claim_idempotency_slot(scope="s", key="k2", request_hash="h2")
        finalize_idempotency_record(
            record=record,
            request_hash="h2",
            response_status=201,
            response_body={"ok": True},
        )
        existing, claimed = claim_idempotency_slot(scope="s", key="k2", request_hash="h2")
        self.assertFalse(claimed)
        self.assertEqual(existing.response_status, 201)
        self.assertEqual(existing.response_body, {"ok": True})

    def test_abandon_allows_retry(self):
        record, _ = claim_idempotency_slot(scope="s", key="k3", request_hash="h3")
        abandon_idempotency_claim(record=record)
        again, claimed = claim_idempotency_slot(scope="s", key="k3", request_hash="h3")
        self.assertTrue(claimed)
        self.assertEqual(again.response_status, PENDING_STATUS)

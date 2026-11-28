"""WorkOrder creation and status state-machine regression tests."""

from django.test import TestCase

from apps.production.models import WorkOrder
from apps.production.services import create_work_order, transition_work_order_status
from config.exceptions import DomainError


class WorkOrderLifecycleTests(TestCase):
    def test_create_and_transition_work_order(self) -> None:
        wo = create_work_order(
            source_order_no="TG-B2C-WO-1",
            sku="TEST-14K-BYZ-14",
            size=14,
            quantity=1,
            work_order_no="WO-TEST-001",
        )
        self.assertEqual(wo.status, WorkOrder.Status.PLANNED)
        updated = transition_work_order_status(
            work_order_id_or_no=wo.work_order_no,
            next_status=WorkOrder.Status.CASTING,
        )
        self.assertEqual(updated.status, WorkOrder.Status.CASTING)

    def test_duplicate_work_order_and_invalid_transition_rejected(self) -> None:
        wo = create_work_order(
            source_order_no="TG-B2C-WO-2",
            sku="TEST-14K-BYZ-14",
            work_order_no="WO-TEST-DUP",
        )
        with self.assertRaises(DomainError) as dup_ctx:
            create_work_order(
                source_order_no="TG-B2C-WO-2",
                sku="TEST-14K-BYZ-14",
                work_order_no="WO-TEST-DUP",
            )
        self.assertEqual(dup_ctx.exception.error_code, "DUPLICATE_WORK_ORDER")

        # PLANNED -> SETTING directly is not in WORK_ORDER_ALLOWED_TRANSITIONS
        with self.assertRaises(DomainError) as tr_ctx:
            transition_work_order_status(
                work_order_id_or_no=wo.work_order_no,
                next_status=WorkOrder.Status.SETTING,
            )
        self.assertEqual(tr_ctx.exception.error_code, "INVALID_STATUS_TRANSITION")

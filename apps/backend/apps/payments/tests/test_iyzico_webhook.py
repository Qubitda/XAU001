"""iyzico webhook server-to-server verification, idempotency, and FAILURE guard tests."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import B2cOrder
from apps.customers.models import Customer
from apps.market.models import RateSnapshot
from apps.payments.models import PaymentTransaction

User = get_user_model()


class IyzicoWebhookSecurityTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="wh@test.local", password="pw", full_name="Webhook Buyer")
        self.customer = Customer.objects.create(user=self.user, full_name="Webhook Buyer", email="wh@test.local")
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-WH",
            is_current=True,
            live_has_gold_try_sell=Decimal("3000.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        self.order = B2cOrder.objects.create(
            order_no="TG-B2C-WH-001",
            customer=self.customer,
            created_by=self.user,
            rate_snapshot=self.snap,
            status=B2cOrder.Status.CONFIRMED,
            payment_method="CREDIT_CARD",
            shipping_full_name="Webhook Buyer",
            shipping_email="wh@test.local",
            gold_rate_try_per_gram=Decimal("3000.00"),
            subtotal_list_try=Decimal("1000.00"),
            grand_total_try=Decimal("1000.00"),
        )
        self.tx = PaymentTransaction.objects.create(
            order=self.order,
            provider=PaymentTransaction.Provider.IYZICO,
            conversation_id="TG-B2C-WH-001",
            payment_id="PAY-WH-1",
            token="TOK-WH-1",
            status=PaymentTransaction.Status.SUCCESS,
            price=Decimal("1000.00"),
            base_price=Decimal("1000.00"),
            paid_price=Decimal("1000.00"),
            currency="TRY",
        )
        self.client = APIClient()

    @patch("apps.payments.services.retrieve_payment")
    def test_spoofed_refund_webhook_rejected_when_iyzico_still_success(self, mock_retrieve) -> None:
        mock_retrieve.return_value = {
            "status": "success",
            "paymentStatus": "SUCCESS",
            "conversationId": "TG-B2C-WH-001",
            "itemTransactions": [{"paymentTransactionId": "ITX-1", "transactionStatus": 2, "refundedAmount": "0"}],
        }
        res = self.client.post(
            "/api/v1/payments/iyzico/webhook",
            {"paymentId": "PAY-WH-1", "iyziEventType": "REFUND", "refundPrice": "1000.00"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["data"]["verified"])
        self.tx.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(self.tx.refunded_amount, Decimal("0.00"))
        self.assertEqual(self.order.status, B2cOrder.Status.CONFIRMED)

    @patch("apps.payments.services.retrieve_payment")
    def test_verified_partial_refund_and_retry_idempotency(self, mock_retrieve) -> None:
        mock_retrieve.return_value = {
            "status": "success",
            "paymentStatus": "PARTIAL_REFUNDED",
            "conversationId": "TG-B2C-WH-001",
            "itemTransactions": [{"paymentTransactionId": "ITX-1", "transactionStatus": 2, "refundedAmount": "400.00"}],
        }
        res1 = self.client.post(
            "/api/v1/payments/iyzico/webhook",
            {"paymentId": "PAY-WH-1", "iyziEventType": "REFUND", "refundPrice": "400.00"},
            format="json",
        )
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()["data"]["verified"])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.PARTIAL_REFUNDED)
        self.assertEqual(self.tx.refunded_amount, Decimal("400.00"))

        # Retry of same webhook event must be idempotent (must not double-subtract)
        res2 = self.client.post(
            "/api/v1/payments/iyzico/webhook",
            {"paymentId": "PAY-WH-1", "iyziEventType": "REFUND", "refundPrice": "400.00"},
            format="json",
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["data"]["idempotent"])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.refunded_amount, Decimal("400.00"))

    @patch("apps.payments.services.retrieve_payment")
    def test_verified_cancel_webhook_marks_cancelled(self, mock_retrieve) -> None:
        mock_retrieve.return_value = {
            "status": "success",
            "paymentStatus": "CANCELLED",
            "conversationId": "TG-B2C-WH-001",
        }
        res = self.client.post(
            "/api/v1/payments/iyzico/webhook",
            {"paymentId": "PAY-WH-1", "iyziEventType": "CANCEL"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["data"]["verified"])
        self.tx.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.CANCELLED)
        self.assertEqual(self.order.status, B2cOrder.Status.REFUNDED)

    @patch("apps.payments.services.retrieve_checkout_form")
    def test_failure_webhook_requires_iyzico_confirmation(self, mock_cf) -> None:
        pending_order = B2cOrder.objects.create(
            order_no="TG-B2C-WH-002",
            customer=self.customer,
            created_by=self.user,
            rate_snapshot=self.snap,
            status=B2cOrder.Status.PENDING_PAYMENT,
            payment_method="CREDIT_CARD",
            shipping_full_name="Webhook Buyer",
            shipping_email="wh@test.local",
            gold_rate_try_per_gram=Decimal("3000.00"),
            subtotal_list_try=Decimal("500.00"),
            grand_total_try=Decimal("500.00"),
        )
        pending_tx = PaymentTransaction.objects.create(
            order=pending_order,
            provider=PaymentTransaction.Provider.IYZICO,
            conversation_id="TG-B2C-WH-002",
            token="TOK-WH-2",
            status=PaymentTransaction.Status.PENDING,
            price=Decimal("500.00"),
            base_price=Decimal("500.00"),
            paid_price=Decimal("500.00"),
            currency="TRY",
        )

        # Spoofed FAILURE when iyzico says INIT_THREEDS -> ignored
        mock_cf.return_value = {"status": "success", "paymentStatus": "INIT_THREEDS", "conversationId": "TG-B2C-WH-002"}
        r1 = self.client.post(
            "/api/v1/payments/iyzico/webhook",
            {"conversationId": "TG-B2C-WH-002", "status": "FAILURE"},
            format="json",
        )
        self.assertEqual(r1.status_code, 200)
        self.assertFalse(r1.json()["data"]["verified"])
        pending_tx.refresh_from_db()
        self.assertEqual(pending_tx.status, PaymentTransaction.Status.PENDING)

        # Confirmed FAILURE -> marks FAILURE and emits mail cleanly
        mock_cf.return_value = {"status": "success", "paymentStatus": "FAILURE", "conversationId": "TG-B2C-WH-002"}
        r2 = self.client.post(
            "/api/v1/payments/iyzico/webhook",
            {"conversationId": "TG-B2C-WH-002", "status": "FAILURE"},
            format="json",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["data"]["failed"])
        pending_tx.refresh_from_db()
        pending_order.refresh_from_db()
        self.assertEqual(pending_tx.status, PaymentTransaction.Status.FAILURE)
        self.assertEqual(pending_order.status, B2cOrder.Status.CANCELLED)

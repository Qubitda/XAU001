from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import ProductModel
from apps.commerce.models import B2cCartItem, B2cOrder
from apps.market.services import create_rate_snapshot
from apps.payments.models import PaymentTransaction
from apps.pricing.models import PriceLock


@override_settings(
    IYZICO_API_KEY="sandbox-test-key",
    IYZICO_SECRET_KEY="sandbox-test-secret",
    IYZICO_BASE_URL="sandbox-api.iyzipay.com",
    IYZICO_CALLBACK_BASE_URL="https://example.test",
    FRONTEND_STOREFRONT_URL="http://localhost:3000",
)
class IyzicoCheckoutFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="buyer-pay@test.local", password="pass-1234", full_name="Test Buyer"
        )
        self.client.force_authenticate(user=self.user)

        self.snap = create_rate_snapshot(
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
            live_has_gold_try_sell=Decimal("5000"),
        )
        self.lock = PriceLock.objects.create(
            user=self.user,
            rate_snapshot=self.snap,
            is_active=True,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        self.product = ProductModel.objects.create(
            parent_sku="P-PAY-1",
            title="Test Ring",
            collection="Pay Test",
            category="Yüzük",
            purity_code="14K",
            metal_color="Sarı",
            seo_slug="pay-test-ring",
            stock_status=ProductModel.StockStatus.MADE_TO_ORDER,
            stock_qty=0,
            gross_weight_gram=Decimal("3.5000"),
            sales_channels=["B2B", "B2B_API", "B2C_API"],
        )

        B2cCartItem.objects.create(
            user=self.user,
            sku="P-PAY-1-14K",
            parent_sku=self.product.parent_sku,
            title="Test Ring",
            category="Yüzük",
            metal_color="Sarı",
            purity_code="14K",
            size=14,
            size_unit_label="Yüzük Ölçüsü",
            qty=1,
            stock_status="Siparişe Özel",
            lead_time_text="5–7 iş günü",
            gross_weight_gram=Decimal("3.5000"),
            unit_list_price_try=Decimal("1000.00"),
            unit_final_price_try=Decimal("1000.00"),
            rate_snapshot=self.snap,
            snapshot_code=self.snap.snapshot_code,
        )

    def _payload(self):
        return {
            "customerName": "Test Buyer",
            "customerPhone": "05351234567",
            "customerEmail": "buyer-pay@test.local",
            "identityNumber": "11111111111",
            "shippingCity": "Istanbul",
            "shippingAddress": "Nidakule Göztepe",
            "paymentMethod": "CREDIT_CARD",
            "acceptedCustomPolicy": True,
        }

    @patch("apps.payments.services.initialize_checkout_form")
    def test_initialize_creates_pending_order_and_returns_url(self, mock_init):
        mock_init.return_value = {
            "status": "success",
            "token": "tok-abc-123",
            "paymentPageUrl": "https://sandbox-cpp.iyzipay.com?token=tok-abc-123",
            "checkoutFormContent": "<script></script>",
            "tokenExpireTime": 1800,
        }

        res = self.client.post(
            "/api/v1/storefront/payments/checkout-form/initialize",
            self._payload(),
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.content)
        data = res.json()["data"]
        self.assertTrue(data["paymentPageUrl"].startswith("https://sandbox-cpp.iyzipay.com"))
        self.assertEqual(data["token"], "tok-abc-123")

        order = B2cOrder.objects.get(order_no=data["orderNo"])
        self.assertEqual(order.status, B2cOrder.Status.PENDING_PAYMENT)
        self.assertEqual(B2cCartItem.objects.filter(user=self.user).count(), 0)

        tx = PaymentTransaction.objects.get(conversation_id=order.order_no)
        self.assertEqual(tx.token, "tok-abc-123")
        self.assertEqual(tx.status, PaymentTransaction.Status.REDIRECTED)

    @patch("apps.payments.services.retrieve_checkout_form")
    @patch("apps.payments.services.initialize_checkout_form")
    def test_callback_success_finalizes_order(self, mock_init, mock_retrieve):
        mock_init.return_value = {
            "status": "success",
            "token": "tok-ok",
            "paymentPageUrl": "https://sandbox-cpp.iyzipay.com?token=tok-ok",
        }
        init = self.client.post(
            "/api/v1/storefront/payments/checkout-form/initialize",
            self._payload(),
            format="json",
        )
        self.assertEqual(init.status_code, 201, init.content)
        order_no = init.json()["data"]["orderNo"]

        mock_retrieve.return_value = {
            "status": "success",
            "paymentStatus": "SUCCESS",
            "paymentId": "19831123",
            "conversationId": order_no,
            "paidPrice": "1000.00",
            "price": "1000.00",
            "token": "tok-ok",
        }

        cb = self.client.post("/api/v1/payments/iyzico/callback", {"token": "tok-ok"})
        self.assertEqual(cb.status_code, 302)
        self.assertIn("/odeme-basarili", cb["Location"])
        self.assertIn(order_no, cb["Location"])

        order = B2cOrder.objects.get(order_no=order_no)
        self.assertEqual(order.status, B2cOrder.Status.WORKSHOP)
        tx = PaymentTransaction.objects.get(token="tok-ok")
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(tx.payment_id, "19831123")

    @patch("apps.payments.services.retrieve_checkout_form")
    @patch("apps.payments.services.initialize_checkout_form")
    def test_callback_failure_cancels_order(self, mock_init, mock_retrieve):
        mock_init.return_value = {
            "status": "success",
            "token": "tok-fail",
            "paymentPageUrl": "https://sandbox-cpp.iyzipay.com?token=tok-fail",
        }
        init = self.client.post(
            "/api/v1/storefront/payments/checkout-form/initialize",
            self._payload(),
            format="json",
        )
        self.assertEqual(init.status_code, 201, init.content)
        order_no = init.json()["data"]["orderNo"]

        mock_retrieve.return_value = {
            "status": "failure",
            "paymentStatus": "FAILURE",
            "conversationId": order_no,
            "token": "tok-fail",
        }

        cb = self.client.post("/api/v1/payments/iyzico/callback", {"token": "tok-fail"})
        self.assertEqual(cb.status_code, 302)
        self.assertIn("/odeme-hatali", cb["Location"])

        order = B2cOrder.objects.get(order_no=order_no)
        self.assertEqual(order.status, B2cOrder.Status.CANCELLED)
        tx = PaymentTransaction.objects.get(token="tok-fail")
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILURE)

    def test_direct_credit_card_order_rejected(self):
        res = self.client.post(
            "/api/v1/storefront/orders",
            self._payload(),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertEqual(body.get("code"), "USE_IYZICO_CHECKOUT")

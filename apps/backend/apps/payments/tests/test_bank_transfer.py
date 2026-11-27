"""Bank transfer (Havale/EFT) tests: initiate, receipt upload, OPS approve/reject, manual IBAN refund."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import ProductModel, ProductVariant
from apps.commerce.models import B2cCartItem, B2cOrder
from apps.inventory.models import WarehouseStock
from apps.inventory.services import get_or_create_default_warehouse
from apps.market.models import RateSnapshot
from apps.payments.bank_transfer import (
    approve_bank_transfer,
    complete_manual_bank_refund,
    initiate_bank_transfer_checkout,
    reject_bank_transfer,
    upload_transfer_receipt,
)
from apps.payments.models import PaymentBankAccount, PaymentTransaction
from apps.pricing.models import PriceLock

User = get_user_model()


class BankTransferFlowTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="bt@test.local", password="pw", full_name="BT Buyer")
        self.ops_user = User.objects.create_user(email="ops_bt@test.local", password="pw", full_name="OPS BT")
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-BT",
            is_current=True,
            live_has_gold_try_sell=Decimal("3000.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        )
        self.bank = PaymentBankAccount.objects.create(
            bank_name="Garanti BBVA",
            account_holder="Tara Gold A.Ş.",
            iban="TR330006100519786457841326",
            currency="TRY",
            is_active=True,
        )
        self.product = ProductModel.objects.create(
            parent_sku="BT-RING-1",
            title="Havale Yüzük",
            category="Yüzük",
            sub_category="Tektaş",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.00"),
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2C_API"],
            seo_slug="bt-ring-1",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="BT-RING-1-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.00"),
            stock_qty=5,
            is_default=True,
        )
        WarehouseStock.objects.create(
            warehouse=get_or_create_default_warehouse(),
            variant=self.variant,
            quantity=5,
        )

    def _seed_cart(self) -> None:
        PriceLock.objects.create(
            user=self.user,
            rate_snapshot=self.snap,
            expires_at=timezone.now() + timedelta(minutes=15),
            is_active=True,
        )
        B2cCartItem.objects.create(
            user=self.user,
            variant=self.variant,
            sku=self.variant.sku,
            parent_sku=self.product.parent_sku,
            title=self.product.title,
            category=self.product.category,
            metal_color="Beyaz",
            purity_code="14K",
            size=14,
            qty=1,
            gross_weight_gram=Decimal("3.00"),
            unit_list_price_try=Decimal("5000.00"),
            unit_final_price_try=Decimal("5000.00"),
            rate_snapshot=self.snap,
            snapshot_code=self.snap.snapshot_code,
        )

    def _checkout_payload(self) -> dict:
        return {
            "customerName": "BT Buyer",
            "customerPhone": "+905551112233",
            "customerEmail": "bt@test.local",
            "shippingCity": "İstanbul",
            "shippingAddress": "Nuruosmaniye No:5",
            "acceptedCustomPolicy": True,
        }

    def test_initiate_receipt_approve_and_manual_refund(self) -> None:
        self._seed_cart()
        res = initiate_bank_transfer_checkout(user=self.user, payload=self._checkout_payload())
        order = B2cOrder.objects.get(order_no=res["orderNo"])
        self.assertEqual(order.status, B2cOrder.Status.PENDING_PAYMENT)
        tx = PaymentTransaction.objects.get(order=order, provider=PaymentTransaction.Provider.BANK_TRANSFER)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

        pdf = SimpleUploadedFile("dekont.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        tx = upload_transfer_receipt(user=self.user, order=order, uploaded_file=pdf)
        self.assertEqual(tx.status, PaymentTransaction.Status.RECEIPT_UPLOADED)

        tx = approve_bank_transfer(payment=tx, actor=self.ops_user)
        order.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(tx.receipt_status, PaymentTransaction.ReceiptStatus.APPROVED)
        self.assertEqual(order.status, B2cOrder.Status.CONFIRMED)

        with patch("apps.social_commerce.services.adjust_affiliate_conversion_for_partial_refund") as mock_adj:
            log1 = complete_manual_bank_refund(
                payment=tx,
                actor=self.ops_user,
                amount=Decimal("2000.00"),
                refund_iban="TR33 0006 1005 1978 6457 8413 26",
                refund_account_holder="BT Buyer",
            )
            self.assertEqual(log1.amount, Decimal("2000.00"))
            mock_adj.assert_called_once()
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.PARTIAL_REFUNDED)
        self.assertEqual(tx.refunded_amount, Decimal("2000.00"))

    def test_reject_bank_transfer_cancels_order_and_releases_stock(self) -> None:
        self._seed_cart()
        res = initiate_bank_transfer_checkout(user=self.user, payload=self._checkout_payload())
        order = B2cOrder.objects.get(order_no=res["orderNo"])
        tx = PaymentTransaction.objects.get(order=order, provider=PaymentTransaction.Provider.BANK_TRANSFER)

        tx = reject_bank_transfer(payment=tx, actor=self.ops_user, reason="Eksik tutar")
        order.refresh_from_db()
        ws = WarehouseStock.objects.get(variant=self.variant)
        self.assertEqual(tx.status, PaymentTransaction.Status.REJECTED)
        self.assertEqual(order.status, B2cOrder.Status.CANCELLED)
        self.assertEqual(ws.reserved_qty, 0)

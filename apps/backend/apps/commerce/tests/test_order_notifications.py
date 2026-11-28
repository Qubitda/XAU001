"""Tests for B2C (non-iyzico) and B2B order created/cancelled email and in-app notifications."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from apps.catalog.models import ProductModel, ProductVariant
from apps.commerce.models import B2bDraftLine, B2bOrder, B2cCartItem, B2cOrder
from apps.commerce.services import (
    submit_b2b_order,
    submit_b2c_order,
    transition_b2b_order_status,
    transition_b2c_order_status,
)
from apps.customers.models import Customer
from apps.inventory.services import get_or_create_default_warehouse, set_variant_warehouse_stock
from apps.mail.constants import ORDER_CANCELLED, ORDER_CREATED
from apps.mail.models import MailLog
from apps.market.models import RateSnapshot
from apps.notifications.models import Notification
from apps.organizations.models import Branch, Organization, OrganizationMembership
from apps.pricing.models import ChannelRule, CostLine, PriceLock, PricingRecipe

User = get_user_model()


@override_settings(
    TESTING=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class OrderNotificationWiringTests(TestCase):
    def setUp(self) -> None:
        self.snap = RateSnapshot.objects.create(
            snapshot_code="SNAP-NOTIF-1",
            is_current=True,
            live_has_gold_try_sell=Decimal("3200.00"),
            live_usd_sell=Decimal("34.00"),
            live_eur_sell=Decimal("37.00"),
            fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37"},
        )
        self.wh = get_or_create_default_warehouse()
        self.product = ProductModel.objects.create(
            parent_sku="NTF-001",
            title="Bildirim Test Yüzük",
            category="Yüzük",
            collection="Klasik",
            purity_code="14K",
            metal_color="Beyaz",
            gross_weight_gram=Decimal("3.50"),
            seo_slug="ntf-001",
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            sales_channels=["B2B", "B2C_API"],
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="NTF-001-14K-BYZ-14",
            purity_code="14K",
            metal_color="Beyaz",
            size=14,
            gross_weight_gram=Decimal("3.50"),
            is_default=True,
            is_active=True,
        )
        set_variant_warehouse_stock(
            variant=self.variant,
            warehouse=self.wh,
            quantity=10,
            reference_no="INIT-NTF-001",
        )
        recipe = PricingRecipe.objects.create(product=self.product, version=1, status=PricingRecipe.Status.DRAFT)
        CostLine.objects.create(recipe=recipe, line_type=CostLine.LineType.ISCILIK, fc_currency="USD", fc_price=Decimal("20.00"))
        ChannelRule.objects.create(recipe=recipe, channel="B2C_API", profit_unit="%", profit_value=Decimal("40"))
        ChannelRule.objects.create(recipe=recipe, channel="B2B", profit_unit="%", profit_value=Decimal("15"))
        PricingRecipe.objects.filter(id=recipe.id).update(status=PricingRecipe.Status.PUBLISHED)

        self.b2c_user = User.objects.create_user(email="b2c-notif@tara.local", password="pw", full_name="Ayşe Demir")
        Customer.objects.create(user=self.b2c_user, email="b2c-notif@tara.local", full_name="Ayşe Demir")

        self.org = Organization.objects.create(
            code="BAYI-NTF",
            name="Bildirim Bayi",
            org_type=Organization.OrgType.DEALER,
            email="bayi-org@tara.local",
        )
        self.branch = Branch.objects.create(organization=self.org, code="SUBE-N1", name="Merkez", city="İstanbul")
        self.b2b_user = User.objects.create_user(email="b2b-notif@tara.local", password="pw", full_name="Mehmet Kaya")
        m = OrganizationMembership.objects.create(
            user=self.b2b_user,
            organization=self.org,
            role_key=OrganizationMembership.RoleKey.B2B_BUYER,
            default_branch=self.branch,
        )
        m.branches.add(self.branch)

    def _create_b2c_havale_order(self) -> B2cOrder:
        B2cCartItem.objects.create(
            user=self.b2c_user,
            variant=self.variant,
            sku=self.variant.sku,
            parent_sku=self.product.parent_sku,
            title=self.product.title,
            category=self.product.category,
            metal_color="Beyaz",
            purity_code="14K",
            size=14,
            qty=1,
            gross_weight_gram=Decimal("3.50"),
            unit_list_price_try=Decimal("10000.00"),
            unit_final_price_try=Decimal("10000.00"),
            rate_snapshot=self.snap,
            snapshot_code=self.snap.snapshot_code,
        )
        lock = PriceLock.objects.create(
            user=self.b2c_user,
            rate_snapshot=self.snap,
            expires_at=self.snap.created_at + __import__("datetime").timedelta(hours=1),
            is_active=True,
        )
        return submit_b2c_order(
            user=self.b2c_user,
            payload={
                "paymentMethod": "HAVALE_EFT",
                "customerName": "Ayşe Demir",
                "customerPhone": "05551112233",
                "customerEmail": "b2c-notif@tara.local",
                "shippingCity": "İstanbul",
                "shippingAddress": "Nişantaşı No:1",
            },
            awaiting_payment=False,
        )

    def _create_b2b_order(self) -> B2bOrder:
        B2bDraftLine.objects.create(
            organization=self.org,
            created_by=self.b2b_user,
            variant=self.variant,
            sku=self.variant.sku,
            parent_sku=self.product.parent_sku,
            title=self.product.title,
            category=self.product.category,
            metal_color="Beyaz",
            purity_code="14K",
            size=14,
            qty=1,
            unit_gross_gram=Decimal("3.5000"),
            unit_net_metal_gram=Decimal("3.2000"),
            unit_fire_included_fine_gram=Decimal("1.9000"),
            unit_labor_and_stone_usd=Decimal("20.00"),
            unit_wholesale_usd=Decimal("250.00"),
            unit_wholesale_try=Decimal("8500.00"),
            snapshot_code=self.snap.snapshot_code,
        )
        return submit_b2b_order(
            user=self.b2b_user,
            organization=self.org,
            branch=self.branch,
            payload={
                "contactPerson": "Mehmet Kaya",
                "settlementMethod": "PESIN",
                "rateLockMode": "ANLIK",
                "deliveryMethod": "KURYE",
            },
        )

    def test_b2c_havale_order_created_and_cancelled_notifications(self) -> None:
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            order = self._create_b2c_havale_order()

        self.assertTrue(
            MailLog.objects.filter(
                template_key=ORDER_CREATED,
                recipient="b2c-notif@tara.local",
                context_snapshot__order_no=order.order_no,
            ).exists()
        )
        self.assertTrue(any(order.order_no in m.body for m in mail.outbox))

        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            transition_b2c_order_status(
                order_no=order.order_no,
                next_status=B2cOrder.Status.CANCELLED,
                actor=self.b2c_user,
            )

        self.assertTrue(
            MailLog.objects.filter(
                template_key=ORDER_CANCELLED,
                recipient="b2c-notif@tara.local",
                context_snapshot__order_no=order.order_no,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.b2c_user,
                title__icontains=order.order_no,
            ).exists()
        )
        self.assertTrue(any(order.order_no in m.body for m in mail.outbox))

    def test_b2b_order_created_and_cancelled_notifications(self) -> None:
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            order = self._create_b2b_order()

        self.assertTrue(
            MailLog.objects.filter(
                template_key=ORDER_CREATED,
                recipient="b2b-notif@tara.local",
                organization=self.org,
                context_snapshot__order_no=order.order_no,
            ).exists()
        )
        self.assertTrue(any(order.order_no in m.body for m in mail.outbox))

        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            transition_b2b_order_status(
                order_no=order.order_no,
                next_status=B2bOrder.Status.CANCELLED,
                actor=self.b2b_user,
            )

        self.assertTrue(
            MailLog.objects.filter(
                template_key=ORDER_CANCELLED,
                recipient="b2b-notif@tara.local",
                organization=self.org,
                context_snapshot__order_no=order.order_no,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.b2b_user,
                title__icontains=order.order_no,
            ).exists()
        )
        self.assertTrue(any(order.order_no in m.body for m in mail.outbox))

    def test_notification_failure_does_not_rollback_order_or_cancel(self) -> None:
        with patch("apps.mail.events.emit_order_created", side_effect=RuntimeError("mail down")):
            order = self._create_b2c_havale_order()
        self.assertTrue(B2cOrder.objects.filter(order_no=order.order_no).exists())

        with patch("apps.mail.events.emit_order_cancelled", side_effect=RuntimeError("mail down")):
            cancelled = transition_b2c_order_status(
                order_no=order.order_no,
                next_status=B2cOrder.Status.CANCELLED,
                actor=self.b2c_user,
            )
        self.assertEqual(cancelled.status, B2cOrder.Status.CANCELLED)

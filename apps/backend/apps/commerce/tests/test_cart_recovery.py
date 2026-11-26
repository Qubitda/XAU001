"""Abandoned cart / B2B draft recovery state machine tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.commerce.models import (
    B2bDraftLine,
    B2cCartItem,
    CartRecoveryAttempt,
    CartRecoverySession,
    OpsSalesTask,
)
from apps.commerce.recovery import (
    process_session,
    scan_abandoned_carts,
    suppress_b2c_cart,
    touch_b2b_draft,
    touch_b2c_cart,
)
from apps.mail.models import MailLog
from apps.market.services import create_rate_snapshot
from apps.notifications.models import Notification
from apps.organizations.models import Organization


def _seed_rates():
    return create_rate_snapshot(
        fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        live_has_gold_try_sell=Decimal("3000"),
    )


def _b2c_line(user, *, title="Yüzük", price="1500.00", qty=1) -> B2cCartItem:
    snap = _seed_rates()
    return B2cCartItem.objects.create(
        user=user,
        sku="SE009-BYZ-14",
        parent_sku="SE009",
        title=title,
        category="Yüzük",
        metal_color="Beyaz",
        purity_code="14K",
        size=14,
        qty=qty,
        unit_list_price_try=Decimal(price),
        unit_final_price_try=Decimal(price),
        rate_snapshot=snap,
        snapshot_code=snap.snapshot_code,
        stock_status="Stokta",
    )


def _b2b_line(org, user, *, price="60000.00", supply="STOCK") -> B2bDraftLine:
    snap = _seed_rates()
    return B2bDraftLine.objects.create(
        organization=org,
        created_by=user,
        sku="SE009-BYZ-14",
        parent_sku="SE009",
        title="Bayi Yüzük",
        category="Yüzük",
        metal_color="Beyaz",
        purity_code="14K",
        size=14,
        qty=1,
        supply_type=supply,
        unit_gross_gram=Decimal("3.0000"),
        unit_net_metal_gram=Decimal("2.5000"),
        unit_fire_included_fine_gram=Decimal("2.4000"),
        unit_labor_and_stone_usd=Decimal("10.00"),
        unit_wholesale_usd=Decimal("100.00"),
        unit_wholesale_try=Decimal(price),
        pricing_currency="TRY",
        rate_snapshot=snap,
        snapshot_code=snap.snapshot_code,
    )


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CART_RECOVERY_B2C_T1_SECONDS=0,
    CART_RECOVERY_B2C_T2_SECONDS=0,
    CART_RECOVERY_B2C_T3_SECONDS=0,
    CART_RECOVERY_B2B_T1_SECONDS=0,
    CART_RECOVERY_B2B_T2_SECONDS=0,
    CART_RECOVERY_B2B_T3_SECONDS=0,
    CART_RECOVERY_B2C_OPS_THRESHOLD_TRY="100000",
    CART_RECOVERY_B2B_OPS_THRESHOLD_TRY="50000",
    CART_RECOVERY_COOLDOWN_DAYS=7,
)
def _grant_commercial_email(user):
    from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
    from apps.consent.services import append_consent
    from apps.customers.services import get_or_update_customer_for_user

    customer = get_or_update_customer_for_user(
        user=user, full_name=user.full_name, email=user.email, phone=user.phone or ""
    )
    append_consent(
        customer=customer,
        purpose=ConsentPurpose.COMMERCIAL_EMAIL,
        channel=ConsentChannel.EMAIL,
        status=ConsentStatus.GRANTED,
        source=ConsentSource.OPS,
        actor=user,
    )
    return customer


class CartRecoveryB2cTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="recovery-b2c@test.local", password="pass-1234", full_name="B2C Buyer"
        )
        _grant_commercial_email(self.user)

    def test_touch_creates_active_session(self):
        _b2c_line(self.user)
        session = touch_b2c_cart(user=self.user)
        self.assertIsNotNone(session)
        self.assertEqual(session.status, CartRecoverySession.Status.ACTIVE)
        self.assertEqual(session.segment, CartRecoverySession.Segment.B2C)
        self.assertEqual(session.stage, CartRecoverySession.Stage.NONE)
        self.assertEqual(session.line_count, 1)

    def test_scan_dispatches_t1_email(self):
        _b2c_line(self.user)
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(hours=2)
        session.save(update_fields=["cart_updated_at"])

        result = scan_abandoned_carts()
        self.assertGreaterEqual(result["dispatched"], 1)

        session.refresh_from_db()
        self.assertEqual(session.stage, CartRecoverySession.Stage.T1)
        self.assertTrue(
            CartRecoveryAttempt.objects.filter(
                session=session,
                stage="T1",
                channel=CartRecoveryAttempt.Channel.EMAIL,
            ).exists()
        )
        self.assertTrue(
            MailLog.objects.filter(
                recipient=self.user.email, template_key="cart_recovery_b2c_t1"
            ).exists()
        )

    def test_full_pipeline_to_t3_and_cooldown(self):
        _b2c_line(self.user, price="1500.00")
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(days=2)
        session.save(update_fields=["cart_updated_at"])

        for expected in ("T1", "T2", "T3"):
            got = process_session(session)
            self.assertEqual(got, expected)
            session.refresh_from_db()

        self.assertEqual(session.status, CartRecoverySession.Status.COMPLETED)
        self.assertIsNotNone(session.cooldown_until)
        self.assertTrue(
            Notification.objects.filter(recipient=self.user, title__icontains="Sepetiniz").exists()
        )
        # Below B2C OPS threshold — no open OPS task
        self.assertFalse(
            OpsSalesTask.objects.filter(
                recovery_session=session, status=OpsSalesTask.Status.OPEN
            ).exists()
        )

    def test_high_value_creates_ops_task(self):
        _b2c_line(self.user, price="120000.00")
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(days=2)
        session.save(update_fields=["cart_updated_at"])
        for _ in range(3):
            process_session(session)
            session.refresh_from_db()
        self.assertTrue(
            OpsSalesTask.objects.filter(
                recovery_session=session,
                kind=OpsSalesTask.Kind.ABANDONED_CART_CALL,
                status=OpsSalesTask.Status.OPEN,
            ).exists()
        )

    def test_suppress_on_empty_and_checkout_reason(self):
        _b2c_line(self.user)
        session = touch_b2c_cart(user=self.user)
        B2cCartItem.objects.filter(user=self.user).delete()
        suppress_b2c_cart(user=self.user, reason=CartRecoverySession.SuppressReason.CHECKOUT)
        session.refresh_from_db()
        self.assertEqual(session.status, CartRecoverySession.Status.SUPPRESSED)
        self.assertEqual(session.suppress_reason, CartRecoverySession.SuppressReason.CHECKOUT)

    def test_idempotent_stage_dispatch(self):
        _b2c_line(self.user)
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(hours=2)
        session.save(update_fields=["cart_updated_at"])
        process_session(session)
        process_session(session)  # should advance to T2, not duplicate T1
        session.refresh_from_db()
        self.assertEqual(
            CartRecoveryAttempt.objects.filter(session=session, stage="T1").count(), 1
        )


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CART_RECOVERY_B2B_T1_SECONDS=0,
    CART_RECOVERY_B2B_T2_SECONDS=0,
    CART_RECOVERY_B2B_T3_SECONDS=0,
    CART_RECOVERY_B2B_OPS_THRESHOLD_TRY="50000",
    CART_RECOVERY_COOLDOWN_DAYS=7,
)
class CartRecoveryB2bTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="recovery-b2b@test.local", password="pass-1234", full_name="Bayi Yetkili"
        )
        self.org = Organization.objects.create(
            code="REC-BAYI",
            name="Recovery Bayi A.Ş.",
            tax_number="1234567890",
        )

    def test_b2b_pipeline_creates_ops_for_stock_draft(self):
        _b2b_line(self.org, self.user, price="10000.00", supply="STOCK")
        session = touch_b2b_draft(user=self.user, organization=self.org)
        self.assertEqual(session.segment, CartRecoverySession.Segment.B2B)
        session.cart_updated_at = timezone.now() - timedelta(days=3)
        session.save(update_fields=["cart_updated_at"])

        for expected in ("T1", "T2", "T3"):
            self.assertEqual(process_session(session), expected)
            session.refresh_from_db()

        self.assertTrue(
            MailLog.objects.filter(template_key="cart_recovery_b2b_t1").exists()
        )
        self.assertTrue(
            MailLog.objects.filter(template_key="cart_recovery_b2b_t2").exists()
        )
        self.assertTrue(
            OpsSalesTask.objects.filter(
                recovery_session=session,
                kind=OpsSalesTask.Kind.ABANDONED_DRAFT_CALL,
                status=OpsSalesTask.Status.OPEN,
            ).exists()
        )

    def test_cooldown_blocks_new_active_outreach(self):
        _b2b_line(self.org, self.user, price="60000.00")
        session = touch_b2b_draft(user=self.user, organization=self.org)
        session.status = CartRecoverySession.Status.COMPLETED
        session.stage = CartRecoverySession.Stage.T3
        session.cooldown_until = timezone.now() + timedelta(days=7)
        session.save()

        touched = touch_b2b_draft(user=self.user, organization=self.org)
        self.assertEqual(touched.id, session.id)
        self.assertNotEqual(touched.status, CartRecoverySession.Status.ACTIVE)
        self.assertIsNone(process_session(touched))


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CART_RECOVERY_B2C_T1_SECONDS=0,
    CART_RECOVERY_B2C_T2_SECONDS=0,
    CART_RECOVERY_B2C_T3_SECONDS=0,
)
class GuestCartRecoveryTests(TestCase):
    def test_guest_lead_capture_and_t1_email(self):
        from apps.commerce.recovery import capture_guest_cart_lead
        from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
        from apps.consent.services import append_consent

        session = capture_guest_cart_lead(
            email="guest@test.local",
            items=[
                {
                    "sku": "SE009",
                    "title": "Solitaire",
                    "qty": 1,
                    "unitFinalPriceTry": "12000.00",
                }
            ],
        )
        self.assertIsNotNone(session)
        self.assertIsNone(session.user_id)
        self.assertEqual(session.guest_email, "guest@test.local")
        append_consent(
            guest_email="guest@test.local",
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.FOOTER,
        )
        session.cart_updated_at = timezone.now() - timedelta(hours=2)
        session.save(update_fields=["cart_updated_at"])
        self.assertEqual(process_session(session), "T1")
        self.assertTrue(
            MailLog.objects.filter(
                recipient="guest@test.local", template_key="cart_recovery_b2c_t1"
            ).exists()
        )


class ProformaPdfTests(TestCase):
    def test_build_text_pdf_bytes(self):
        from apps.commerce.proforma_pdf import build_text_pdf

        pdf = build_text_pdf(["Satir 1", "Satir 2 — şöşü"], title="Proforma")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"%%EOF", pdf)

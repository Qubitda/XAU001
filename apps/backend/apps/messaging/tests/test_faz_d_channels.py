"""Faz D — SMS/WhatsApp recovery consent gates."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.commerce.models import B2cCartItem, CartRecoveryAttempt, CartRecoverySession
from apps.commerce.recovery import process_session, touch_b2c_cart
from apps.consent.models import ConsentChannel, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent
from apps.customers.services import get_or_update_customer_for_user
from apps.market.services import create_rate_snapshot
from apps.messaging.models import ChannelOutboundLog
from apps.messaging.services import channel_consent_ok, enqueue_channel_message


def _seed_rates():
    return create_rate_snapshot(
        fx_base_rates={"TRY": "1", "USD": "34", "EUR": "37", "XAU": "168000"},
        live_has_gold_try_sell=Decimal("3000"),
    )


def _line(user):
    snap = _seed_rates()
    return B2cCartItem.objects.create(
        user=user,
        sku="SE009-BYZ-14",
        parent_sku="SE009",
        title="Yüzük",
        category="Yüzük",
        metal_color="Beyaz",
        purity_code="14K",
        size=14,
        qty=1,
        unit_list_price_try=Decimal("1500.00"),
        unit_final_price_try=Decimal("1500.00"),
        rate_snapshot=snap,
        snapshot_code=snap.snapshot_code,
        stock_status="Stokta",
    )


class ChannelConsentUnitTests(TestCase):
    def test_sms_consent_required(self):
        user = User.objects.create_user(
            email="sms@test.local", password="pass-1234", full_name="S", phone="05551234567"
        )
        customer = get_or_update_customer_for_user(
            user=user, full_name=user.full_name, email=user.email, phone=user.phone
        )
        self.assertFalse(
            channel_consent_ok(channel="SMS", customer=customer)
        )
        append_consent(
            customer=customer,
            purpose=ConsentPurpose.COMMERCIAL_SMS,
            channel=ConsentChannel.SMS,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.OPS,
        )
        self.assertTrue(channel_consent_ok(channel="SMS", customer=customer))

    @override_settings(MESSAGING_SMS_ENABLED=True, MESSAGING_SMS_PROVIDER="console")
    def test_console_send_logs(self):
        log = enqueue_channel_message(
            channel="SMS",
            recipient="05551112233",
            body="Test",
            template_key="unit",
        )
        self.assertEqual(log.status, ChannelOutboundLog.Status.SENT)
        self.assertEqual(log.provider, "console")


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CART_RECOVERY_B2C_T1_SECONDS=0,
    CART_RECOVERY_B2C_T2_SECONDS=0,
    CART_RECOVERY_B2C_T3_SECONDS=0,
    MESSAGING_SMS_ENABLED=True,
    MESSAGING_WHATSAPP_ENABLED=True,
    MESSAGING_SMS_PROVIDER="console",
    MESSAGING_WHATSAPP_PROVIDER="console",
)
class RecoveryChannelGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ch@test.local",
            password="pass-1234",
            full_name="Channel User",
            phone="05559876543",
        )
        self.customer = get_or_update_customer_for_user(
            user=self.user,
            full_name=self.user.full_name,
            email=self.user.email,
            phone=self.user.phone,
        )
        # Email consent so T1/T3 email path can proceed where needed
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.OPS,
        )
        _line(self.user)

    def test_sms_skipped_without_consent(self):
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(days=2)
        session.save(update_fields=["cart_updated_at"])
        process_session(session)  # T1 email
        process_session(session)  # T2 in-app + SMS
        sms = CartRecoveryAttempt.objects.filter(
            session=session, stage="T2", channel=CartRecoveryAttempt.Channel.SMS
        ).first()
        self.assertIsNotNone(sms)
        self.assertEqual(sms.status, CartRecoveryAttempt.Status.SKIPPED)
        self.assertEqual(sms.skip_reason, "NO_CONSENT")

    def test_sms_and_whatsapp_sent_with_consent(self):
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_SMS,
            channel=ConsentChannel.SMS,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.OPS,
        )
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_WHATSAPP,
            channel=ConsentChannel.WHATSAPP,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.OPS,
        )
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(days=2)
        session.save(update_fields=["cart_updated_at"])
        for _ in range(3):
            process_session(session)
            session.refresh_from_db()
        sms = CartRecoveryAttempt.objects.get(
            session=session, stage="T2", channel=CartRecoveryAttempt.Channel.SMS
        )
        wa = CartRecoveryAttempt.objects.get(
            session=session, stage="T3", channel=CartRecoveryAttempt.Channel.WHATSAPP
        )
        self.assertEqual(sms.status, CartRecoveryAttempt.Status.SENT)
        self.assertEqual(wa.status, CartRecoveryAttempt.Status.SENT)
        self.assertTrue(
            ChannelOutboundLog.objects.filter(channel="SMS", status="SENT").exists()
        )
        self.assertTrue(
            ChannelOutboundLog.objects.filter(channel="WHATSAPP", status="SENT").exists()
        )

    @override_settings(MESSAGING_SMS_ENABLED=False, MESSAGING_WHATSAPP_ENABLED=False)
    def test_disabled_channels_no_attempt(self):
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(days=2)
        session.save(update_fields=["cart_updated_at"])
        for _ in range(3):
            process_session(session)
            session.refresh_from_db()
        self.assertFalse(
            CartRecoveryAttempt.objects.filter(
                session=session, channel=CartRecoveryAttempt.Channel.SMS
            ).exists()
        )
        self.assertFalse(
            CartRecoveryAttempt.objects.filter(
                session=session, channel=CartRecoveryAttempt.Channel.WHATSAPP
            ).exists()
        )

    @override_settings(
        MESSAGING_SMS_ENABLED=True,
        MESSAGING_SMS_PROVIDER="webhook",
        MESSAGING_SMS_WEBHOOK_URL="",
    )
    def test_sms_send_failed_is_failed_not_skipped(self):
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_SMS,
            channel=ConsentChannel.SMS,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.OPS,
        )
        session = touch_b2c_cart(user=self.user)
        session.cart_updated_at = timezone.now() - timedelta(days=2)
        session.save(update_fields=["cart_updated_at"])
        process_session(session)  # T1
        process_session(session)  # T2 SMS
        sms = CartRecoveryAttempt.objects.get(
            session=session, stage="T2", channel=CartRecoveryAttempt.Channel.SMS
        )
        self.assertEqual(sms.status, CartRecoveryAttempt.Status.FAILED)
        self.assertEqual(sms.skip_reason, "SEND_FAILED")

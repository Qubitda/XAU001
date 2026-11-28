"""KVKK / commercial consent lifecycle & channel gating regression tests."""

from django.test import TestCase

from apps.consent.models import ConsentChannel, ConsentLog, ConsentPurpose, ConsentSource, ConsentStatus
from apps.consent.services import append_consent, has_active_consent
from apps.customers.models import Customer
from apps.messaging.services import channel_consent_ok


class ConsentLifecycleTests(TestCase):
    def setUp(self) -> None:
        self.customer = Customer.objects.create(
            email="kvkk-test@tara.local",
            full_name="Zeynep Kaya",
            phone="05551234567",
        )

    def test_grant_then_withdraw_consent_updates_active_status(self) -> None:
        self.assertFalse(
            has_active_consent(
                customer=self.customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel=ConsentChannel.EMAIL,
            )
        )

        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.GRANTED,
            source=ConsentSource.REGISTER,
        )
        self.assertTrue(
            has_active_consent(
                customer=self.customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel=ConsentChannel.EMAIL,
            )
        )

        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_EMAIL,
            channel=ConsentChannel.EMAIL,
            status=ConsentStatus.WITHDRAWN,
            source=ConsentSource.IYS,
        )
        self.assertFalse(
            has_active_consent(
                customer=self.customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel=ConsentChannel.EMAIL,
            )
        )
        # Append-only evidence: both rows remain in ConsentLog
        self.assertEqual(
            ConsentLog.objects.filter(
                customer=self.customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel=ConsentChannel.EMAIL,
            ).count(),
            2,
        )

    def test_channel_consent_blocks_all_commercial_channels_without_grant(self) -> None:
        for channel in (ConsentChannel.EMAIL, ConsentChannel.SMS, ConsentChannel.WHATSAPP):
            self.assertFalse(channel_consent_ok(channel=channel, customer=self.customer))

        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_SMS,
            channel=ConsentChannel.SMS,
            status=ConsentStatus.GRANTED,
        )
        self.assertTrue(channel_consent_ok(channel="SMS", customer=self.customer))
        self.assertFalse(channel_consent_ok(channel="EMAIL", customer=self.customer))
        self.assertFalse(channel_consent_ok(channel="WHATSAPP", customer=self.customer))

        # Revoke SMS -> blocked again
        append_consent(
            customer=self.customer,
            purpose=ConsentPurpose.COMMERCIAL_SMS,
            channel=ConsentChannel.SMS,
            status=ConsentStatus.WITHDRAWN,
        )
        self.assertFalse(channel_consent_ok(channel="SMS", customer=self.customer))

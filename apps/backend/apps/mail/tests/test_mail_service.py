from django.core import mail
from django.test import TestCase, override_settings

from apps.mail.constants import PAYMENT_SUCCESS, WELCOME
from apps.mail.crypto import decrypt_secret, encrypt_secret
from apps.mail.events import emit_payment_success, emit_welcome
from apps.mail.models import MailLog
from apps.mail.service import MailService


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MAIL_ENCRYPTION_KEY="test-mail-encryption-key-32b!!",
)
class MailServiceTests(TestCase):
    def test_aes_roundtrip(self):
        blob = encrypt_secret("AppPassword-123!")
        self.assertNotEqual(blob, "AppPassword-123!")
        self.assertEqual(decrypt_secret(blob), "AppPassword-123!")

    def test_filesystem_welcome_render_and_send(self):
        log = MailService().send(
            template_key=WELCOME,
            recipient="buyer@test.local",
            context={"customer_name": "Ayşe", "verify_url": "http://localhost:3000/e-posta-dogrula"},
        )
        self.assertEqual(log.status, MailLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Hoş geldiniz", mail.outbox[0].alternatives[0][0])
        self.assertIn("Ayşe", mail.outbox[0].alternatives[0][0])

    def test_payment_success_event_queues_and_sends_sync_fallback(self):
        # Celery broker typically unavailable in unit tests → sync fallback in on_commit.
        with self.captureOnCommitCallbacks(execute=True):
            log_id = emit_payment_success(
                recipient="payer@test.local",
                customer_name="Emre",
                order_no="TG-B2C-2026-ABC",
                amount="12500.00",
                currency="TRY",
                date="26.11.2026 18:00",
                order_url="http://localhost:3000/hesabim/siparisler/TG-B2C-2026-ABC",
            )
        self.assertTrue(log_id)
        log = MailLog.objects.get(id=log_id)
        self.assertEqual(log.template_key, PAYMENT_SUCCESS)
        self.assertEqual(log.status, MailLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("TG-B2C-2026-ABC", html)
        self.assertIn("12500.00", html)

    def test_emit_welcome_on_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            emit_welcome(
                recipient="new@test.local",
                customer_name="Yeni Üye",
                verify_url="http://localhost:3000/e-posta-dogrula?x=1",
            )
        self.assertEqual(MailLog.objects.filter(template_key=WELCOME).count(), 1)
        self.assertEqual(MailLog.objects.get(template_key=WELCOME).status, MailLog.Status.SENT)

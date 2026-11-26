from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import email_verify_token, password_reset_token
from apps.organizations.models import OrganizationMembership


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ENABLE_B2C_SELF_REGISTER=True,
    ENFORCE_EMAIL_VERIFICATION=False,
)
class AuthLifecycleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_b2c_register_creates_membership_and_sends_mail(self):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                reverse("auth-register"),
                {
                    "email": "buyer@example.com",
                    "password": "ComplexPass123!",
                    "fullName": "Buyer User",
                    "phone": "+905551112233",
                },
                format="json",
            )
        self.assertEqual(res.status_code, 201)
        user = User.objects.get(email="buyer@example.com")
        self.assertTrue(
            OrganizationMembership.objects.filter(
                user=user, role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER
            ).exists()
        )
        # welcome + email_verification
        self.assertGreaterEqual(len(mail.outbox), 1)
        subjects = " ".join(m.subject.lower() for m in mail.outbox)
        self.assertTrue("doğrulama" in subjects or "hoş" in subjects)

    def test_password_reset_flow(self):
        user = User.objects.create_user(
            email="reset@example.com", password="OldPass123!", full_name="Reset Me"
        )
        with self.captureOnCommitCallbacks(execute=True):
            forgot = self.client.post(
                reverse("auth-password-forgot"),
                {"email": "reset@example.com"},
                format="json",
            )
        self.assertEqual(forgot.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token.make_token(user)
        reset = self.client.post(
            reverse("auth-password-reset"),
            {"uid": uid, "token": token, "newPassword": "NewPass123!"},
            format="json",
        )
        self.assertEqual(reset.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass123!"))

    def test_email_verify(self):
        user = User.objects.create_user(
            email="verify@example.com", password="Pass1234!", full_name="Verify Me"
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verify_token.make_token(user)
        res = self.client.post(
            reverse("auth-email-verify"),
            {"uid": uid, "token": token},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class _EmailVerifyTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):  # noqa: ANN001
        email_field = getattr(user, "email", "") or ""
        verified = getattr(user, "email_verified_at", None)
        verified_ts = "" if verified is None else str(int(verified.timestamp()))
        return f"{user.pk}{user.password}{email_field}{verified_ts}{timestamp}"


password_reset_token = PasswordResetTokenGenerator()
email_verify_token = _EmailVerifyTokenGenerator()

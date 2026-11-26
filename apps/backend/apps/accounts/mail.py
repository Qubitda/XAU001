"""Account lifecycle emails — event-driven via apps.mail (async queue + logs)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.mail.events import emit_email_verification, emit_password_reset, emit_welcome

from .tokens import email_verify_token, password_reset_token

logger = logging.getLogger(__name__)


def _frontend_base() -> str:
    return (getattr(settings, "FRONTEND_STOREFRONT_URL", "") or "http://localhost:3000").rstrip("/")


def send_password_reset_email(*, user) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token.make_token(user)
    link = f"{_frontend_base()}/sifre-sifirla?uid={uid}&token={token}"
    log_id = emit_password_reset(
        recipient=user.email,
        customer_name=user.full_name or user.email,
        reset_url=link,
    )
    return bool(log_id)


def send_email_verification(*, user, also_welcome: bool = False) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verify_token.make_token(user)
    link = f"{_frontend_base()}/e-posta-dogrula?uid={uid}&token={token}"
    name = user.full_name or user.email
    if also_welcome:
        emit_welcome(recipient=user.email, customer_name=name, verify_url=link)
    log_id = emit_email_verification(
        recipient=user.email,
        customer_name=name,
        verify_url=link,
    )
    return bool(log_id)

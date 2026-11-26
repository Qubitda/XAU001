"""AES-256-GCM helpers for SMTP password at rest."""

from __future__ import annotations

import base64
import hashlib
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _aes_key() -> bytes:
    raw = (getattr(settings, "MAIL_ENCRYPTION_KEY", "") or "").strip()
    if not raw:
        raw = getattr(settings, "SECRET_KEY", "") or ""
    if not raw:
        raise ImproperlyConfigured("MAIL_ENCRYPTION_KEY or SECRET_KEY required for mail crypto.")
    # SHA-256 → 32-byte AES-256 key (stable derivation).
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> str:
    if plaintext is None:
        return ""
    text = str(plaintext)
    if not text:
        return ""
    nonce = os.urandom(12)
    aesgcm = AESGCM(_aes_key())
    ciphertext = aesgcm.encrypt(nonce, text.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(blob: str) -> str:
    if not blob:
        return ""
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    if len(raw) < 13:
        raise ValueError("Invalid ciphertext blob.")
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_aes_key())
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

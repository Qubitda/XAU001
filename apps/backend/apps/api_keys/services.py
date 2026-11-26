from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .constants import KEY_PREFIX, VALID_SCOPES
from .models import ApiKey

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.organizations.models import Organization


def _api_key_pepper() -> bytes:
    """
    HMAC pepper for API key hashes. Prefer dedicated API_KEY_HASH_PEPPER;
    fall back to SECRET_KEY so hashes are never unsalted SHA-256 of the key alone.
    """
    pepper = (getattr(settings, "API_KEY_HASH_PEPPER", None) or "").strip()
    if not pepper:
        pepper = settings.SECRET_KEY
    return pepper.encode("utf-8")


def hash_api_key(raw_key: str) -> str:
    return hmac.new(_api_key_pepper(), raw_key.encode("utf-8"), hashlib.sha256).hexdigest()


def _legacy_hash_api_key(raw_key: str) -> str:
    """Pre-pepper SHA-256; kept only for transparent upgrade on verify."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _lookup_prefix(raw_key: str) -> str | None:
    if not raw_key.startswith(KEY_PREFIX):
        return None
    secret = raw_key[len(KEY_PREFIX) :]
    if len(secret) < 8:
        return None
    return secret[:8]


@transaction.atomic
def create_api_key(
    *,
    organization: Organization,
    name: str,
    created_by: User,
    scopes: list[str] | None = None,
    expires_at=None,
) -> tuple[ApiKey, str]:
    secret = secrets.token_urlsafe(32)
    plaintext = f"{KEY_PREFIX}{secret}"
    prefix = secret[:8]
    normalized_scopes = [s for s in (scopes or []) if s in VALID_SCOPES]
    if not normalized_scopes:
        from .constants import DEFAULT_SCOPES

        normalized_scopes = list(DEFAULT_SCOPES)

    api_key = ApiKey.objects.create(
        organization=organization,
        name=name.strip(),
        prefix=prefix,
        key_hash=hash_api_key(plaintext),
        scopes=normalized_scopes,
        created_by=created_by,
        expires_at=expires_at,
    )
    return api_key, plaintext


def verify_api_key(raw_key: str) -> ApiKey | None:
    prefix = _lookup_prefix(raw_key)
    if prefix is None:
        return None

    candidates = list(
        ApiKey.objects.filter(prefix=prefix, is_active=True).select_related(
            "organization", "created_by"
        )[:8]
    )
    if not candidates:
        return None

    expected_hash = hash_api_key(raw_key)
    legacy_hash = _legacy_hash_api_key(raw_key)
    for candidate in candidates:
        matched = hmac.compare_digest(candidate.key_hash, expected_hash)
        if not matched and hmac.compare_digest(candidate.key_hash, legacy_hash):
            # Transparent upgrade from unsalted SHA-256 → peppered HMAC.
            ApiKey.objects.filter(pk=candidate.pk).update(key_hash=expected_hash)
            matched = True
        if not matched:
            continue
        if candidate.is_expired:
            return None
        ApiKey.objects.filter(pk=candidate.pk).update(last_used_at=timezone.now())
        return candidate
    return None


def revoke_api_key(api_key: ApiKey) -> ApiKey:
    api_key.is_active = False
    api_key.save(update_fields=["is_active", "updated_at"])
    return api_key

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit
from apps.mail.crypto import decrypt_secret, encrypt_secret

from ..models import SocialChannel, SocialConnection

logger = logging.getLogger(__name__)

OAUTH_STATE_TTL_SECONDS = 600


def _validate_oauth_redirect_uri(redirect_uri: str) -> str:
    uri = (redirect_uri or "").strip()
    parsed = urlparse(uri)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SocialCommerceError("Geçersiz OAuth redirectUri.", code="INVALID_REDIRECT_URI", status_code=400)
    origin = f"{parsed.scheme}://{parsed.netloc}".lower()
    allowed_origins: set[str] = set()
    for candidate in (
        list(getattr(settings, "SOCIAL_OAUTH_ALLOWED_REDIRECT_URIS", []) or [])
        + list(getattr(settings, "CORS_ALLOWED_ORIGINS", []) or [])
        + [getattr(settings, "FRONTEND_STOREFRONT_URL", "") or ""]
    ):
        c = str(candidate or "").strip()
        if not c:
            continue
        cp = urlparse(c)
        if cp.scheme and cp.netloc:
            allowed_origins.add(f"{cp.scheme}://{cp.netloc}".lower())
    if not allowed_origins or origin not in allowed_origins:
        raise SocialCommerceError(
            "Güvenilmeyen veya yapılandırılmamış OAuth redirectUri origin'i.",
            code="UNTRUSTED_REDIRECT_URI",
            status_code=400,
        )
    return uri


class SocialCommerceError(Exception):
    def __init__(self, message: str, *, code: str = "SOCIAL_COMMERCE_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def decrypt_connection_token(conn: SocialConnection | None) -> str:
    if conn is None or not conn.access_token_encrypted:
        return ""
    try:
        return decrypt_secret(conn.access_token_encrypted)
    except Exception:
        logger.warning("Failed to decrypt social connection token channel=%s", conn.channel_id)
        return ""


def _oauth_app_creds(platform: str) -> tuple[str, str]:
    p = platform.upper()
    if p in ("INSTAGRAM", "WHATSAPP"):
        return (
            (getattr(settings, "META_APP_ID", "") or "").strip(),
            (getattr(settings, "META_APP_SECRET", "") or "").strip(),
        )
    if p == "TIKTOK":
        return (
            (getattr(settings, "TIKTOK_CLIENT_KEY", "") or "").strip(),
            (getattr(settings, "TIKTOK_CLIENT_SECRET", "") or "").strip(),
        )
    if p == "PINTEREST":
        return (
            (getattr(settings, "PINTEREST_APP_ID", "") or "").strip(),
            (getattr(settings, "PINTEREST_APP_SECRET", "") or "").strip(),
        )
    return ("", "")


def build_oauth_authorize_url(*, channel: SocialChannel, redirect_uri: str) -> dict[str, Any]:
    """Generate official OAuth authorization URL with single-use CSRF state."""
    safe_redirect = _validate_oauth_redirect_uri(redirect_uri)
    client_id, _ = _oauth_app_creds(channel.platform)
    if not client_id:
        raise SocialCommerceError(
            f"{channel.platform} için OAuth app client_id yapılandırılmamış.",
            code="OAUTH_NOT_CONFIGURED",
            status_code=400,
        )
    state = secrets.token_urlsafe(24)
    cache.set(
        f"soc_oauth_state:{state}",
        {
            "channel_id": str(channel.id),
            "platform": channel.platform,
            "redirect_uri": safe_redirect,
        },
        timeout=OAUTH_STATE_TTL_SECONDS,
    )
    p = channel.platform.upper()
    if p in ("INSTAGRAM", "WHATSAPP"):
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": safe_redirect,
                "state": state,
                "scope": "instagram_basic,instagram_content_publish,catalog_management,whatsapp_business_messaging",
                "response_type": "code",
            }
        )
        url = f"https://www.facebook.com/v21.0/dialog/oauth?{params}"
    elif p == "TIKTOK":
        params = urlencode(
            {
                "client_key": client_id,
                "redirect_uri": safe_redirect,
                "state": state,
                "scope": "user.info.basic,video.publish,video.list",
                "response_type": "code",
            }
        )
        url = f"https://www.tiktok.com/v2/auth/authorize/?{params}"
    elif p == "PINTEREST":
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": safe_redirect,
                "state": state,
                "scope": "boards:read,pins:read,pins:write,catalogs:read,catalogs:write",
                "response_type": "code",
            }
        )
        url = f"https://www.pinterest.com/oauth/?{params}"
    else:
        raise SocialCommerceError(f"Desteklenmeyen OAuth platformu: {channel.platform}")

    return {"authorizeUrl": url, "state": state, "expiresIn": OAUTH_STATE_TTL_SECONDS}


def handle_oauth_callback(
    *,
    channel: SocialChannel,
    code: str,
    state: str,
    redirect_uri: str,
    actor=None,
) -> SocialConnection:
    """Validate OAuth state & redirect_uri, exchange authorization code for tokens, and store encrypted."""
    safe_redirect = _validate_oauth_redirect_uri(redirect_uri)
    cached = cache.get(f"soc_oauth_state:{state}")
    if not cached or cached.get("channel_id") != str(channel.id):
        raise SocialCommerceError("Geçersiz veya süresi dolmuş OAuth state.", code="INVALID_OAUTH_STATE", status_code=400)
    if cached.get("redirect_uri") != safe_redirect:
        raise SocialCommerceError(
            "OAuth redirectUri başlangıçtaki adresle eşleşmiyor.",
            code="REDIRECT_URI_MISMATCH",
            status_code=400,
        )
    cache.delete(f"soc_oauth_state:{state}")

    client_id, client_secret = _oauth_app_creds(channel.platform)
    if not client_id or not client_secret:
        raise SocialCommerceError(
            f"{channel.platform} OAuth client_id/client_secret yapılandırılmamış.",
            code="OAUTH_NOT_CONFIGURED",
            status_code=400,
        )

    p = channel.platform.upper()
    try:
        if p in ("INSTAGRAM", "WHATSAPP"):
            resp = requests.get(
                "https://graph.facebook.com/v21.0/oauth/access_token",
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": safe_redirect,
                    "code": code,
                },
                timeout=12,
            )
            data = resp.json() if resp.content else {}
        elif p == "TIKTOK":
            resp = requests.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": safe_redirect,
                },
                timeout=12,
            )
            data = resp.json() if resp.content else {}
        elif p == "PINTEREST":
            resp = requests.post(
                "https://api.pinterest.com/v5/oauth/token",
                auth=(client_id, client_secret),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": safe_redirect,
                },
                timeout=12,
            )
            data = resp.json() if resp.content else {}
        else:
            raise SocialCommerceError(f"Desteklenmeyen OAuth platformu: {channel.platform}")
    except SocialCommerceError:
        raise
    except Exception as exc:
        raise SocialCommerceError(f"OAuth token değişimi başarısız: {exc}", code="OAUTH_EXCHANGE_FAILED", status_code=502)

    access_token = str(data.get("access_token") or "")
    if resp.status_code >= 400 or not access_token:
        raise SocialCommerceError(
            str(data.get("error_description") or data.get("message") or "OAuth token alınamadı."),
            code="OAUTH_EXCHANGE_FAILED",
            status_code=400,
        )

    expires_in = data.get("expires_in")
    expires_at = (
        timezone.now() + timedelta(seconds=int(expires_in))
        if isinstance(expires_in, (int, float)) and expires_in > 0
        else None
    )
    return connect_social_channel(
        channel=channel,
        access_token=access_token,
        refresh_token=str(data.get("refresh_token") or ""),
        expires_at=expires_at,
        actor=actor,
    )


def refresh_channel_token(*, channel: SocialChannel, actor=None) -> SocialConnection:
    """
    Refresh OAuth access token per platform protocol:
    - Meta (INSTAGRAM / WHATSAPP): exchanges existing long-lived access_token via fb_exchange_token
      (falls back to refresh_token if stored, since Meta Graph API does not issue refresh_token).
    - TikTok / Pinterest: exchanges encrypted refresh_token.
    """
    conn = getattr(channel, "connection", None)
    if conn is None:
        raise SocialCommerceError("Kanal bağlantısı bulunamadı.", code="NO_REFRESH_TOKEN", status_code=400)
    client_id, client_secret = _oauth_app_creds(channel.platform)
    if not client_id or not client_secret:
        raise SocialCommerceError("OAuth app kimlik bilgileri yapılandırılmamış.", code="OAUTH_NOT_CONFIGURED", status_code=400)

    p = channel.platform.upper()
    refresh_token = ""
    if p in ("INSTAGRAM", "WHATSAPP"):
        exchange_token = (
            decrypt_secret(conn.refresh_token_encrypted)
            if conn.refresh_token_encrypted
            else decrypt_connection_token(conn)
        )
        if not exchange_token:
            raise SocialCommerceError(
                "Meta token yenileme için aktif access_token veya refresh_token bulunamadı.",
                code="NO_REFRESH_TOKEN",
                status_code=400,
            )
        resp = requests.get(
            "https://graph.facebook.com/v21.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "fb_exchange_token": exchange_token,
            },
            timeout=12,
        )
    elif p in ("TIKTOK", "PINTEREST"):
        if not conn.refresh_token_encrypted:
            raise SocialCommerceError("Yenileme token'ı (refresh_token) bulunamadı.", code="NO_REFRESH_TOKEN", status_code=400)
        refresh_token = decrypt_secret(conn.refresh_token_encrypted)
        if p == "TIKTOK":
            resp = requests.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                timeout=12,
            )
        else:
            resp = requests.post(
                "https://api.pinterest.com/v5/oauth/token",
                auth=(client_id, client_secret),
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                timeout=12,
            )
    else:
        raise SocialCommerceError(f"{channel.platform} için token yenileme akışı desteklenmiyor.", status_code=400)

    data = resp.json() if resp.content else {}
    new_token = str(data.get("access_token") or "")
    if resp.status_code >= 400 or not new_token:
        conn.status = SocialConnection.Status.EXPIRED
        conn.last_error = str(data.get("error_description") or data.get("message") or "Token yenilenemedi.")
        conn.save(update_fields=["status", "last_error", "updated_at"])
        raise SocialCommerceError(conn.last_error, code="OAUTH_REFRESH_FAILED", status_code=400)

    expires_in = data.get("expires_in")
    expires_at = (
        timezone.now() + timedelta(seconds=int(expires_in))
        if isinstance(expires_in, (int, float)) and expires_in > 0
        else None
    )
    next_refresh = str(data.get("refresh_token") or refresh_token)
    return connect_social_channel(
        channel=channel,
        access_token=new_token,
        refresh_token=next_refresh,
        expires_at=expires_at,
        actor=actor,
    )


@transaction.atomic
def revoke_channel_connection(*, channel: SocialChannel, actor=None) -> SocialConnection:
    conn, _ = SocialConnection.objects.get_or_create(channel=channel)
    conn.access_token_encrypted = ""
    conn.refresh_token_encrypted = ""
    conn.status = SocialConnection.Status.REVOKED
    conn.last_error = ""
    conn.save()
    record_audit(
        actor=actor,
        action="social.channel.revoked",
        entity_type="SocialChannel",
        entity_id=str(channel.id),
        metadata={"platform": channel.platform},
    )
    return conn


@transaction.atomic
def connect_social_channel(
    *,
    channel: SocialChannel,
    access_token: str,
    refresh_token: str = "",
    webhook_secret: str = "",
    scopes: list[str] | None = None,
    expires_at=None,
    actor=None,
) -> SocialConnection:
    """Store encrypted OAuth/API tokens for a SocialChannel without logging secrets."""
    conn, _ = SocialConnection.objects.get_or_create(channel=channel)
    if access_token:
        conn.access_token_encrypted = encrypt_secret(access_token.strip())
        conn.status = SocialConnection.Status.CONNECTED
    if refresh_token:
        conn.refresh_token_encrypted = encrypt_secret(refresh_token.strip())
    if webhook_secret:
        conn.webhook_secret_encrypted = encrypt_secret(webhook_secret.strip())
    if scopes is not None:
        conn.scopes = list(scopes)
    if expires_at is not None:
        conn.token_expires_at = expires_at
    conn.last_error = ""
    conn.save()

    record_audit(
        actor=actor,
        action="social.channel.connected",
        entity_type="SocialChannel",
        entity_id=str(channel.id),
        metadata={"platform": channel.platform, "status": conn.status},
    )
    return conn

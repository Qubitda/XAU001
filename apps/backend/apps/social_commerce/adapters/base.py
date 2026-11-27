from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ChannelCapabilities:
    platform: str
    country_code: str
    supports_catalog_feed: bool
    supports_direct_publish: bool
    supports_inbox_api: bool
    supports_in_app_shop: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderResult:
    ok: bool
    status: str  # PUBLISHED | SYNCED | NOT_CONFIGURED | MANUAL_REQUIRED | ERROR
    external_id: str = ""
    external_url: str = ""
    error: str = ""
    raw: dict[str, Any] | None = None


def verify_hmac_sha256(*, raw_body: bytes, secret: str, signature_header: str) -> bool:
    """Verify HMAC-SHA256 webhook signature (supports 'sha256=<hex>' or raw '<hex>')."""
    if not secret or not signature_header:
        return False
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig[7:]
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), sig.lower())


class SocialProviderAdapter(ABC):
    platform: str

    @abstractmethod
    def capabilities(self, country_code: str = "TR") -> ChannelCapabilities:
        ...

    @abstractmethod
    def sync_catalog_items(
        self,
        *,
        access_token: str,
        external_catalog_id: str,
        items: list[dict[str, Any]],
    ) -> ProviderResult:
        ...

    @abstractmethod
    def publish_post(
        self,
        *,
        access_token: str,
        external_account_id: str,
        post_type: str,
        caption: str,
        media_urls: list[str],
        target_url: str = "",
    ) -> ProviderResult:
        ...

    @abstractmethod
    def send_message(
        self,
        *,
        access_token: str,
        external_account_id: str,
        recipient_id: str,
        body: str,
    ) -> ProviderResult:
        ...

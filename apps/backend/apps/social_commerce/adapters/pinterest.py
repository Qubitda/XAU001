from __future__ import annotations

import logging
from typing import Any

import requests

from .base import ChannelCapabilities, ProviderResult, SocialProviderAdapter

logger = logging.getLogger(__name__)

PINTEREST_API_BASE = "https://api.pinterest.com/v5"


class PinterestBusinessAdapter(SocialProviderAdapter):
    platform = "PINTEREST"

    def capabilities(self, country_code: str = "TR") -> ChannelCapabilities:
        return ChannelCapabilities(
            platform=self.platform,
            country_code=(country_code or "TR").upper(),
            supports_catalog_feed=True,
            supports_direct_publish=True,
            supports_inbox_api=False,
            supports_in_app_shop=False,
            notes="Pinterest Business API v5 ile Product Pin ve otomatik katalog feed'i desteklenir.",
        )

    def sync_catalog_items(
        self,
        *,
        access_token: str,
        external_catalog_id: str,
        items: list[dict[str, Any]],
    ) -> ProviderResult:
        if not access_token or not external_catalog_id:
            return ProviderResult(
                ok=False,
                status="NOT_CONFIGURED",
                error="Pinterest Business OAuth token veya catalog_id tanımlı değil.",
            )
        if not items:
            return ProviderResult(ok=False, status="EMPTY_FEED", error="Boş ürün listesi senkronize edilemez.")
        batch_items = [
            {
                "item_id": str(it["id"]),
                "attributes": {
                    "title": str(it.get("title") or "")[:500],
                    "description": str(it.get("description") or "")[:10000],
                    "link": str(it.get("link") or ""),
                    "image_link": [str(it.get("image_link") or "")] if it.get("image_link") else [],
                    "price": str(it.get("price") or ""),
                    "availability": "IN_STOCK" if it.get("availability") == "in stock" else "OUT_OF_STOCK",
                    "brand": str(it.get("brand") or "TARA DIAMOND"),
                },
            }
            for it in items
        ]
        try:
            resp = requests.post(
                f"{PINTEREST_API_BASE}/catalogs/items/batch",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "country": "TR",
                    "language": "TR",
                    "operation": "UPSERT",
                    "items": batch_items,
                },
                timeout=15,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400:
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(data.get("message") or f"HTTP_{resp.status_code}"),
                    raw=data,
                )
            return ProviderResult(
                ok=True,
                status="SYNCED",
                external_id=str(data.get("batch_id") or external_catalog_id),
                raw=data,
            )
        except Exception as exc:
            logger.exception("Pinterest catalog batch sync failed")
            return ProviderResult(ok=False, status="ERROR", error=str(exc)[:400])

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
        if not access_token or not external_account_id:
            return ProviderResult(
                ok=False,
                status="NOT_CONFIGURED",
                error="Pinterest OAuth bağlantısı veya board_id tanımlı değil.",
            )
        if not media_urls:
            return ProviderResult(ok=False, status="ERROR", error="Pinterest Pin için görsel URL zorunludur.")
        try:
            resp = requests.post(
                f"{PINTEREST_API_BASE}/pins",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "board_id": external_account_id,
                    "title": caption[:100],
                    "description": caption[:500],
                    "link": target_url or None,
                    "media_source": {"source_type": "image_url", "url": media_urls[0]},
                },
                timeout=12,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400:
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(data.get("message") or f"HTTP_{resp.status_code}"),
                    raw=data,
                )
            pin_id = str(data.get("id", ""))
            return ProviderResult(
                ok=True,
                status="PUBLISHED",
                external_id=pin_id,
                external_url=f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else "",
                raw=data,
            )
        except Exception as exc:
            logger.exception("Pinterest publish failed")
            return ProviderResult(ok=False, status="ERROR", error=str(exc)[:400])

    def send_message(
        self,
        *,
        access_token: str,
        external_account_id: str,
        recipient_id: str,
        body: str,
    ) -> ProviderResult:
        return ProviderResult(
            ok=False,
            status="MANUAL_REQUIRED",
            error="Pinterest mesajlaşma API'si desteklenmemektedir.",
        )

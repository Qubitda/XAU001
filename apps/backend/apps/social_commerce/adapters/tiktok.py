from __future__ import annotations

import logging
from typing import Any

import requests

from .base import ChannelCapabilities, ProviderResult, SocialProviderAdapter

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TIKTOK_BUSINESS_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"


class TikTokBusinessAdapter(SocialProviderAdapter):
    platform = "TIKTOK"

    def capabilities(self, country_code: str = "TR") -> ChannelCapabilities:
        cc = (country_code or "TR").upper()
        return ChannelCapabilities(
            platform=self.platform,
            country_code=cc,
            supports_catalog_feed=True,
            supports_direct_publish=True,
            supports_inbox_api=False,
            supports_in_app_shop=False,
            notes=(
                "Türkiye'de TikTok Shop doğrudan desteklenmediği için web ürün sayfası ve "
                "WhatsApp yönlendirmesi kullanılır; TikTok Shop mimaride bayraklı olarak hazırdır."
            ),
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
                error="TikTok Business token veya catalog_id tanımlı değil.",
            )
        if not items:
            return ProviderResult(ok=False, status="EMPTY_FEED", error="Boş ürün listesi senkronize edilemez.")
        dpa_products = [
            {
                "sku_id": str(it["id"]),
                "title": str(it.get("title") or "")[:500],
                "description": str(it.get("description") or "")[:2000],
                "availability": "IN_STOCK" if it.get("availability") == "in stock" else "OUT_OF_STOCK",
                "image_url": str(it.get("image_link") or ""),
                "landing_page_url": str(it.get("link") or ""),
                "price_info": {"price": str(it.get("priceTry") or "0.00"), "currency": "TRY"},
                "brand": str(it.get("brand") or "TARA DIAMOND"),
            }
            for it in items
        ]
        try:
            resp = requests.post(
                f"{TIKTOK_BUSINESS_API_BASE}/catalog/product/upload/",
                headers={"Access-Token": access_token},
                json={
                    "catalog_id": external_catalog_id,
                    "dpa_products": dpa_products,
                },
                timeout=15,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400 or (data.get("code") not in (None, 0)):
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(data.get("message") or f"HTTP_{resp.status_code}"),
                    raw=data,
                )
            return ProviderResult(
                ok=True,
                status="SYNCED",
                external_id=str(data.get("data", {}).get("feed_id") or external_catalog_id),
                raw=data,
            )
        except Exception as exc:
            logger.exception("TikTok catalog upload failed")
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
                error="TikTok OAuth bağlantısı henüz yapılmamış.",
            )
        if not media_urls:
            return ProviderResult(ok=False, status="ERROR", error="TikTok videosu için video URL zorunludur.")
        try:
            resp = requests.post(
                f"{TIKTOK_API_BASE}/post/publish/video/init/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "post_info": {"title": caption[:150], "privacy_level": "PUBLIC_TO_EVERYONE"},
                    "source_info": {"source": "PULL_FROM_URL", "video_url": media_urls[0]},
                },
                timeout=12,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400 or data.get("error", {}).get("code", "ok") != "ok":
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(data.get("error", {}).get("message") or f"HTTP_{resp.status_code}"),
                    raw=data,
                )
            publish_id = str(data.get("data", {}).get("publish_id", ""))
            # TikTok /init/ only queues async processing; do NOT mark PUBLISHED yet.
            return ProviderResult(ok=True, status="PUBLISHING", external_id=publish_id, raw=data)
        except Exception as exc:
            logger.exception("TikTok publish init failed")
            return ProviderResult(ok=False, status="ERROR", error=str(exc)[:400])

    def check_publish_status(
        self,
        *,
        access_token: str,
        publish_id: str,
    ) -> ProviderResult:
        """Poll TikTok /post/publish/status/fetch/ to confirm PUBLISH_COMPLETE."""
        if not access_token or not publish_id:
            return ProviderResult(
                ok=False,
                status="NOT_CONFIGURED",
                error="TikTok access token veya publish_id eksik.",
            )
        try:
            resp = requests.post(
                f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"publish_id": publish_id},
                timeout=10,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400:
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(data.get("error", {}).get("message") or f"HTTP_{resp.status_code}"),
                    raw=data,
                )
            tk_status = str(data.get("data", {}).get("status", "")).upper()
            if tk_status == "PUBLISH_COMPLETE":
                return ProviderResult(ok=True, status="PUBLISHED", external_id=publish_id, raw=data)
            if tk_status in ("FAILED", "PUBLISH_FAILED"):
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(data.get("data", {}).get("fail_reason") or "TikTok yayınlama başarısız."),
                    raw=data,
                )
            return ProviderResult(ok=True, status="PUBLISHING", external_id=publish_id, raw=data)
        except Exception as exc:
            logger.exception("TikTok status fetch failed")
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
            error="TikTok doğrudan mesajlaşma API'si üçüncü taraf uygulamalar için kısıtlıdır.",
        )

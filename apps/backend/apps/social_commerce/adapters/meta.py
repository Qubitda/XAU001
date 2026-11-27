from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

from .base import ChannelCapabilities, ProviderResult, SocialProviderAdapter

logger = logging.getLogger(__name__)

META_GRAPH_BASE = "https://graph.facebook.com/v21.0"


class MetaInstagramAdapter(SocialProviderAdapter):
    platform = "INSTAGRAM"

    def capabilities(self, country_code: str = "TR") -> ChannelCapabilities:
        cc = (country_code or "TR").upper()
        # Meta IG Shop in-app checkout is region-gated; TR uses catalog feed + web/WhatsApp conversion.
        in_app_shop = bool(getattr(settings, "SOCIAL_META_IN_APP_SHOP_ENABLED", False)) and cc == "US"
        return ChannelCapabilities(
            platform=self.platform,
            country_code=cc,
            supports_catalog_feed=True,
            supports_direct_publish=True,
            supports_inbox_api=True,
            supports_in_app_shop=in_app_shop,
            notes=(
                "Türkiye bölgesinde Instagram Shop uygulama içi ödeme varsayılan olarak kapalıdır; "
                "Meta Katalog feed, Reels/Gönderi, DM API ve web ürün bağlantısı aktif modeldir."
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
                error="Meta OAuth token veya external_catalog_id tanımlı değil.",
            )
        if not items:
            return ProviderResult(
                ok=False,
                status="EMPTY_FEED",
                error="Meta kataloğa gönderilecek ürün bulunamadı.",
            )
        batch_requests = [
            {
                "method": "UPDATE",
                "retailer_id": str(item["id"]),
                "data": {
                    "name": str(item.get("title") or "")[:150],
                    "description": str(item.get("description") or item.get("title") or "")[:5000],
                    "availability": item.get("availability", "in stock"),
                    "price": item.get("price", "0.00 TRY"),
                    "url": item.get("link", ""),
                    "image_url": item.get("image_link", ""),
                    "brand": item.get("brand", "TARA DIAMOND"),
                },
            }
            for item in items
        ]
        try:
            resp = requests.post(
                f"{META_GRAPH_BASE}/{external_catalog_id}/batch",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"requests": batch_requests},
                timeout=12,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400:
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(data.get("error", {}).get("message") or f"HTTP_{resp.status_code}"),
                    raw=data,
                )
            return ProviderResult(
                ok=True,
                status="SYNCED",
                external_id=str(data.get("handles", [""])[0] if isinstance(data.get("handles"), list) else ""),
                raw=data,
            )
        except Exception as exc:
            logger.exception("Meta catalog sync failed")
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
        if post_type == "STORY":
            return ProviderResult(
                ok=False,
                status="MANUAL_REQUIRED",
                error="Instagram Hikâye içerikleri için manuel yayınlama akışı kullanılmalıdır.",
            )
        if not access_token or not external_account_id:
            return ProviderResult(
                ok=False,
                status="NOT_CONFIGURED",
                error="Instagram profesyonel hesap OAuth bağlantısı henüz yapılmamış.",
            )
        if not media_urls:
            return ProviderResult(ok=False, status="ERROR", error="Yayın için medya URL zorunludur.")

        try:
            payload: dict[str, Any] = {"caption": caption}
            if post_type == "REELS":
                payload["media_type"] = "REELS"
                payload["video_url"] = media_urls[0]
            else:
                payload["image_url"] = media_urls[0]

            create_resp = requests.post(
                f"{META_GRAPH_BASE}/{external_account_id}/media",
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=12,
            )
            create_data = create_resp.json() if create_resp.content else {}
            if create_resp.status_code >= 400 or not create_data.get("id"):
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(create_data.get("error", {}).get("message") or f"HTTP_{create_resp.status_code}"),
                    raw=create_data,
                )

            pub_resp = requests.post(
                f"{META_GRAPH_BASE}/{external_account_id}/media_publish",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"creation_id": create_data["id"]},
                timeout=12,
            )
            pub_data = pub_resp.json() if pub_resp.content else {}
            if pub_resp.status_code >= 400:
                return ProviderResult(
                    ok=False,
                    status="ERROR",
                    error=str(pub_data.get("error", {}).get("message") or f"HTTP_{pub_resp.status_code}"),
                    raw=pub_data,
                )
            return ProviderResult(
                ok=True,
                status="PUBLISHED",
                external_id=str(pub_data.get("id", "")),
                raw=pub_data,
            )
        except Exception as exc:
            logger.exception("Meta Instagram publish failed")
            return ProviderResult(ok=False, status="ERROR", error=str(exc)[:400])

    def send_message(
        self,
        *,
        access_token: str,
        external_account_id: str,
        recipient_id: str,
        body: str,
    ) -> ProviderResult:
        if not access_token or not external_account_id:
            return ProviderResult(
                ok=False,
                status="NOT_CONFIGURED",
                error="Instagram Messaging API token veya hesap ID tanımlı değil.",
            )
        try:
            resp = requests.post(
                f"{META_GRAPH_BASE}/{external_account_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"recipient": {"id": recipient_id}, "message": {"text": body}},
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
            return ProviderResult(
                ok=True,
                status="PUBLISHED",
                external_id=str(data.get("message_id", "")),
                raw=data,
            )
        except Exception as exc:
            logger.exception("Instagram DM send failed")
            return ProviderResult(ok=False, status="ERROR", error=str(exc)[:400])


class WhatsAppCloudAdapter(SocialProviderAdapter):
    platform = "WHATSAPP"

    def capabilities(self, country_code: str = "TR") -> ChannelCapabilities:
        return ChannelCapabilities(
            platform=self.platform,
            country_code=(country_code or "TR").upper(),
            supports_catalog_feed=True,
            supports_direct_publish=False,
            supports_inbox_api=True,
            supports_in_app_shop=False,
            notes="WhatsApp Business Cloud API ile 24 saat penceresi ve onaylı şablon mesajları desteklenir.",
        )

    def sync_catalog_items(
        self,
        *,
        access_token: str,
        external_catalog_id: str,
        items: list[dict[str, Any]],
    ) -> ProviderResult:
        return MetaInstagramAdapter().sync_catalog_items(
            access_token=access_token,
            external_catalog_id=external_catalog_id,
            items=items,
        )

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
        return ProviderResult(
            ok=False,
            status="MANUAL_REQUIRED",
            error="WhatsApp kanalı akış yayını değil, birebir müşteri mesajlaşması içindir.",
        )

    def send_message(
        self,
        *,
        access_token: str,
        external_account_id: str,
        recipient_id: str,
        body: str,
    ) -> ProviderResult:
        if not access_token or not external_account_id:
            return ProviderResult(
                ok=False,
                status="NOT_CONFIGURED",
                error="WhatsApp Cloud API access token veya phone_number_id eksik.",
            )
        try:
            resp = requests.post(
                f"{META_GRAPH_BASE}/{external_account_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient_id,
                    "type": "text",
                    "text": {"body": body},
                },
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
            msg_id = ""
            msgs = data.get("messages")
            if isinstance(msgs, list) and msgs:
                msg_id = str(msgs[0].get("id", ""))
            return ProviderResult(ok=True, status="PUBLISHED", external_id=msg_id, raw=data)
        except Exception as exc:
            logger.exception("WhatsApp Cloud send failed")
            return ProviderResult(ok=False, status="ERROR", error=str(exc)[:400])

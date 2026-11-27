from __future__ import annotations

from typing import Any

from apps.messaging.whatsapp_client import send_whatsapp_template, send_whatsapp_text

from .base import ChannelCapabilities, ProviderResult, SocialProviderAdapter


class WhatsAppCloudAdapter(SocialProviderAdapter):
    """SocialProviderAdapter bridge delegating WhatsApp Cloud transport to apps.messaging."""

    platform = "WHATSAPP"

    def capabilities(self, country_code: str = "TR") -> ChannelCapabilities:
        return ChannelCapabilities(
            platform=self.platform,
            country_code=(country_code or "TR").upper(),
            supports_catalog_feed=True,
            supports_direct_publish=False,
            supports_inbox_api=True,
            supports_in_app_shop=False,
            notes="WhatsApp Business Cloud API: 24 saat penceresi, onaylı şablon mesajları ve teslimat durumları desteklenir.",
        )

    def sync_catalog_items(
        self,
        *,
        access_token: str,
        external_catalog_id: str,
        items: list[dict[str, Any]],
    ) -> ProviderResult:
        from .meta import MetaInstagramAdapter

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
        res = send_whatsapp_text(
            access_token=access_token,
            phone_number_id=external_account_id,
            recipient_id=recipient_id,
            body=body,
        )
        return ProviderResult(
            ok=res.ok,
            status=res.status,
            external_id=res.external_id,
            error=res.error,
            raw=res.raw,
        )

    def send_template(
        self,
        *,
        access_token: str,
        external_account_id: str,
        recipient_id: str,
        template_name: str,
        language_code: str = "tr",
        components: list[dict[str, Any]] | None = None,
    ) -> ProviderResult:
        """Send an approved WhatsApp Business template message (valid outside 24h window)."""
        res = send_whatsapp_template(
            access_token=access_token,
            phone_number_id=external_account_id,
            recipient_id=recipient_id,
            template_name=template_name,
            language_code=language_code,
            components=components,
        )
        return ProviderResult(
            ok=res.ok,
            status=res.status,
            external_id=res.external_id,
            error=res.error,
            raw=res.raw,
        )

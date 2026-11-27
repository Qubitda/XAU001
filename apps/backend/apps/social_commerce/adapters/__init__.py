from .base import ChannelCapabilities, ProviderResult, SocialProviderAdapter, verify_hmac_sha256
from .meta import MetaInstagramAdapter
from .pinterest import PinterestBusinessAdapter
from .tiktok import TikTokBusinessAdapter
from .whatsapp import WhatsAppCloudAdapter

ADAPTER_REGISTRY: dict[str, SocialProviderAdapter] = {
    "INSTAGRAM": MetaInstagramAdapter(),
    "WHATSAPP": WhatsAppCloudAdapter(),
    "TIKTOK": TikTokBusinessAdapter(),
    "PINTEREST": PinterestBusinessAdapter(),
}


def get_adapter(platform: str) -> SocialProviderAdapter:
    adapter = ADAPTER_REGISTRY.get((platform or "").upper())
    if adapter is None:
        raise ValueError(f"Desteklenmeyen sosyal platform: {platform}")
    return adapter


__all__ = [
    "ADAPTER_REGISTRY",
    "ChannelCapabilities",
    "MetaInstagramAdapter",
    "PinterestBusinessAdapter",
    "ProviderResult",
    "SocialProviderAdapter",
    "TikTokBusinessAdapter",
    "WhatsAppCloudAdapter",
    "get_adapter",
    "verify_hmac_sha256",
]

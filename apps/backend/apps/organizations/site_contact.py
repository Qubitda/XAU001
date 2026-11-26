"""Platform public contact settings (storefront footer / OPS CMS)."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .models import SiteContactSettings

SINGLETON_KEY = "platform"


def serialize_site_contact(row: SiteContactSettings) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "companyName": row.company_name,
        "tagline": row.tagline,
        "addressLine": row.address_line,
        "phone": row.phone,
        "email": row.email,
        "workingHours": row.working_hours,
        "whatsapp": row.whatsapp,
        "instagramUrl": row.instagram_url,
        "youtubeUrl": row.youtube_url,
        "tiktokUrl": row.tiktok_url,
        "pinterestUrl": row.pinterest_url,
        "mapUrl": row.map_url,
        "updatedAt": row.updated_at.isoformat(),
    }


def get_or_create_site_contact() -> SiteContactSettings:
    row, _ = SiteContactSettings.objects.get_or_create(singleton_key=SINGLETON_KEY)
    return row


@transaction.atomic
def update_site_contact(data: dict[str, Any]) -> SiteContactSettings:
    row = get_or_create_site_contact()
    field_map = {
        "companyName": "company_name",
        "tagline": "tagline",
        "addressLine": "address_line",
        "phone": "phone",
        "email": "email",
        "workingHours": "working_hours",
        "whatsapp": "whatsapp",
        "instagramUrl": "instagram_url",
        "youtubeUrl": "youtube_url",
        "tiktokUrl": "tiktok_url",
        "pinterestUrl": "pinterest_url",
        "mapUrl": "map_url",
    }
    for api_key, model_field in field_map.items():
        if api_key in data:
            setattr(row, model_field, (data.get(api_key) or "").strip())
    row.save()
    return row

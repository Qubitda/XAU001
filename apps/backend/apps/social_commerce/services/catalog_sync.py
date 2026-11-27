from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_audit
from apps.catalog.models import ProductMedia, ProductModel
from apps.organizations.models import Organization
from apps.pricing.services import create_live_quote

from ..adapters import get_adapter
from ..models import SocialCatalog, SocialProductMapping
from .oauth import SocialCommerceError, decrypt_connection_token

logger = logging.getLogger(__name__)

FORBIDDEN_SOCIAL_FIELDS = frozenset(
    {
        "fireRatePct",
        "ownerOrganizationId",
        "erpCode",
        "stockQty",
        "supplierName",
        "warehouseLocation",
        "unitWholesaleUsd",
        "unitWholesaleTry",
        "cost",
        "margin",
    }
)

CATALOG_SYNC_BATCH_SIZE = 50
CATALOG_SYNC_LOCK_TTL = 300


def _storefront_base_url() -> str:
    return (getattr(settings, "FRONTEND_STOREFRONT_URL", "") or "https://taradiamond.com.tr").rstrip("/")


def _gallery_urls(product: ProductModel) -> list[str]:
    gallery_roles = {
        ProductMedia.MediaRole.GALLERY_MAIN,
        ProductMedia.MediaRole.ON_HAND,
        ProductMedia.MediaRole.MACRO,
    }
    return [
        m.url
        for m in product.media_items.filter(role__in=gallery_roles).order_by("sort_order")
    ]


def _effective_stock_status(product: ProductModel) -> str:
    if product.stock_qty <= 0 and product.stock_status != ProductModel.StockStatus.MADE_TO_ORDER:
        return ProductModel.StockStatus.OUT_OF_STOCK
    return product.stock_status


def build_social_b2c_product_dto(product: ProductModel) -> dict[str, Any]:
    """
    Blind-pool-safe B2C social product DTO using central B2C pricing engine.
    Enforces owner_organization is None so B2B dealer products never leak to B2C.
    """
    if product.owner_organization_id is not None:
        raise SocialCommerceError("Bayiye özel ürün B2C sosyal kataloğa açılamaz.", status_code=403)

    effective_status = _effective_stock_status(product)
    quote, _ = create_live_quote(product=product, channel="B2C")
    availability = (
        "in stock"
        if effective_status in (ProductModel.StockStatus.IN_STOCK, ProductModel.StockStatus.MADE_TO_ORDER)
        else "out of stock"
    )
    gallery = _gallery_urls(product)
    return {
        "id": product.parent_sku,
        "title": product.title,
        "description": product.description,
        "availability": availability,
        "stockStatus": effective_status,
        "price": f"{quote.final_price_try:.2f} TRY",
        "priceTry": str(quote.final_price_try),
        "link": f"{_storefront_base_url()}/urun/{product.parent_sku}",
        "image_link": gallery[0] if gallery else "",
        "additional_image_link": gallery[1:5],
        "brand": "TARA DIAMOND",
        "category": product.category,
        "metal": f"{product.purity_code} {product.metal_color}".strip(),
        "stoneType": product.stone_type,
        "certificateAgency": product.certificate_agency,
    }


def build_b2b_social_product_dto(product: ProductModel, organization: Organization) -> dict[str, Any]:
    """
    B2B dealer-isolated product DTO using central B2B pricing & organization rules.
    Never exposes OPS cost, fire, wastage, supplier, warehouse, or other dealers' products.
    """
    if product.owner_organization_id not in (None, organization.id):
        raise SocialCommerceError("Bu ürün aktif bayi organizasyonuna ait değil.", status_code=403)

    effective_status = _effective_stock_status(product)
    quote, _ = create_live_quote(product=product, channel="B2B", organization=organization)
    gallery = _gallery_urls(product)
    return {
        "id": product.parent_sku,
        "title": product.title,
        "description": product.description,
        "stockStatus": effective_status,
        "b2bPriceTry": str(quote.final_price_try),
        "link": f"{_storefront_base_url()}/urun/{product.parent_sku}",
        "image_link": gallery[0] if gallery else "",
        "additional_image_link": gallery[1:5],
        "category": product.category,
        "metal": f"{product.purity_code} {product.metal_color}".strip(),
        "stoneType": product.stone_type,
        "certificateAgency": product.certificate_agency,
        "b2bShareReady": True,
    }


def build_b2b_social_catalog_items(*, organization: Organization) -> list[dict[str, Any]]:
    """
    B2B dealer-isolated catalog query: strictly scoped to platform + active dealer's organization
    and priced via B2B pricing engine.
    """
    qs = (
        ProductModel.objects.filter(catalog_status=ProductModel.CatalogStatus.ACTIVE)
        .filter(Q(owner_organization__isnull=True) | Q(owner_organization=organization))
        .order_by("parent_sku")
    )
    items: list[dict[str, Any]] = []
    for p in qs.iterator(chunk_size=CATALOG_SYNC_BATCH_SIZE):
        if "B2B" not in (p.sales_channels or []):
            continue
        try:
            items.append(build_b2b_social_product_dto(p, organization))
        except Exception:
            continue
    return items


def generate_catalog_feed_items(
    catalog: SocialCatalog,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Paginated feed generation strictly scoped by SocialCatalog.audience (B2C vs B2B)."""
    if catalog.audience == "B2B":
        org = catalog.channel.organization
        if org is None:
            raise SocialCommerceError(
                "B2B katalog için kanal organizasyonu zorunludur.",
                code="ORG_REQUIRED",
                status_code=400,
            )
        qs = (
            ProductModel.objects.filter(catalog_status=ProductModel.CatalogStatus.ACTIVE)
            .filter(Q(owner_organization__isnull=True) | Q(owner_organization=org))
            .order_by("parent_sku")[offset : offset + limit]
        )
        items: list[dict[str, Any]] = []
        for p in qs:
            if "B2B" not in (p.sales_channels or []):
                continue
            try:
                items.append(build_b2b_social_product_dto(p, org))
            except Exception:
                continue
        return items

    qs = (
        ProductModel.objects.filter(
            catalog_status=ProductModel.CatalogStatus.ACTIVE,
            owner_organization__isnull=True,
        )
        .order_by("parent_sku")[offset : offset + limit]
    )
    items = []
    for p in qs:
        if "B2C_API" not in (p.sales_channels or []):
            continue
        try:
            items.append(build_social_b2c_product_dto(p))
        except Exception:
            continue
    return items


def sync_social_catalog(catalog: SocialCatalog, *, actor=None) -> dict[str, Any]:
    """
    Scalable, lock-protected catalog sync:
    - Respects SocialCatalog.audience (B2C vs B2B organization-isolated).
    - Never marks an empty product list as SYNCED.
    - Cache lock prevents concurrent syncs of the same catalog.
    - External provider HTTP call runs OUTSIDE any database transaction.
    """
    is_b2b = catalog.audience == "B2B"
    org = catalog.channel.organization if is_b2b else None
    if is_b2b and org is None:
        raise SocialCommerceError(
            "B2B katalog senkronizasyonu için kanal organizasyonu zorunludur.",
            code="ORG_REQUIRED",
            status_code=400,
        )

    lock_key = f"soc_cat_sync_lock:{catalog.id}"
    if not cache.add(lock_key, "1", timeout=CATALOG_SYNC_LOCK_TTL):
        raise SocialCommerceError(
            "Bu katalog için senkronizasyon zaten çalışıyor.",
            code="SYNC_IN_PROGRESS",
            status_code=409,
        )

    try:
        adapter = get_adapter(catalog.channel.platform)
        conn = getattr(catalog.channel, "connection", None)
        token = decrypt_connection_token(conn)

        catalog.sync_status = SocialCatalog.SyncStatus.SYNCING
        catalog.save(update_fields=["sync_status", "updated_at"])

        if is_b2b:
            qs = (
                ProductModel.objects.filter(catalog_status=ProductModel.CatalogStatus.ACTIVE)
                .filter(Q(owner_organization__isnull=True) | Q(owner_organization=org))
                .order_by("parent_sku")
            )
            channel_flag = "B2B"
        else:
            qs = ProductModel.objects.filter(
                catalog_status=ProductModel.CatalogStatus.ACTIVE,
                owner_organization__isnull=True,
            ).order_by("parent_sku")
            channel_flag = "B2C_API"

        batch_items: list[dict[str, Any]] = []
        batch_mappings: list[SocialProductMapping] = []
        total_items = 0
        error_count = 0
        provider_status = "IDLE"
        provider_err = ""
        now = timezone.now()

        def _flush_batch() -> None:
            nonlocal provider_status, provider_err
            if not batch_items:
                return
            result = adapter.sync_catalog_items(
                access_token=token,
                external_catalog_id=catalog.external_catalog_id,
                items=batch_items,
            )
            provider_status = result.status
            if not result.ok:
                provider_err = result.error
                if provider_status not in ("NOT_CONFIGURED", "MANUAL_REQUIRED"):
                    SocialProductMapping.objects.filter(
                        id__in=[m.id for m in batch_mappings]
                    ).update(
                        sync_status=SocialProductMapping.SyncStatus.ERROR,
                        rejection_reason=(provider_err or "")[:400],
                        last_synced_at=now,
                    )
            else:
                SocialProductMapping.objects.filter(
                    id__in=[m.id for m in batch_mappings],
                    sync_status=SocialProductMapping.SyncStatus.PENDING,
                ).update(
                    sync_status=SocialProductMapping.SyncStatus.SYNCED,
                    last_synced_at=now,
                )
            batch_items.clear()
            batch_mappings.clear()

        for p in qs.iterator(chunk_size=CATALOG_SYNC_BATCH_SIZE):
            if channel_flag not in (p.sales_channels or []):
                continue
            mapping, _ = SocialProductMapping.objects.get_or_create(catalog=catalog, product=p)
            try:
                if is_b2b:
                    assert org is not None
                    dto = build_b2b_social_product_dto(p, org)
                    price_val = Decimal(dto["b2bPriceTry"])
                    is_available = dto["stockStatus"] in (
                        ProductModel.StockStatus.IN_STOCK,
                        ProductModel.StockStatus.MADE_TO_ORDER,
                    )
                else:
                    dto = build_social_b2c_product_dto(p)
                    price_val = Decimal(dto["priceTry"])
                    is_available = dto["availability"] == "in stock"

                mapping.last_synced_price_try = price_val
                mapping.last_synced_stock_qty = p.stock_qty
                mapping.last_synced_at = now
                mapping.rejection_reason = ""
                mapping.sync_status = (
                    SocialProductMapping.SyncStatus.UNPUBLISHED
                    if not is_available
                    else SocialProductMapping.SyncStatus.PENDING
                )
                mapping.save()

                total_items += 1
                batch_items.append(dto)
                batch_mappings.append(mapping)
                if len(batch_items) >= CATALOG_SYNC_BATCH_SIZE:
                    _flush_batch()
                    if provider_err:
                        break
            except Exception as exc:
                error_count += 1
                mapping.sync_status = SocialProductMapping.SyncStatus.ERROR
                mapping.rejection_reason = str(exc)[:400]
                mapping.last_synced_at = now
                mapping.save()

        if batch_items and not provider_err:
            _flush_batch()

        # Empty feed must NEVER be marked SYNCED
        if total_items == 0 and error_count == 0:
            catalog.sync_status = SocialCatalog.SyncStatus.IDLE
            catalog.last_synced_at = now
            catalog.last_error = "Senkronize edilecek uygun ürün bulunamadı."
            catalog.save(update_fields=["sync_status", "last_synced_at", "last_error", "updated_at"])
            return {
                "catalogId": str(catalog.id),
                "audience": catalog.audience,
                "itemCount": 0,
                "errorCount": 0,
                "syncStatus": catalog.sync_status,
                "providerStatus": "EMPTY_FEED",
                "message": catalog.last_error,
            }

        catalog.last_synced_at = now
        if provider_err and provider_status not in ("NOT_CONFIGURED", "MANUAL_REQUIRED"):
            catalog.sync_status = SocialCatalog.SyncStatus.FAILED
            catalog.last_error = provider_err
        elif error_count > 0:
            catalog.sync_status = SocialCatalog.SyncStatus.PARTIAL
            catalog.last_error = provider_err or f"{error_count} ürün senkronizasyonda hata aldı."
        elif provider_status in ("NOT_CONFIGURED", "MANUAL_REQUIRED"):
            catalog.sync_status = SocialCatalog.SyncStatus.IDLE
            catalog.last_error = provider_err
        else:
            catalog.sync_status = SocialCatalog.SyncStatus.SYNCED
            catalog.last_error = ""

        catalog.save(update_fields=["sync_status", "last_synced_at", "last_error", "updated_at"])
        record_audit(
            actor=actor,
            action="social.catalog.synced",
            entity_type="SocialCatalog",
            entity_id=str(catalog.id),
            metadata={
                "audience": catalog.audience,
                "itemCount": total_items,
                "errorCount": error_count,
                "providerStatus": provider_status,
            },
        )
        return {
            "catalogId": str(catalog.id),
            "audience": catalog.audience,
            "itemCount": total_items,
            "errorCount": error_count,
            "syncStatus": catalog.sync_status,
            "providerStatus": provider_status,
            "message": catalog.last_error or "Katalog senkronizasyonu tamamlandı.",
        }
    finally:
        cache.delete(lock_key)

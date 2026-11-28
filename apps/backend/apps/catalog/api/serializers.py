"""Blind-pool and OPS product serialization + list query helpers."""
from decimal import Decimal

from django.db.models import Prefetch, Q
from rest_framework.request import Request

from apps.pricing.models import CostLine, PricingRecipe
from apps.pricing.services import evaluate_recipe
from apps.catalog.models import ProductMedia, ProductModel, SupplierOffer
from apps.catalog.product_details import serialize_product_details
from .common import (
    CARAT_Q,
    DIM_Q,
    FINENESS_Q,
    GRAM_Q,
    MONEY_Q,
    _dec_str,
    _safe_detail,
    _serialize_mount,
    _serialize_variants,
    _stone_summary,
)

def _catalog_card_fields(
    product: ProductModel,
    center_carat: Decimal,
    side_carat: Decimal,
    stone_lines: list[dict],
    *,
    for_ops: bool = False,
) -> dict:
    """
    Shared catalog identity fields safe for all audiences when for_ops=False.
    Never put ownerOrganizationId / erpCode / stockQty / salesChannels / cost details here for buyers.
    """
    active_variants = [v for v in product.variants.all() if v.is_active]
    media_items = list(product.media_items.all())
    gallery_roles = {
        ProductMedia.MediaRole.GALLERY_MAIN,
        ProductMedia.MediaRole.GALLERY,
        ProductMedia.MediaRole.ON_HAND,
        ProductMedia.MediaRole.MACRO,
        ProductMedia.MediaRole.DETAIL,
    }
    sorted_media = sorted(media_items, key=lambda x: x.sort_order)
    gallery_urls = [m.url for m in sorted_media if m.role in gallery_roles]
    serialized_media = [
        {
            "id": str(m.id),
            "metalColor": m.metal_color,
            "role": m.role,
            "url": m.url,
            "sortOrder": m.sort_order,
        }
        for m in sorted_media
    ]
    reels_url = next((m.url for m in media_items if m.role == ProductMedia.MediaRole.VIDEO_REELS), "")
    spin_url = next((m.url for m in media_items if m.role == ProductMedia.MediaRole.SPIN_360), "")
    catalog_clean_url = next((m.url for m in media_items if m.role == ProductMedia.MediaRole.CATALOG_CLEAN), "")
    cert_url = next((m.url for m in media_items if m.role == ProductMedia.MediaRole.CERTIFICATE_PDF), "")
    effective_stock_status = (
        ProductModel.StockStatus.OUT_OF_STOCK
        if product.stock_qty <= 0 and product.stock_status != ProductModel.StockStatus.MADE_TO_ORDER
        else product.stock_status
    )
    finished = _safe_detail(product, "finished_detail")
    mounting = _safe_detail(product, "mounting_detail")
    loose = _safe_detail(product, "loose_stone_detail")
    metal_detail = finished or mounting

    metal_name = (metal_detail.metal_name if metal_detail else "") or product.metal_name
    purity_code = (metal_detail.purity_code if metal_detail else "") or product.purity_code
    metal_color = (metal_detail.metal_color if metal_detail else "") or product.metal_color
    stone_type = (loose.stone_category if loose else "") or product.stone_type
    stone_clarity = (loose.clarity if loose else "") or product.stone_clarity
    stone_color_grade = (loose.color if loose else "") or product.stone_color_grade
    stone_cut_grade = (loose.cut_grade if loose else "") or product.stone_cut_grade
    stone_cut_shape = (loose.shape if loose else "") or product.stone_cut_shape
    setting_type = (mounting.setting_type_code if mounting else "") or product.setting_type
    cert_agency = (loose.cert_lab if loose else "") or product.certificate_agency
    cert_number = (loose.cert_number if loose else "") or product.certificate_number

    data = {
        "parentSku": product.parent_sku,
        "barcode": product.barcode,
        "visualType": product.visual_type,
        "title": product.title,
        "description": product.description,
        "productType": product.product_type,
        **serialize_product_details(product, for_ops=for_ops),
        "collection": product.collection,
        "category": product.category,
        "subCategory": product.sub_category,
        "styleTechnique": product.style_technique,
        "occasion": product.occasion,
        "ageGroup": product.age_group,
        "metalName": metal_name,
        "purityCode": purity_code,
        "metalColor": metal_color,
        "availableColors": product.available_colors or ([metal_color] if metal_color else []),
        "grossWeightGram": _dec_str(product.gross_weight_gram, GRAM_Q),
        "stockStatus": effective_stock_status,
        "leadTimeDays": product.lead_time_days,
        "stoneType": stone_type,
        "stoneMeasureUnit": product.stone_measure_unit,
        "centerStoneCarat": _dec_str(center_carat, CARAT_Q),
        "sideStoneCarat": _dec_str(side_carat, CARAT_Q),
        "stoneCount": sum(s["count"] for s in stone_lines),
        "stoneClarity": stone_clarity,
        "stoneColorGrade": stone_color_grade,
        "stoneCutGrade": stone_cut_grade,
        "stoneCutShape": stone_cut_shape,
        "stoneOrigin": product.stone_origin,
        "settingType": setting_type,
        "hasCertificate": bool(cert_agency and (cert_number or cert_url)),
        "certificateAgency": cert_agency,
        "certificateNumber": cert_number,
        "certificateFileUrl": cert_url,
        "mountSpec": _serialize_mount(product),
        "stoneLines": stone_lines,
        "variantSize": product.variant_size,
        "availableSizes": product.available_sizes or [],
        "variantCount": len(active_variants) or max(1, len(product.available_sizes or []) * max(1, len(product.available_colors or []))),
        "widthMm": _dec_str(product.width_mm, DIM_Q),
        "thicknessMm": _dec_str(product.thickness_mm, DIM_Q),
        "heightMm": _dec_str(product.height_mm, DIM_Q),
        "chainType": product.chain_type,
        "claspType": product.clasp_type,
        "isResizable": product.is_resizable,
        "galleryImages": gallery_urls,
        "mediaItems": serialized_media,
        "reelsVideoUrl": reels_url,
        "spin360Url": spin_url,
        "catalogCleanImageUrl": catalog_clean_url,
        "b2bSharePermission": product.b2b_share_permission or "ALLOWED",
        "dynamicDealerWatermark": product.dynamic_dealer_watermark,
        "socialShareCaption": product.social_share_caption,
        "warrantyMonths": product.warranty_months,
        "lifetimeMaintenance": product.lifetime_maintenance,
        "insuredShippingInfo": product.insured_shipping_info,
        "returnPolicyText": product.return_policy_text,
        "seoSlug": product.seo_slug,
        "metaTitle": product.meta_title or product.title,
        "metaDescription": product.meta_description,
        "marketplaceCategory": product.marketplace_category,
        "sizeGuideUrl": product.size_guide_url,
        "ogImage": product.og_image,
        "canonicalUrl": product.canonical_url,
        "robots": product.robots or "index,follow",
        "keywords": product.keywords,
        "inStock": product.stock_qty > 0 or product.stock_status == ProductModel.StockStatus.MADE_TO_ORDER,
        "catalogStatus": product.catalog_status,
    }
    if for_ops:
        data.update(
            {
                "ownerOrganizationId": str(product.owner_organization_id) if product.owner_organization_id else None,
                "erpCode": product.erp_code,
                "stockQty": product.stock_qty,
                # Empty list = not published to any buyer sales channel
                "salesChannels": product.sales_channels if product.sales_channels is not None else [],
            }
        )
    return data


def _serialize_buyer_offers(product: ProductModel) -> list[dict]:
    """Blind-pool anonymous offer cards for buyers (zero supplier identity/cost/exact qty)."""
    prefetched = getattr(product, "approved_supplier_offers", None)
    if prefetched is not None:
        offers = prefetched
    else:
        offers = product.supplier_offers.filter(
            status=SupplierOffer.Status.APPROVED,
            is_active=True,
            available_qty__gt=0,
        )
    return [
        {
            "offerRef": str(o.offer_ref),
            "leadTimeDays": o.lead_time_days,
            "inStock": o.available_qty > 0,
            "variantId": str(o.variant_id) if o.variant_id else None,
        }
        for o in offers
    ]


def serialize_storefront_product(product: ProductModel, recipe: PricingRecipe | None, rates) -> dict:
    """
    StorefrontProductSerializer contract (B2C blind-pool).
    Public catalog + final retail prices only — no owner/ERP/stock qty/sales channels/costs/fire.
    """
    center_carat, side_carat, stone_lines = _stone_summary(product)
    data = _catalog_card_fields(product, center_carat, side_carat, stone_lines, for_ops=False)
    variant_outputs: dict = {}
    variants = _serialize_variants(product, recipe, rates, audience="b2c", variant_outputs=variant_outputs)
    default_v = next((v for v in product.variants.all() if v.is_active and v.is_default), None)
    if default_v is not None and default_v.id in variant_outputs:
        out = variant_outputs[default_v.id]
    else:
        out = evaluate_recipe(recipe, rates, variant=default_v) if recipe is not None else None
    b2c_ch = out.resolve_channel("B2C") if out else None

    data["variants"] = variants
    data["b2cPricing"] = {
        "snapshotId": rates.snapshot_code,
        "listPriceTry": _dec_str(b2c_ch.liste_fiyati_try, MONEY_Q) if b2c_ch else None,
        "finalPriceTry": _dec_str(b2c_ch.nihai_fiyat_try, MONEY_Q) if b2c_ch else None,
        "effectiveDiscountPct": _dec_str(b2c_ch.effective_discount_pct, DIM_Q) if b2c_ch else "0.00",
    }
    # Display metal physics only — never fire-included / cost equivalents.
    data["metalSummary"] = {
        "netMetalGram": _dec_str(out.net_metal_gram, GRAM_Q) if out else _dec_str(product.gross_weight_gram, GRAM_Q),
        "fineMetalGram": _dec_str(out.fine_metal_gram, GRAM_Q) if out else "0.0000",
        "fineness": _dec_str(out.fineness, FINENESS_Q) if out else "0.585",
    }
    data["offers"] = _serialize_buyer_offers(product)
    return data


def serialize_b2b_product(product: ProductModel, recipe: PricingRecipe | None, rates) -> dict:
    """
    B2bProductSerializer contract (dealer blind-pool).
    Wholesale channel prices only — ZERO cost/fire/labor breakdown, owner, ERP, stock qty, salesChannels.
    """
    center_carat, side_carat, stone_lines = _stone_summary(product)
    data = _catalog_card_fields(product, center_carat, side_carat, stone_lines, for_ops=False)
    variant_outputs: dict = {}
    variants = _serialize_variants(product, recipe, rates, audience="b2b", variant_outputs=variant_outputs)
    default_v = next((v for v in product.variants.all() if v.is_active and v.is_default), None)
    if default_v is not None and default_v.id in variant_outputs:
        out = variant_outputs[default_v.id]
    else:
        out = evaluate_recipe(recipe, rates, variant=default_v) if recipe is not None else None
    b2b_ch = out.resolve_channel("B2B") if out else None

    data["variants"] = variants
    data["b2bPricing"] = {
        "snapshotId": rates.snapshot_code,
        "lcCurrency": out.lc_currency if out else "TRY",
        "finalPriceLc": _dec_str(b2b_ch.nihai_fiyat_lc, MONEY_Q) if b2b_ch else None,
        "finalPriceTry": _dec_str(b2b_ch.nihai_fiyat_try, MONEY_Q) if b2b_ch else None,
    }
    data["metalSummary"] = {
        "netMetalGram": _dec_str(out.net_metal_gram, GRAM_Q) if out else _dec_str(product.gross_weight_gram, GRAM_Q),
        "fineMetalGram": _dec_str(out.fine_metal_gram, GRAM_Q) if out else "0.0000",
        "fineness": _dec_str(out.fineness, FINENESS_Q) if out else "0.585",
    }
    data["offers"] = _serialize_buyer_offers(product)
    return data


def serialize_ops_product(product: ProductModel, recipe: PricingRecipe | None, rates) -> dict:
    """
    OpsProductSerializer (requires catalog:write / pricing:read).
    Full ledger, costs, fire, supplier, warehouse, exact stock qty, channel rules.
    """
    center_carat, side_carat, stone_lines = _stone_summary(product)
    data = _catalog_card_fields(product, center_carat, side_carat, stone_lines, for_ops=True)
    variant_outputs: dict = {}
    ops_variants = _serialize_variants(product, recipe, rates, audience="ops", variant_outputs=variant_outputs)
    default_v = next((v for v in product.variants.all() if v.is_active and v.is_default), None)
    if default_v is not None and default_v.id in variant_outputs:
        out = variant_outputs[default_v.id]
    else:
        out = evaluate_recipe(recipe, rates, variant=default_v) if recipe is not None else None
    data.update(
        {
            "supplierName": product.supplier_name,
            "warehouseLocation": product.warehouse_location,
            "ownershipType": product.ownership_type,
            "fireRatePct": _dec_str(product.fire_rate_pct, DIM_Q),
            "pricingMode": recipe.pricing_mode if recipe else "1",
            "pricingCurrency": recipe.lc_currency if recipe else "TRY",
            "recipeId": str(recipe.id) if recipe else None,
            "variants": ops_variants,
            "metalSummary": {
                "netMetalGram": _dec_str(out.net_metal_gram, GRAM_Q) if out else _dec_str(product.gross_weight_gram, GRAM_Q),
                "fineMetalGram": _dec_str(out.fine_metal_gram, GRAM_Q) if out else "0.0000",
                "fireIncludedFineMetalGram": _dec_str(out.fire_included_fine_metal_gram, GRAM_Q) if out else "0.0000",
                "fineness": _dec_str(out.fineness, FINENESS_Q) if out else "0.585",
            },
        }
    )
    if out is not None and out.pure_gold_equivalent is not None:
        data["pricingBreakdown"] = {
            "productKind": out.product_kind,
            "pureGoldEquivalent": _dec_str(out.pure_gold_equivalent, GRAM_Q),
            "laborOnlyUsd": _dec_str(out.labor_only_usd or Decimal("0"), MONEY_Q),
        }

    if recipe is not None:
        lines_by_type = {cl.line_type: cl for cl in recipe.cost_lines.all()}

        def _cl(lt: str, default_cur: str = "USD"):
            return lines_by_type.get(lt) or CostLine(line_type=lt, fc_currency=default_cur)

        maden = _cl(CostLine.LineType.MADEN, "USD")
        iscilik = _cl(CostLine.LineType.ISCILIK, "EUR")
        tas = _cl(CostLine.LineType.TAS, "USD")
        montur = _cl(CostLine.LineType.MONTUR, "USD")
        diger = _cl(CostLine.LineType.DIGER, "TRY")
        tedarikci = _cl(CostLine.LineType.TEDARIKCI, "USD")

        data["ledger"] = {
            "lcCurrency": recipe.lc_currency,
            "metalCurrency": maden.fc_currency,
            "metalFcManual": _dec_str(maden.fc_price_manual, GRAM_Q),
            "metalRateOverride": _dec_str(maden.rate_override, GRAM_Q),
            "laborCurrency": iscilik.fc_currency,
            "laborFcPrice": _dec_str(iscilik.fc_price, GRAM_Q),
            "laborUnitFee": _dec_str(iscilik.fc_price, GRAM_Q),
            "laborGramOverride": None,
            "laborRateOverride": _dec_str(iscilik.rate_override, GRAM_Q),
            "stoneCurrency": tas.fc_currency,
            "stoneFcPrice": _dec_str(tas.fc_price, GRAM_Q),
            "stoneRateOverride": _dec_str(tas.rate_override, GRAM_Q),
            "mountingCurrency": montur.fc_currency,
            "mountingFcPrice": _dec_str(montur.fc_price, GRAM_Q),
            "mountingRateOverride": _dec_str(montur.rate_override, GRAM_Q),
            "otherCostCurrency": diger.fc_currency,
            "otherCostFcPrice": _dec_str(diger.fc_price, GRAM_Q),
            "otherCostRateOverride": _dec_str(diger.rate_override, GRAM_Q),
            "supplierCurrency": tedarikci.fc_currency,
            "supplierFcPrice": _dec_str(tedarikci.fc_price, GRAM_Q),
            "supplierRateOverride": _dec_str(tedarikci.rate_override, GRAM_Q),
            "channelRules": [
                {
                    "id": str(cr.id),
                    "channel": cr.channel,
                    "profit": {"unit": cr.profit_unit, "value": _dec_str(cr.profit_value, GRAM_Q)},
                    "discount": {"unit": cr.discount_unit, "value": _dec_str(cr.discount_value, GRAM_Q)},
                    "platformFee": {"unit": cr.servis_bedeli_unit, "value": _dec_str(cr.servis_bedeli_value, GRAM_Q)},
                }
                for cr in recipe.channel_rules.all()
            ],
        }
    return data


def _products_queryset():
    return ProductModel.objects.select_related(
        "owner_organization",
        "finished_detail",
        "mounting_detail",
        "loose_stone_detail",
    ).prefetch_related(
        "stone_lines",
        "variants",
        "media_items",
        Prefetch(
            "pricing_recipes",
            queryset=PricingRecipe.objects.filter(status=PricingRecipe.Status.PUBLISHED).prefetch_related(
                "cost_lines", "channel_rules"
            ),
            to_attr="published_recipes",
        ),
        Prefetch(
            "supplier_offers",
            queryset=SupplierOffer.objects.filter(
                status=SupplierOffer.Status.APPROVED,
                is_active=True,
                available_qty__gt=0,
            ),
            to_attr="approved_supplier_offers",
        ),
    )


def _channel_filter(qs, channel: str):
    """Filter products to those explicitly enabled for the given sales channel (Postgres + SQLite safe)."""
    from django.db import connection

    if connection.vendor == "postgresql":
        return qs.filter(sales_channels__contains=[channel])
    return qs.filter(sales_channels__icontains=f'"{channel}"')


def _apply_filters(qs, request: Request):
    category = request.query_params.get("category")
    collection = request.query_params.get("collection")
    purity = request.query_params.get("purity")
    color = request.query_params.get("color")
    q = (request.query_params.get("q") or "").strip()[:64]
    if category:
        qs = qs.filter(category=category)
    if collection:
        qs = qs.filter(collection=collection)
    if purity:
        qs = qs.filter(Q(purity_code=purity) | Q(variants__purity_code=purity)).distinct()
    if color:
        qs = qs.filter(Q(metal_color=color) | Q(variants__metal_color=color)).distinct()
    if len(q) >= 2:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(parent_sku__icontains=q)
            | Q(stone_type__icontains=q)
            | Q(variants__sku__icontains=q)
        ).distinct()
    return qs


"""Catalog API shared helpers (parsing, media sync, kind fields, variant rows)."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps.definitions.sales_channels import SALES_CHANNEL_CODES, normalize_sales_channel
from apps.pricing.models import PricingRecipe
from apps.pricing.services import evaluate_recipe
from config.exceptions import DomainError
from apps.catalog.models import ProductMedia, ProductModel, StoneLine
from apps.catalog.product_kinds import kind_to_product_type_label, normalize_product_kind

MONEY_Q = Decimal("0.01")
GRAM_Q = Decimal("0.0001")
CARAT_Q = Decimal("0.001")
FINENESS_Q = Decimal("0.001")
DIM_Q = Decimal("0.01")


def _detail_overrides_from_payload(d: dict) -> dict | None:
    for key in ("finishedDetail", "mountingDetail", "looseStoneDetail"):
        if isinstance(d.get(key), dict) and d[key]:
            return d[key]
    return None


def _apply_kind_fields(product: ProductModel, d: dict) -> None:
    if d.get("productKind"):
        kind = normalize_product_kind(d["productKind"])
        product.product_kind = kind
        product.product_type = kind_to_product_type_label(kind)
    elif d.get("productType"):
        kind = normalize_product_kind(d["productType"])
        product.product_kind = kind
        product.product_type = kind_to_product_type_label(kind)
    if "erpCode" in d:
        code = (d.get("erpCode") or "").strip() or None
        product.erp_code = code


def _normalize_sales_channels(raw) -> list[str]:
    if not isinstance(raw, list) or not raw:
        return ["B2B", "B2B_API", "B2C_API"]
    out: list[str] = []
    for item in raw:
        code = normalize_sales_channel(str(item))
        if code and code not in out:
            out.append(code)
    if not out:
        raise DomainError(
            "Ürün satış kanalı yalnızca B2B, B2B_API veya B2C_API olabilir.",
            code="INVALID_SALES_CHANNEL",
            status_code=400,
        )
    unknown = [str(i) for i in raw if normalize_sales_channel(str(i)) is None]
    if unknown:
        raise DomainError(
            f"Geçersiz satış kanalı: {', '.join(unknown)}. İzin verilenler: {', '.join(sorted(SALES_CHANNEL_CODES))}.",
            code="INVALID_SALES_CHANNEL",
            status_code=400,
        )
    return out


def _dec_str(val: Decimal | None, q: Decimal) -> str | None:
    if val is None:
        return None
    return str(Decimal(val).quantize(q, rounding=ROUND_HALF_UP))


def _parse_decimal(value, *, field_name: str, default: Decimal | None = None, min_value: Decimal | None = None) -> Decimal:
    if value is None or value == "":
        if default is not None:
            return default
        raise DomainError(f"{field_name} alanı zorunludur.", code="INVALID_NUMBER", status_code=400)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise DomainError(f"{field_name} alanı geçerli bir sayı olmalıdır.", code="INVALID_NUMBER", status_code=400)
    if min_value is not None and parsed < min_value:
        raise DomainError(f"{field_name} alanı en az {min_value} olmalıdır.", code="INVALID_NUMBER", status_code=400)
    return parsed


def _parse_int(value, *, field_name: str, default: int = 1, min_value: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (ValueError, TypeError):
        raise DomainError(f"{field_name} alanı geçerli bir tam sayı olmalıdır.", code="INVALID_NUMBER", status_code=400)
    if parsed < min_value:
        raise DomainError(f"{field_name} alanı en az {min_value} olmalıdır.", code="INVALID_NUMBER", status_code=400)
    return parsed


def _stone_summary(product: ProductModel) -> tuple[Decimal, Decimal, list[dict]]:
    lines = list(product.stone_lines.all())
    center_carat = sum(
        (s.carat * s.count for s in lines if s.role == StoneLine.Role.MERKEZ),
        Decimal("0"),
    )
    side_carat = sum(
        (s.carat * s.count for s in lines if s.role != StoneLine.Role.MERKEZ),
        Decimal("0"),
    )
    serialized = [
        {
            "id": str(s.id),
            "role": s.role,
            "stoneType": s.stone_type,
            "measureUnit": s.measure_unit,
            "count": s.count,
            "carat": _dec_str(s.carat, GRAM_Q),
            "clarity": s.clarity,
            "colorGrade": s.color_grade,
            "cutShape": s.cut_shape,
        }
        for s in lines
    ]
    return center_carat, side_carat, serialized


def _safe_detail(product: ProductModel, attr: str):
    try:
        return getattr(product, attr)
    except Exception:
        return None


def _serialize_mount(product: ProductModel) -> dict:
    mounting = _safe_detail(product, "mounting_detail")
    if mounting is not None:
        return {
            "structure": mounting.mount_structure or product.mount_structure,
            "allowedCaratMin": _dec_str(mounting.min_carat if mounting.min_carat is not None else product.allowed_carat_min, CARAT_Q),
            "allowedCaratMax": _dec_str(mounting.max_carat if mounting.max_carat is not None else product.allowed_carat_max, CARAT_Q),
            "headCode": mounting.head_code or product.head_code,
            "bandCode": mounting.band_code or product.band_code,
            "headWeightGram": _dec_str(mounting.head_weight_gram if mounting.head_weight_gram is not None else product.head_weight_gram, GRAM_Q),
            "bandWeightGram": _dec_str(mounting.band_weight_gram if mounting.band_weight_gram is not None else product.band_weight_gram, GRAM_Q),
        }
    return {
        "structure": product.mount_structure,
        "allowedCaratMin": _dec_str(product.allowed_carat_min, CARAT_Q),
        "allowedCaratMax": _dec_str(product.allowed_carat_max, CARAT_Q),
        "headCode": product.head_code,
        "bandCode": product.band_code,
        "headWeightGram": _dec_str(product.head_weight_gram, GRAM_Q),
        "bandWeightGram": _dec_str(product.band_weight_gram, GRAM_Q),
    }


def _serialize_variants(
    product: ProductModel,
    recipe: PricingRecipe | None,
    rates,
    *,
    audience: str,
    variant_outputs: dict | None = None,
) -> list[dict]:
    variants = [v for v in product.variants.all() if v.is_active]
    payload: list[dict] = []
    for v in variants:
        out = evaluate_recipe(recipe, rates, variant=v) if recipe is not None else None
        if variant_outputs is not None:
            variant_outputs[v.id] = out
        b2c_ch = out.resolve_channel("B2C") if out else None
        b2b_ch = out.resolve_channel("B2B") if out else None

        entry: dict = {
            "id": str(v.id),
            "sku": v.sku,
            "purityCode": v.purity_code,
            "metalColor": v.metal_color,
            "size": v.size,
            "centerStoneCarat": _dec_str(v.center_stone_carat, CARAT_Q),
            "grossWeightGram": _dec_str(v.gross_weight_gram, GRAM_Q),
            "isDefault": v.is_default,
            "isActive": v.is_active,
            "inStock": v.stock_qty > 0,
        }
        # Exact qty is OPS-only; public channels get availability boolean only.
        if audience == "ops":
            entry["stockQty"] = v.stock_qty
        if audience in ("b2c", "ops"):
            entry["b2cPricing"] = {
                "snapshotId": rates.snapshot_code,
                "listPriceTry": _dec_str(b2c_ch.liste_fiyati_try, MONEY_Q) if b2c_ch else None,
                "finalPriceTry": _dec_str(b2c_ch.nihai_fiyat_try, MONEY_Q) if b2c_ch else None,
                "effectiveDiscountPct": _dec_str(b2c_ch.effective_discount_pct, DIM_Q) if b2c_ch else "0.00",
            }
        if audience in ("b2b", "ops"):
            entry["b2bPricing"] = {
                "snapshotId": rates.snapshot_code,
                "lcCurrency": out.lc_currency if out else "TRY",
                "finalPriceLc": _dec_str(b2b_ch.nihai_fiyat_lc, MONEY_Q) if b2b_ch else None,
                "finalPriceTry": _dec_str(b2b_ch.nihai_fiyat_try, MONEY_Q) if b2b_ch else None,
            }
        payload.append(entry)
    return payload


def _sync_product_media(
    product: ProductModel,
    *,
    gallery_images: list[str] | None = None,
    reels_video_url: str | None = None,
    spin_360_url: str | None = None,
    certificate_file_url: str | None = None,
) -> None:
    def _is_http_url(val: str) -> bool:
        cleaned = (val or "").strip()
        if not cleaned:
            return False
        if len(cleaned) > 500 or not cleaned.startswith("https://"):
            raise DomainError(
                "Medya URL'si yalnızca geçerli bir https:// adresi olabilir.",
                code="INVALID_MEDIA_URL",
                status_code=400,
            )
        return True

    if gallery_images is not None:
        ProductMedia.objects.filter(
            product=product,
            role__in=[
                ProductMedia.MediaRole.GALLERY_MAIN,
                ProductMedia.MediaRole.ON_HAND,
                ProductMedia.MediaRole.MACRO,
            ],
        ).delete()
        roles = [
            ProductMedia.MediaRole.GALLERY_MAIN,
            ProductMedia.MediaRole.ON_HAND,
            ProductMedia.MediaRole.MACRO,
        ]
        for idx, raw_url in enumerate(gallery_images, start=1):
            url = (raw_url or "").strip()
            if not _is_http_url(url):
                continue
            role = roles[idx - 1] if idx <= len(roles) else ProductMedia.MediaRole.GALLERY_MAIN
            ProductMedia.objects.create(
                product=product,
                metal_color=product.metal_color,
                role=role,
                url=url,
                sort_order=idx,
            )

    single_role_updates = [
        (reels_video_url, ProductMedia.MediaRole.VIDEO_REELS, 10),
        (spin_360_url, ProductMedia.MediaRole.SPIN_360, 11),
        (certificate_file_url, ProductMedia.MediaRole.CERTIFICATE_PDF, 12),
    ]
    for raw_val, media_role, order_no in single_role_updates:
        if raw_val is None:
            continue
        ProductMedia.objects.filter(product=product, role=media_role).delete()
        cleaned = raw_val.strip()
        if _is_http_url(cleaned):
            ProductMedia.objects.create(
                product=product,
                metal_color=product.metal_color,
                role=media_role,
                url=cleaned,
                sort_order=order_no,
            )


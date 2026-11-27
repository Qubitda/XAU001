"""
Dual-write / read helpers for core ProductModel + type detail tables.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings

from apps.common.responses import CARAT_Q, GRAM_Q, MONEY_Q, dec_str

logger = logging.getLogger(__name__)

from apps.catalog.models import (
    FinishedDetail,
    LooseStoneDetail,
    MountingDetail,
    ProductModel,
)
from apps.catalog.product_kinds import (
    FINISHED,
    LOOSE_STONE,
    MOUNTING,
    kind_to_product_type_label,
    normalize_product_kind,
)
from apps.pricing.engine import PURITY_FINENESS


def dual_write_enabled() -> bool:
    return getattr(settings, "CATALOG_DUAL_WRITE_DETAILS", True)


def pricing_read_from_details() -> bool:
    return getattr(settings, "PRICING_READ_FROM_DETAILS", False)


def resolve_fineness(purity_code: str, fallback: Decimal | None = None) -> Decimal:
    """Prefer DefinitionItem.meta.fineness (ayar_kodu); fall back to engine map."""
    code = (purity_code or "").strip()
    try:
        from apps.definitions.services import find_item_by_label_or_code

        item = find_item_by_label_or_code("ayar_kodu", code)
        if item is not None:
            raw = (item.meta or {}).get("fineness")
            if raw is not None:
                return Decimal(str(raw))
    except (LookupError, ValueError, TypeError, ArithmeticError) as exc:
        logger.warning("resolve_fineness failed for %r: %s", purity_code, exc)
    if code in PURITY_FINENESS:
        return PURITY_FINENESS[code]
    return fallback if fallback is not None else Decimal("0.5850")


def _d(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def sync_kind_and_label(product: ProductModel, *, kind: str | None = None, product_type: str | None = None) -> str:
    """Keep product_kind and legacy product_type in sync. Returns canonical kind."""
    if kind:
        resolved = normalize_product_kind(kind)
    elif product_type:
        resolved = normalize_product_kind(product_type)
    else:
        resolved = normalize_product_kind(product.product_kind or product.product_type)
    product.product_kind = resolved
    product.product_type = kind_to_product_type_label(resolved)
    if resolved == LOOSE_STONE and product.stock_qty > 1:
        product.stock_qty = 1
    return resolved


def _stone_summary_from_product(product: ProductModel) -> dict:
    lines = []
    for line in product.stone_lines.all():
        lines.append(
            {
                "role": line.role,
                "stoneType": line.stone_type,
                "count": line.count,
                "carat": str(line.carat),
                "clarity": line.clarity,
                "colorGrade": line.color_grade,
                "cutShape": line.cut_shape,
            }
        )
    return {
        "header": {
            "stoneType": product.stone_type,
            "clarity": product.stone_clarity,
            "colorGrade": product.stone_color_grade,
            "cutGrade": product.stone_cut_grade,
            "cutShape": product.stone_cut_shape,
            "origin": product.stone_origin,
        },
        "lines": lines,
    }


def _labor_from_recipe(product: ProductModel) -> tuple[str, Decimal]:
    recipe = product.pricing_recipes.order_by("-updated_at").first()
    if not recipe:
        return ProductModel.LaborCostType.FIXED, Decimal("0")
    labor = recipe.cost_lines.filter(line_type="ISCILIK").first()
    if labor:
        return ProductModel.LaborCostType.FIXED, labor.fc_price or Decimal("0")
    return ProductModel.LaborCostType.FIXED, Decimal("0")


def _stone_cost_usd_from_recipe(product: ProductModel) -> Decimal:
    recipe = product.pricing_recipes.order_by("-updated_at").first()
    if not recipe:
        return Decimal("0")
    stone = recipe.cost_lines.filter(line_type="TAS").first()
    if not stone:
        return Decimal("0")
    # Prefer USD lines; otherwise treat as USD-equivalent snapshot
    return stone.fc_price or Decimal("0")


def upsert_finished_detail(product: ProductModel, overrides: dict | None = None) -> FinishedDetail:
    o = overrides or {}
    labor_type, labor_value = _labor_from_recipe(product)
    defaults = {
        "metal_name": o.get("metalName", product.metal_name),
        "purity_code": o.get("purityCode", product.purity_code),
        "metal_color": o.get("metalColor", product.metal_color),
        "fineness": _d(o.get("fineness"), str(resolve_fineness(o.get("purityCode", product.purity_code)))),
        "base_weight_gr": _d(o.get("baseWeightGr", product.gross_weight_gram)),
        "fire_rate_pct": _d(o.get("fireRatePct", product.fire_rate_pct)),
        "labor_cost_type": o.get("laborCostType", labor_type),
        "labor_cost_value": _d(o.get("laborCostValue", labor_value)),
        "stone_summary": o.get("stoneSummary") or _stone_summary_from_product(product),
        "fixed_stone_cost_usd": _d(o.get("fixedStoneCostUsd", _stone_cost_usd_from_recipe(product))),
    }
    detail, _ = FinishedDetail.objects.update_or_create(product=product, defaults=defaults)
    return detail


def upsert_mounting_detail(product: ProductModel, overrides: dict | None = None) -> MountingDetail:
    o = overrides or {}
    labor_type, labor_value = _labor_from_recipe(product)
    defaults = {
        "metal_name": o.get("metalName", product.metal_name),
        "purity_code": o.get("purityCode", product.purity_code),
        "metal_color": o.get("metalColor", product.metal_color),
        "fineness": _d(o.get("fineness"), str(resolve_fineness(o.get("purityCode", product.purity_code)))),
        "net_weight_gr": _d(o.get("netWeightGr", product.gross_weight_gram)),
        "labor_cost_type": o.get("laborCostType", labor_type),
        "labor_cost_value": _d(o.get("laborCostValue", labor_value)),
        "mount_structure": o.get("mountStructure", product.mount_structure),
        "compatible_shapes": o.get("compatibleShapes", []),
        "min_carat": _d(o["minCarat"]) if o.get("minCarat") is not None else product.allowed_carat_min,
        "max_carat": _d(o["maxCarat"]) if o.get("maxCarat") is not None else product.allowed_carat_max,
        "min_length_mm": _d(o["minLengthMm"]) if o.get("minLengthMm") is not None else None,
        "max_length_mm": _d(o["maxLengthMm"]) if o.get("maxLengthMm") is not None else None,
        "min_width_mm": _d(o["minWidthMm"]) if o.get("minWidthMm") is not None else None,
        "max_width_mm": _d(o["maxWidthMm"]) if o.get("maxWidthMm") is not None else None,
        "setting_labor_usd": _d(o.get("settingLaborUsd", 0)),
        "setting_type_code": o.get("settingTypeCode", ""),
        "head_code": o.get("headCode", product.head_code),
        "band_code": o.get("bandCode", product.band_code),
        "head_weight_gram": o.get("headWeightGram", product.head_weight_gram),
        "band_weight_gram": o.get("bandWeightGram", product.band_weight_gram),
    }
    detail, _ = MountingDetail.objects.update_or_create(product=product, defaults=defaults)
    return detail


def upsert_loose_stone_detail(product: ProductModel, overrides: dict | None = None) -> LooseStoneDetail:
    o = overrides or {}
    center = product.stone_lines.filter(role="MERKEZ").first()
    carat = o.get("carat")
    if carat is None:
        carat = center.carat if center else Decimal("0")
    net = o.get("netCostUsd")
    if net is None:
        net = _stone_cost_usd_from_recipe(product)
    defaults = {
        "stone_category": o.get("stoneCategory", product.stone_type or "Pırlanta"),
        "shape": o.get("shape", product.stone_cut_shape or (center.cut_shape if center else "")),
        "carat": _d(carat),
        "color": o.get("color", product.stone_color_grade or (center.color_grade if center else "")),
        "clarity": o.get("clarity", product.stone_clarity or (center.clarity if center else "")),
        "cut_grade": o.get("cutGrade", product.stone_cut_grade),
        "cert_lab": o.get("certLab", product.certificate_agency),
        "cert_number": o.get("certNumber", product.certificate_number),
        "cert_url": o.get("certUrl", ""),
        "measurements_mm": o.get("measurementsMm", ""),
        "length_mm": _d(o["lengthMm"]) if o.get("lengthMm") is not None else None,
        "width_mm": _d(o["widthMm"]) if o.get("widthMm") is not None else None,
        "depth_mm": _d(o["depthMm"]) if o.get("depthMm") is not None else None,
        "rapaport_price_usd": _d(o["rapaportPriceUsd"]) if o.get("rapaportPriceUsd") is not None else None,
        "discount_percent": _d(o["discountPercent"]) if o.get("discountPercent") is not None else None,
        "net_cost_usd": _d(net),
        "supplier_id": o.get("supplierId", product.supplier_name or "INTERNAL"),
    }
    detail, _ = LooseStoneDetail.objects.update_or_create(product=product, defaults=defaults)
    return detail


def clear_other_details(product: ProductModel, kind: str) -> None:
    if kind != FINISHED:
        FinishedDetail.objects.filter(product=product).delete()
    if kind != MOUNTING:
        MountingDetail.objects.filter(product=product).delete()
    if kind != LOOSE_STONE:
        LooseStoneDetail.objects.filter(product=product).delete()


def dual_write_product_details(product: ProductModel, overrides: dict | None = None) -> None:
    """Upsert the matching detail row and remove mismatched kinds."""
    if not dual_write_enabled():
        return
    kind = sync_kind_and_label(product)
    product.save(update_fields=["product_kind", "product_type", "stock_qty", "updated_at"])
    clear_other_details(product, kind)
    if kind == FINISHED:
        upsert_finished_detail(product, overrides)
    elif kind == MOUNTING:
        upsert_mounting_detail(product, overrides)
    else:
        upsert_loose_stone_detail(product, overrides)


def mirror_detail_to_legacy(product: ProductModel) -> None:
    """Push detail fields back onto legacy ProductModel columns (read-path sync)."""
    kind = normalize_product_kind(product.product_kind)
    if kind == FINISHED and hasattr(product, "finished_detail"):
        d = product.finished_detail
        product.metal_name = d.metal_name
        product.purity_code = d.purity_code
        product.metal_color = d.metal_color
        product.gross_weight_gram = d.base_weight_gr
        product.fire_rate_pct = d.fire_rate_pct
    elif kind == MOUNTING and hasattr(product, "mounting_detail"):
        d = product.mounting_detail
        product.metal_name = d.metal_name
        product.purity_code = d.purity_code
        product.metal_color = d.metal_color
        product.gross_weight_gram = d.net_weight_gr
        product.mount_structure = d.mount_structure
        product.allowed_carat_min = d.min_carat or product.allowed_carat_min
        product.allowed_carat_max = d.max_carat or product.allowed_carat_max
        product.head_code = d.head_code
        product.band_code = d.band_code
        product.head_weight_gram = d.head_weight_gram
        product.band_weight_gram = d.band_weight_gram
    elif kind == LOOSE_STONE and hasattr(product, "loose_stone_detail"):
        d = product.loose_stone_detail
        product.stone_type = d.stone_category
        product.stone_cut_shape = d.shape
        product.stone_color_grade = d.color
        product.stone_clarity = d.clarity
        product.stone_cut_grade = d.cut_grade
        product.certificate_agency = d.cert_lab
        product.certificate_number = d.cert_number


def serialize_finished_detail(d: FinishedDetail, *, for_ops: bool = False) -> dict:
    data = {
        "metalName": d.metal_name,
        "purityCode": d.purity_code,
        "metalColor": d.metal_color,
        "fineness": dec_str(d.fineness, Decimal("0.0001")),
        "baseWeightGr": dec_str(d.base_weight_gr, GRAM_Q),
        "stoneSummary": d.stone_summary or {},
    }
    if for_ops:
        data.update(
            {
                "fireRatePct": dec_str(d.fire_rate_pct, MONEY_Q),
                "laborCostType": d.labor_cost_type,
                "laborCostValue": dec_str(d.labor_cost_value, MONEY_Q),
                "fixedStoneCostUsd": dec_str(d.fixed_stone_cost_usd, MONEY_Q),
            }
        )
    return data


def serialize_mounting_detail(d: MountingDetail, *, for_ops: bool = False) -> dict:
    data = {
        "metalName": d.metal_name,
        "purityCode": d.purity_code,
        "metalColor": d.metal_color,
        "fineness": dec_str(d.fineness, Decimal("0.0001")),
        "netWeightGr": dec_str(d.net_weight_gr, GRAM_Q),
        "mountStructure": d.mount_structure,
        "compatibleShapes": d.compatible_shapes or [],
        "minCarat": dec_str(d.min_carat, CARAT_Q),
        "maxCarat": dec_str(d.max_carat, CARAT_Q),
        "minLengthMm": dec_str(d.min_length_mm, MONEY_Q),
        "maxLengthMm": dec_str(d.max_length_mm, MONEY_Q),
        "minWidthMm": dec_str(d.min_width_mm, MONEY_Q),
        "maxWidthMm": dec_str(d.max_width_mm, MONEY_Q),
        "settingTypeCode": d.setting_type_code,
        "headCode": d.head_code,
        "bandCode": d.band_code,
        "headWeightGram": dec_str(d.head_weight_gram, GRAM_Q),
        "bandWeightGram": dec_str(d.band_weight_gram, GRAM_Q),
    }
    if for_ops:
        data.update(
            {
                "laborCostType": d.labor_cost_type,
                "laborCostValue": dec_str(d.labor_cost_value, MONEY_Q),
                "settingLaborUsd": dec_str(d.setting_labor_usd, MONEY_Q),
            }
        )
    return data


def serialize_loose_stone_detail(d: LooseStoneDetail, *, for_ops: bool = False) -> dict:
    data = {
        "stoneCategory": d.stone_category,
        "shape": d.shape,
        "carat": dec_str(d.carat, CARAT_Q),
        "color": d.color,
        "clarity": d.clarity,
        "cutGrade": d.cut_grade,
        "certLab": d.cert_lab,
        "certNumber": d.cert_number,
        "certUrl": d.cert_url,
        "measurementsMm": d.measurements_mm,
        "lengthMm": dec_str(d.length_mm, MONEY_Q),
        "widthMm": dec_str(d.width_mm, MONEY_Q),
        "depthMm": dec_str(d.depth_mm, MONEY_Q),
    }
    if for_ops:
        data.update(
            {
                "rapaportPriceUsd": dec_str(d.rapaport_price_usd, MONEY_Q),
                "discountPercent": dec_str(d.discount_percent, MONEY_Q),
                "netCostUsd": dec_str(d.net_cost_usd, MONEY_Q),
                "supplierId": d.supplier_id,
            }
        )
    return data


def _safe_related(product: ProductModel, attr: str):
    try:
        return getattr(product, attr)
    except Exception:
        return None


def serialize_product_details(product: ProductModel, *, for_ops: bool = False) -> dict:
    kind = normalize_product_kind(product.product_kind)
    out: dict[str, Any] = {
        "productKind": kind,
        "finishedDetail": None,
        "mountingDetail": None,
        "looseStoneDetail": None,
    }
    if kind == FINISHED:
        detail = _safe_related(product, "finished_detail")
        if detail:
            out["finishedDetail"] = serialize_finished_detail(detail, for_ops=for_ops)
    elif kind == MOUNTING:
        detail = _safe_related(product, "mounting_detail")
        if detail:
            out["mountingDetail"] = serialize_mounting_detail(detail, for_ops=for_ops)
    else:
        detail = _safe_related(product, "loose_stone_detail")
        if detail:
            out["looseStoneDetail"] = serialize_loose_stone_detail(detail, for_ops=for_ops)
    return out

"""
DYO (Design Your Own): mounting ↔ stone matching, soft-locks, bundle create, pricing.
"""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.catalog.models import LooseStoneDetail, MountingDetail, ProductModel, ProductVariant
from apps.catalog.product_kinds import LOOSE_STONE, MOUNTING, normalize_product_kind
from apps.market.services import get_current_rate_snapshot
from apps.pricing.engine import (
    AdjustmentInput,
    ChannelRuleInput,
    CostLineInput,
    PricingEngineInput,
    calculate_pricing,
    get_matrix_rate,
    q_money,
    ZERO,
)
from apps.pricing.models import PricingRecipe
from config.exceptions import DomainError

from .models import (
    B2bDraftLine,
    B2cCartItem,
    BundleRole,
    CustomBundle,
    StoneSoftLock,
)

STONE_LOCK_TTL_SECONDS = int(getattr(settings, "DYO_STONE_LOCK_TTL_SECONDS", 15 * 60))
REDIS_LOCK_PREFIX = "stone_lock:"


def normalize_shape(value: str) -> str:
    raw = (value or "").strip().upper()
    raw = raw.replace(" ", "_").replace("-", "_")
    aliases = {
        "YUVARLAK": "ROUND",
        "ROUND": "ROUND",
        "BRILLIANT": "ROUND",
        "OVAL": "OVAL",
        "PRINCESS": "PRINCESS",
        "PRINSES": "PRINCESS",
        "BAGET": "BAGUETTE",
        "BAGUETTE": "BAGUETTE",
        "DAMLA": "PEAR",
        "PEAR": "PEAR",
        "MARKIZ": "MARQUISE",
        "MARQUISE": "MARQUISE",
        "KALP": "HEART",
        "HEART": "HEART",
        "ZUMRUT_KESIM": "EMERALD",
        "EMERALD": "EMERALD",
    }
    if raw in aliases:
        return aliases[raw]
    # "Yuvarlak (Round)" → ROUND
    m = re.search(r"\(([A-Z]+)\)", (value or "").upper())
    if m and m.group(1) in aliases:
        return aliases[m.group(1)]
    return raw


def normalize_shape_list(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for v in values or []:
        n = normalize_shape(str(v))
        if n and n not in out:
            out.append(n)
    return out


def _active_locked_stone_ids(*, exclude_user_id=None, exclude_bundle_id=None) -> set:
    now = timezone.now()
    qs = StoneSoftLock.objects.filter(status=StoneSoftLock.Status.ACTIVE, expires_at__gt=now)
    if exclude_user_id:
        qs = qs.exclude(user_id=exclude_user_id)
    if exclude_bundle_id:
        qs = qs.exclude(bundle_id=exclude_bundle_id)
    return set(qs.values_list("stone_product_id", flat=True))


def get_mounting_detail(mounting: ProductModel) -> MountingDetail:
    if normalize_product_kind(mounting.product_kind) != MOUNTING:
        raise DomainError("Ürün montür (MOUNTING) değil.", code="DYO_NOT_MOUNTING", status_code=400)
    detail = MountingDetail.objects.filter(product=mounting).first()
    if detail is None:
        raise DomainError("Montür detayı bulunamadı.", code="DYO_MOUNTING_DETAIL_MISSING", status_code=400)
    return detail


def compatible_stones_queryset(
    mounting: ProductModel,
    *,
    exclude_user_id=None,
    color: str = "",
    clarity: str = "",
) -> QuerySet[LooseStoneDetail]:
    detail = get_mounting_detail(mounting)
    shapes = normalize_shape_list(detail.compatible_shapes or [])
    if not shapes:
        return LooseStoneDetail.objects.none()
    if detail.min_carat is None or detail.max_carat is None:
        raise DomainError(
            "Montür min/max karat aralığı tanımlı değil.",
            code="DYO_MOUNTING_RANGE_MISSING",
            status_code=400,
        )

    locked = _active_locked_stone_ids(exclude_user_id=exclude_user_id)
    qs = LooseStoneDetail.objects.filter(
        product__product_kind=LOOSE_STONE,
        product__stock_status=ProductModel.StockStatus.IN_STOCK,
        product__stock_qty__gt=0,
        carat__gte=detail.min_carat,
        carat__lte=detail.max_carat,
    ).select_related("product")
    if locked:
        qs = qs.exclude(product_id__in=locked)
    if color:
        qs = qs.filter(color__iexact=color.strip())
    if clarity:
        qs = qs.filter(clarity__iexact=clarity.strip())

    # Shape filter in Python-normalized form via Q of iexact / icontains fallbacks
    shape_q = Q()
    for s in shapes:
        shape_q |= Q(shape__iexact=s) | Q(shape__icontains=s)
    qs = qs.filter(shape_q)

    if detail.min_length_mm is not None:
        qs = qs.filter(Q(length_mm__isnull=True) | Q(length_mm__gte=detail.min_length_mm))
    if detail.max_length_mm is not None:
        qs = qs.filter(Q(length_mm__isnull=True) | Q(length_mm__lte=detail.max_length_mm))
    if detail.min_width_mm is not None:
        qs = qs.filter(Q(width_mm__isnull=True) | Q(width_mm__gte=detail.min_width_mm))
    if detail.max_width_mm is not None:
        qs = qs.filter(Q(width_mm__isnull=True) | Q(width_mm__lte=detail.max_width_mm))

    return qs.order_by("carat", "net_cost_usd")


def validate_mounting_stone_pair(mounting: ProductModel, stone: ProductModel) -> MountingDetail:
    if normalize_product_kind(stone.product_kind) != LOOSE_STONE:
        raise DomainError("Ürün serbest taş (LOOSE_STONE) değil.", code="DYO_NOT_STONE", status_code=400)
    stone_detail = LooseStoneDetail.objects.filter(product=stone).first()
    if stone_detail is None:
        raise DomainError("Taş detayı bulunamadı.", code="DYO_STONE_DETAIL_MISSING", status_code=400)
    if stone.stock_qty <= 0 or stone.stock_status != ProductModel.StockStatus.IN_STOCK:
        raise DomainError("Taş stokta değil.", code="DYO_STONE_UNAVAILABLE", status_code=409)

    detail = get_mounting_detail(mounting)
    shapes = normalize_shape_list(detail.compatible_shapes or [])
    stone_shape = normalize_shape(stone_detail.shape)
    if stone_shape not in shapes:
        raise DomainError(
            f"Taş şekli ({stone_detail.shape}) montür ile uyumlu değil.",
            code="DYO_SHAPE_MISMATCH",
            status_code=400,
        )
    if detail.min_carat is None or detail.max_carat is None:
        raise DomainError("Montür karat aralığı eksik.", code="DYO_MOUNTING_RANGE_MISSING", status_code=400)
    if not (detail.min_carat <= stone_detail.carat <= detail.max_carat):
        raise DomainError(
            f"Taş karatı ({stone_detail.carat}) montür aralığı dışında.",
            code="DYO_CARAT_MISMATCH",
            status_code=400,
        )
    return detail


def _redis_lock_key(stone_product_id) -> str:
    return f"{REDIS_LOCK_PREFIX}{stone_product_id}"


@transaction.atomic
def acquire_stone_soft_lock(*, user, stone: ProductModel, bundle: CustomBundle | None = None) -> StoneSoftLock:
    """Exclusive soft-lock. `bundle` may be null for non-DYO single-stone cart holds."""
    # Row lock on the stone product serializes concurrent POST /dyo/bundles (and future solo locks).
    stone = ProductModel.objects.select_for_update().get(pk=stone.pk)

    now = timezone.now()
    expires = now + timedelta(seconds=STONE_LOCK_TTL_SECONDS)
    StoneSoftLock.objects.filter(
        status=StoneSoftLock.Status.ACTIVE, expires_at__lte=now
    ).update(status=StoneSoftLock.Status.RELEASED)

    existing = (
        StoneSoftLock.objects.select_for_update()
        .filter(stone_product=stone, status=StoneSoftLock.Status.ACTIVE, expires_at__gt=now)
        .first()
    )
    if existing and existing.user_id != user.id:
        raise DomainError(
            "Bu taş başka bir kullanıcı tarafından rezerve edildi.",
            code="STONE_LOCKED",
            status_code=409,
        )
    if existing and existing.user_id == user.id:
        existing.expires_at = expires
        existing.bundle = bundle or existing.bundle
        existing.save(update_fields=["expires_at", "bundle", "updated_at"])
        cache.set(
            _redis_lock_key(stone.id),
            {"userId": str(user.id), "bundleId": str(bundle.id) if bundle else None},
            STONE_LOCK_TTL_SECONDS,
        )
        return existing

    try:
        lock = StoneSoftLock.objects.create(
            stone_product=stone,
            user=user,
            bundle=bundle,
            expires_at=expires,
            status=StoneSoftLock.Status.ACTIVE,
        )
    except IntegrityError as exc:
        raise DomainError(
            "Bu taş başka bir kullanıcı tarafından rezerve edildi.",
            code="STONE_LOCKED",
            status_code=409,
        ) from exc
    cache.set(
        _redis_lock_key(stone.id),
        {"userId": str(user.id), "bundleId": str(bundle.id) if bundle else None},
        STONE_LOCK_TTL_SECONDS,
    )
    return lock


def release_stone_soft_lock(*, stone: ProductModel, user=None) -> None:
    qs = StoneSoftLock.objects.filter(stone_product=stone, status=StoneSoftLock.Status.ACTIVE)
    if user is not None:
        qs = qs.filter(user=user)
    qs.update(status=StoneSoftLock.Status.RELEASED)
    cache.delete(_redis_lock_key(stone.id))


def release_expired_stone_locks() -> int:
    now = timezone.now()
    expired = list(
        StoneSoftLock.objects.filter(status=StoneSoftLock.Status.ACTIVE, expires_at__lte=now)
    )
    count = 0
    for lock in expired:
        lock.status = StoneSoftLock.Status.RELEASED
        lock.save(update_fields=["status", "updated_at"])
        cache.delete(_redis_lock_key(lock.stone_product_id))
        CustomBundle.objects.filter(
            id=lock.bundle_id, status__in=[CustomBundle.Status.DRAFT, CustomBundle.Status.IN_CART]
        ).update(status=CustomBundle.Status.EXPIRED)
        count += 1
    return count


def extend_bundle_lock(*, bundle: CustomBundle) -> None:
    now = timezone.now()
    expires = now + timedelta(seconds=STONE_LOCK_TTL_SECONDS)
    bundle.expires_at = expires
    bundle.save(update_fields=["expires_at", "updated_at"])
    StoneSoftLock.objects.filter(
        bundle=bundle, status=StoneSoftLock.Status.ACTIVE
    ).update(expires_at=expires)
    cache.set(
        _redis_lock_key(bundle.stone_product_id),
        {"userId": str(bundle.user_id), "bundleId": str(bundle.id)},
        STONE_LOCK_TTL_SECONDS,
    )


def _default_channel_rules() -> list[ChannelRuleInput]:
    return [
        ChannelRuleInput(
            channel="B2B",
            profit=AdjustmentInput(unit="%", value=Decimal("10")),
            discount=AdjustmentInput(unit="%", value=ZERO),
            servis_bedeli=AdjustmentInput(unit="%", value=ZERO),
        ),
        ChannelRuleInput(
            channel="B2B_API",
            profit=AdjustmentInput(unit="%", value=Decimal("12")),
            discount=AdjustmentInput(unit="%", value=ZERO),
            servis_bedeli=AdjustmentInput(unit="%", value=ZERO),
        ),
        ChannelRuleInput(
            channel="B2C_API",
            profit=AdjustmentInput(unit="%", value=Decimal("40")),
            discount=AdjustmentInput(unit="%", value=ZERO),
            servis_bedeli=AdjustmentInput(unit="%", value=Decimal("2")),
        ),
    ]


def _channel_rules_from_mounting(mounting: ProductModel) -> list[ChannelRuleInput]:
    recipe = (
        PricingRecipe.objects.filter(product=mounting, status=PricingRecipe.Status.PUBLISHED)
        .prefetch_related("channel_rules")
        .first()
    )
    if recipe is None:
        return _default_channel_rules()
    rules: list[ChannelRuleInput] = []
    for cr in recipe.channel_rules.all():
        ch = (cr.channel or "").strip().upper()
        if ch == "B2C":
            ch = "B2C_API"
        if ch not in ("B2B", "B2B_API", "B2C_API"):
            continue
        rules.append(
            ChannelRuleInput(
                channel=ch,  # type: ignore[arg-type]
                profit=AdjustmentInput(unit=cr.profit_unit, value=cr.profit_value),
                discount=AdjustmentInput(unit=cr.discount_unit, value=cr.discount_value),
                servis_bedeli=AdjustmentInput(unit=cr.servis_bedeli_unit, value=cr.servis_bedeli_value),
            )
        )
    return rules or _default_channel_rules()


def calculate_dyo_bundle(
    *,
    mounting: ProductModel,
    stone: ProductModel,
    setting_labor_usd: Decimal | None = None,
) -> dict:
    """Compose mounting + stone + setting labor base cost, apply channel rules once."""
    mount_detail = validate_mounting_stone_pair(mounting, stone)
    stone_detail = LooseStoneDetail.objects.get(product=stone)
    snap = get_current_rate_snapshot()
    rates = snap.get_decimal_rates()
    has_try = snap.live_has_gold_try_sell
    usd_try = get_matrix_rate("USD", "TRY", rates)

    setting_usd = (
        setting_labor_usd
        if setting_labor_usd is not None
        else (mount_detail.setting_labor_usd or ZERO)
    )
    pure = mount_detail.net_weight_gr * mount_detail.fineness
    if mount_detail.labor_cost_type == ProductModel.LaborCostType.PER_GRAM:
        labor_usd = mount_detail.net_weight_gr * mount_detail.labor_cost_value
    else:
        labor_usd = mount_detail.labor_cost_value
    metal_try = pure * has_try
    labor_try = labor_usd * usd_try
    stone_try = (stone_detail.net_cost_usd or ZERO) * usd_try
    setting_try = setting_usd * usd_try
    base_cost_try = metal_try + labor_try + stone_try + setting_try

    engine_input = PricingEngineInput(
        pricing_mode="2",
        lc_currency="TRY",
        purity_code=mount_detail.purity_code or "14K",
        gross_weight_gram=Decimal("1"),
        fire_rate_pct=ZERO,
        has_gold_try_per_gram=has_try,
        fx_base_rates=rates,
        stone_lines=(),
        cost_lines=[CostLineInput(line_type="TEDARIKCI", fc_currency="TRY", fc_price=base_cost_try)],
        channel_rules=_channel_rules_from_mounting(mounting),
    )
    out = calculate_pricing(engine_input)
    channels = {}
    for key, ch in out.channels.items():
        channels[key] = {
            "finalPriceTry": float(ch.nihai_fiyat_try),
            "listPriceTry": float(ch.liste_fiyati_try),
            "profitLc": float(ch.profit_lc),
            "discountLc": float(ch.discount_lc),
            "serviceFeeLc": float(ch.servis_bedeli_lc),
        }
    return {
        "snapshotCode": snap.snapshot_code,
        # Internal cost/fire components — strip via public_dyo_pricing() for buyers.
        "pureGoldEquivalent": float(pure),
        "mountLaborUsd": float(labor_usd),
        "stoneUsd": float(stone_detail.net_cost_usd or ZERO),
        "settingLaborUsd": float(setting_usd),
        "baseCostTry": float(q_money(base_cost_try)),
        "breakdownTry": {
            "metal": float(q_money(metal_try)),
            "labor": float(q_money(labor_try)),
            "stone": float(q_money(stone_try)),
            "setting": float(q_money(setting_try)),
        },
        "channels": channels,
    }


def public_dyo_pricing(pricing: dict) -> dict:
    """Buyer-facing DYO quote: channel finals only (blind-pool)."""
    return {
        "snapshotCode": pricing.get("snapshotCode"),
        "channels": pricing.get("channels") or {},
    }


def _default_variant(product: ProductModel) -> ProductVariant | None:
    return (
        ProductVariant.objects.filter(product=product, is_active=True)
        .order_by("-is_default", "created_at")
        .first()
    )


@transaction.atomic
def create_dyo_bundle(
    *,
    user,
    mounting_sku: str,
    stone_sku: str,
    audience: str = "B2C",
    add_to_cart: bool = True,
) -> tuple[CustomBundle, dict]:
    mounting = ProductModel.objects.select_for_update().filter(parent_sku__iexact=mounting_sku).first()
    stone = ProductModel.objects.select_for_update().filter(parent_sku__iexact=stone_sku).first()
    if mounting is None:
        raise DomainError(f"Montür bulunamadı: {mounting_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
    if stone is None:
        raise DomainError(f"Taş bulunamadı: {stone_sku}", code="PRODUCT_NOT_FOUND", status_code=404)

    mount_detail = validate_mounting_stone_pair(mounting, stone)
    pricing = calculate_dyo_bundle(mounting=mounting, stone=stone)
    expires = timezone.now() + timedelta(seconds=STONE_LOCK_TTL_SECONDS)
    audience_norm = CustomBundle.Audience.B2B if audience.upper() == "B2B" else CustomBundle.Audience.B2C

    bundle = CustomBundle.objects.create(
        user=user,
        audience=audience_norm,
        mounting_product=mounting,
        stone_product=stone,
        mounting_variant=_default_variant(mounting),
        stone_variant=_default_variant(stone),
        status=CustomBundle.Status.IN_CART if add_to_cart else CustomBundle.Status.DRAFT,
        setting_labor_usd=mount_detail.setting_labor_usd or ZERO,
        expires_at=expires,
    )
    acquire_stone_soft_lock(user=user, stone=stone, bundle=bundle)

    b2c_final = Decimal(str(pricing["channels"].get("B2C_API", {}).get("finalPriceTry", pricing["baseCostTry"])))
    b2b_final = Decimal(str(pricing["channels"].get("B2B", {}).get("finalPriceTry", pricing["baseCostTry"])))
    metal = Decimal(str(pricing["breakdownTry"]["metal"]))
    labor = Decimal(str(pricing["breakdownTry"]["labor"]))
    setting = Decimal(str(pricing["breakdownTry"]["setting"]))
    stone_try = Decimal(str(pricing["breakdownTry"]["stone"]))
    mount_share = metal + labor + setting
    total_parts = mount_share + stone_try
    if total_parts <= 0:
        mount_ratio = Decimal("0.5")
    else:
        mount_ratio = mount_share / total_parts

    if add_to_cart and audience_norm == CustomBundle.Audience.B2C:
        final_total = b2c_final
        mount_price = q_money(final_total * mount_ratio)
        stone_price = q_money(final_total - mount_price)
        _add_b2c_bundle_lines(user=user, bundle=bundle, mount_price=mount_price, stone_price=stone_price, snap_code=pricing["snapshotCode"])
    elif add_to_cart and audience_norm == CustomBundle.Audience.B2B:
        final_total = b2b_final
        mount_price = q_money(final_total * mount_ratio)
        stone_price = q_money(final_total - mount_price)
        _add_b2b_bundle_lines(
            user=user,
            bundle=bundle,
            mount_price=mount_price,
            stone_price=stone_price,
            snap_code=pricing["snapshotCode"],
            pricing=pricing,
        )

    return bundle, pricing


def _add_b2c_bundle_lines(*, user, bundle: CustomBundle, mount_price: Decimal, stone_price: Decimal, snap_code: str):
    snap = get_current_rate_snapshot()
    m = bundle.mounting_product
    s = bundle.stone_product
    mv = bundle.mounting_variant
    sv = bundle.stone_variant
    B2cCartItem.objects.create(
        user=user,
        variant=mv,
        bundle=bundle,
        bundle_role=BundleRole.MOUNTING,
        sku=mv.sku if mv else m.parent_sku,
        parent_sku=m.parent_sku,
        title=f"[DYO Montür] {m.title}",
        category=m.category,
        metal_color=m.metal_color,
        purity_code=m.purity_code[:8],
        size=m.variant_size,
        qty=1,
        stock_status=m.stock_status,
        gross_weight_gram=m.gross_weight_gram,
        unit_list_price_try=mount_price,
        unit_final_price_try=mount_price,
        rate_snapshot=snap,
        snapshot_code=snap_code,
    )
    B2cCartItem.objects.create(
        user=user,
        variant=sv,
        bundle=bundle,
        bundle_role=BundleRole.STONE,
        sku=sv.sku if sv else s.parent_sku,
        parent_sku=s.parent_sku,
        title=f"[DYO Taş] {s.title}",
        category=s.category,
        metal_color=s.metal_color or "—",
        purity_code=(s.purity_code or "—")[:8],
        size=s.variant_size or 0,
        qty=1,
        stock_status=s.stock_status,
        certificate_label=s.certificate_number or "",
        gross_weight_gram=Decimal("0"),
        unit_list_price_try=stone_price,
        unit_final_price_try=stone_price,
        rate_snapshot=snap,
        snapshot_code=snap_code,
    )


def _add_b2b_bundle_lines(*, user, bundle: CustomBundle, mount_price, stone_price, snap_code, pricing):
    from apps.organizations.selectors import resolve_tenant_context

    # Organization from user's active membership is resolved at API layer; store under first org of lines' creator
    org = None
    membership = getattr(user, "memberships", None)
    if membership is not None:
        m = user.memberships.select_related("organization").first()
        if m:
            org = m.organization
    if org is None:
        raise DomainError("B2B DYO için organizasyon üyeliği gerekli.", code="ORG_REQUIRED", status_code=400)

    snap = get_current_rate_snapshot()
    m = bundle.mounting_product
    s = bundle.stone_product
    for role, product, variant, price, labor_usd in (
        (
            BundleRole.MOUNTING,
            m,
            bundle.mounting_variant,
            mount_price,
            Decimal(str(pricing["mountLaborUsd"])) + Decimal(str(pricing["settingLaborUsd"])),
        ),
        (
            BundleRole.STONE,
            s,
            bundle.stone_variant,
            stone_price,
            Decimal(str(pricing["stoneUsd"])),
        ),
    ):
        B2bDraftLine.objects.create(
            organization=org,
            created_by=user,
            variant=variant,
            bundle=bundle,
            bundle_role=role,
            sku=variant.sku if variant else product.parent_sku,
            parent_sku=product.parent_sku,
            title=f"[DYO {role}] {product.title}",
            category=product.category,
            metal_color=product.metal_color or "—",
            purity_code=(product.purity_code or "—")[:8],
            size=product.variant_size or 0,
            qty=1,
            unit_gross_gram=product.gross_weight_gram if role == BundleRole.MOUNTING else ZERO,
            unit_net_metal_gram=Decimal(str(pricing["pureGoldEquivalent"])) if role == BundleRole.MOUNTING else ZERO,
            unit_fire_included_fine_gram=Decimal(str(pricing["pureGoldEquivalent"])) if role == BundleRole.MOUNTING else ZERO,
            unit_labor_and_stone_usd=labor_usd,
            unit_wholesale_usd=labor_usd,
            unit_wholesale_try=price,
            pricing_currency="TRY",
            rate_snapshot=snap,
            snapshot_code=snap_code,
        )


def serialize_bundle(bundle: CustomBundle, pricing: dict | None = None, *, for_ops: bool = False) -> dict:
    data = {
        "id": str(bundle.id),
        "status": bundle.status,
        "audience": bundle.audience,
        "mountingSku": bundle.mounting_product.parent_sku,
        "stoneSku": bundle.stone_product.parent_sku,
        "expiresAt": bundle.expires_at.isoformat() if bundle.expires_at else None,
        "pricing": pricing if for_ops else (public_dyo_pricing(pricing) if pricing else None),
    }
    if for_ops:
        data["settingLaborUsd"] = float(bundle.setting_labor_usd)
    return data

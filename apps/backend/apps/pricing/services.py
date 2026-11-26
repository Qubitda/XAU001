from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from dataclasses import replace
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record_audit
from apps.catalog.models import ProductModel, ProductVariant
from apps.market.models import RateSnapshot
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Organization
from config.exceptions import DomainError
from .engine import (
    AdjustmentInput,
    ChannelRuleInput,
    CostLineInput,
    MountCaratRangeError,
    MountRangeInput,
    PricingEngineError,
    PricingEngineInput,
    PricingEngineOutput,
    StoneLineInput,
    calculate_pricing,
)
from .models import PriceLock, PriceQuote, PricingRecipe
from .strategies import build_input_from_details


GRAM_Q = Decimal("0.0001")


def resolve_product_variant(
    product: ProductModel,
    *,
    variant: ProductVariant | None = None,
    variant_id: str | None = None,
    variant_sku: str | None = None,
    purity_code: str | None = None,
    metal_color: str | None = None,
    size: int | None = None,
) -> ProductVariant | None:
    """
    Deterministically resolves a concrete sellable ProductVariant for a ProductModel.
    - Explicit variant_id / variant_sku must match an active variant of `product` (else 404).
    - Attribute fallback matches (purity_code, metal_color, size) -> (purity_code, metal_color)
      -> default variant -> first active variant.
    """
    if variant is not None:
        if variant.product_id != product.id:
            raise DomainError(
                "Seçilen varyant bu ürüne ait değil.",
                code="VARIANT_PRODUCT_MISMATCH",
                status_code=400,
            )
        return variant

    if variant_id:
        found = ProductVariant.objects.filter(
            id=variant_id, product=product, is_active=True
        ).first()
        if found is None:
            raise DomainError(
                f"Varyant bulunamadı: {variant_id}",
                code="VARIANT_NOT_FOUND",
                status_code=404,
            )
        return found

    if variant_sku:
        found = ProductVariant.objects.filter(
            sku__iexact=variant_sku.strip(), product=product, is_active=True
        ).first()
        if found is None:
            raise DomainError(
                f"Varyant SKU bulunamadı: {variant_sku}",
                code="VARIANT_NOT_FOUND",
                status_code=404,
            )
        return found

    variants = list(
        ProductVariant.objects.filter(product=product, is_active=True).order_by("-is_default", "created_at")
    )
    if not variants:
        return None

    target_purity = (purity_code or "").strip()
    target_color = (metal_color or "").strip()

    if target_purity and target_color and size is not None:
        exact = next(
            (
                v
                for v in variants
                if v.purity_code == target_purity and v.metal_color == target_color and v.size == size
            ),
            None,
        )
        if exact is not None:
            return exact

    if target_purity and target_color:
        match_pc = next(
            (v for v in variants if v.purity_code == target_purity and v.metal_color == target_color),
            None,
        )
        if match_pc is not None:
            return match_pc

    if target_color:
        match_c = next((v for v in variants if v.metal_color == target_color), None)
        if match_c is not None:
            return match_c

    if target_purity:
        match_p = next((v for v in variants if v.purity_code == target_purity), None)
        if match_p is not None:
            return match_p

    return next((v for v in variants if v.is_default), variants[0])


def compute_size_adjusted_gross_weight(
    product: ProductModel,
    size: int | None,
    *,
    variant: ProductVariant | None = None,
) -> Decimal:
    base_weight = variant.gross_weight_gram if variant is not None else product.gross_weight_gram
    base_size = variant.size if variant is not None else product.variant_size
    if size is None or size == base_size:
        return base_weight.quantize(GRAM_Q, rounding=ROUND_HALF_UP)
    step = Decimal("0.07") if product.category == "Yüzük" else Decimal("0.04")
    delta = Decimal(size - base_size) * step
    adjusted = base_weight + delta
    return max(Decimal("0.5000"), adjusted).quantize(GRAM_Q, rounding=ROUND_HALF_UP)


def evaluate_recipe(
    recipe: PricingRecipe,
    snapshot: RateSnapshot | None = None,
    *,
    variant: ProductVariant | None = None,
    enforce_mount_range: bool = False,
    gross_weight_override: Decimal | None = None,
) -> PricingEngineOutput:
    snap = snapshot or get_current_rate_snapshot()
    product = recipe.product

    # Build stone lines from ProductModel, substituting variant's center_stone_carat when set.
    stone_lines: list[StoneLineInput] = []
    center_overridden = False
    variant_center_carat = (
        variant.center_stone_carat if variant is not None and variant.center_stone_carat > 0 else None
    )
    for st in product.stone_lines.all():
        carat = st.carat
        if variant_center_carat is not None and st.role == "MERKEZ" and not center_overridden:
            carat = variant_center_carat
            center_overridden = True
        stone_lines.append(
            StoneLineInput(
                role=st.role,  # type: ignore[arg-type]
                stone_type=st.stone_type,
                measure_unit=st.measure_unit,  # type: ignore[arg-type]
                count=st.count,
                carat=carat,
            )
        )
    if variant_center_carat is not None and not center_overridden:
        stone_lines.insert(
            0,
            StoneLineInput(
                role="MERKEZ",
                stone_type=product.stone_type,
                measure_unit=product.stone_measure_unit,  # type: ignore[arg-type]
                count=1,
                carat=variant_center_carat,
            ),
        )

    cost_lines = [
        CostLineInput(
            line_type=cl.line_type,  # type: ignore[arg-type]
            fc_currency=cl.fc_currency,
            fc_price=cl.fc_price,
            fc_price_manual=cl.fc_price_manual,
            rate_override=cl.rate_override,
        )
        for cl in recipe.cost_lines.all()
    ]
    channel_rules: list[ChannelRuleInput] = []
    for cr in recipe.channel_rules.all():
        ch = (cr.channel or "").strip().upper()
        if ch == "B2C":
            ch = "B2C_API"
        if ch == "BOTH":
            # Legacy BOTH → apply same rule to B2B + B2C_API
            for legacy_target in ("B2B", "B2C_API"):
                channel_rules.append(
                    ChannelRuleInput(
                        channel=legacy_target,  # type: ignore[arg-type]
                        profit=AdjustmentInput(unit=cr.profit_unit, value=cr.profit_value),
                        discount=AdjustmentInput(unit=cr.discount_unit, value=cr.discount_value),
                        servis_bedeli=AdjustmentInput(
                            unit=cr.servis_bedeli_unit, value=cr.servis_bedeli_value
                        ),
                    )
                )
            continue
        if ch not in ("B2B", "B2B_API", "B2C_API"):
            continue
        channel_rules.append(
            ChannelRuleInput(
                channel=ch,  # type: ignore[arg-type]
                profit=AdjustmentInput(unit=cr.profit_unit, value=cr.profit_value),
                discount=AdjustmentInput(unit=cr.discount_unit, value=cr.discount_value),
                servis_bedeli=AdjustmentInput(unit=cr.servis_bedeli_unit, value=cr.servis_bedeli_value),
            )
        )
    mount_range = MountRangeInput(
        structure=product.mount_structure,  # type: ignore[arg-type]
        allowed_carat_min=product.allowed_carat_min,
        allowed_carat_max=product.allowed_carat_max,
    )

    effective_purity = variant.purity_code if variant is not None else product.purity_code
    effective_gross = (
        gross_weight_override
        if gross_weight_override is not None
        else (variant.gross_weight_gram if variant is not None else product.gross_weight_gram)
    )

    engine_input = PricingEngineInput(
        pricing_mode=recipe.pricing_mode,  # type: ignore[arg-type]
        lc_currency=recipe.lc_currency,
        purity_code=effective_purity,
        gross_weight_gram=effective_gross,
        fire_rate_pct=product.fire_rate_pct,
        has_gold_try_per_gram=snap.live_has_gold_try_sell,
        fx_base_rates=snap.get_decimal_rates(),
        stone_lines=stone_lines,
        cost_lines=cost_lines,
        channel_rules=channel_rules,
        mount_range=mount_range,
        enforce_mount_range=enforce_mount_range,
    )
    extras: dict = {}
    if getattr(settings, "PRICING_READ_FROM_DETAILS", False):
        engine_input, extras = build_input_from_details(product, base=engine_input)

    try:
        output = calculate_pricing(engine_input)
    except MountCaratRangeError as exc:
        raise DomainError(str(exc), code="MOUNT_CARAT_OUT_OF_RANGE", status_code=400) from exc
    except PricingEngineError as exc:
        raise DomainError(str(exc), code="PRICING_CALCULATION_ERROR", status_code=400) from exc

    if extras:
        output = replace(
            output,
            product_kind=extras.get("productKind"),
            pure_gold_equivalent=extras.get("pureGoldEquivalent"),
            labor_only_usd=extras.get("laborOnlyUsd"),
            fineness=extras.get("fineness", output.fineness),
        )
    return output


@transaction.atomic
def publish_recipe(recipe: PricingRecipe, *, actor=None) -> tuple[PricingRecipe, PricingEngineOutput]:
    """
    Publish a DRAFT recipe. Already-PUBLISHED recipes are immutable content-wise;
    re-publish of the same row only refreshes cached prices against live rates.
    To change cost lines / channel rules, create a new version (see _sync_recipe_from_ledger).
    """
    if recipe.status == PricingRecipe.Status.ARCHIVED:
        raise DomainError(
            "Arşivlenmiş reçete yeniden yayınlanamaz; yeni sürüm oluşturun.",
            code="RECIPE_ARCHIVED",
            status_code=400,
        )

    snap = get_current_rate_snapshot()
    default_variant = resolve_product_variant(recipe.product)
    output = evaluate_recipe(recipe, snap, variant=default_variant, enforce_mount_range=True)
    b2b = output.resolve_channel("B2B")
    b2c = output.resolve_channel("B2C")

    PricingRecipe.objects.filter(
        product=recipe.product, status=PricingRecipe.Status.PUBLISHED
    ).exclude(id=recipe.id).update(status=PricingRecipe.Status.ARCHIVED)

    recipe.status = PricingRecipe.Status.PUBLISHED
    recipe.last_snapshot = snap
    recipe.cached_total_cost_lc = output.total_cost_lc
    recipe.cached_b2b_try = b2b.nihai_fiyat_try if b2b else None
    recipe.cached_b2c_try = b2c.nihai_fiyat_try if b2c else None
    recipe.cached_b2c_list_try = b2c.liste_fiyati_try if b2c else None
    recipe.save(
        update_fields=[
            "status",
            "last_snapshot",
            "cached_total_cost_lc",
            "cached_b2b_try",
            "cached_b2c_try",
            "cached_b2c_list_try",
            "updated_at",
        ]
    )

    record_audit(
        action="PRICING_RECIPE_PUBLISHED",
        entity_type="PricingRecipe",
        entity_id=str(recipe.id),
        actor=actor,
        metadata={
            "parent_sku": recipe.product.parent_sku,
            "default_variant_sku": default_variant.sku if default_variant else None,
            "version": recipe.version,
            "snapshot_code": snap.snapshot_code,
            "b2b_try": str(recipe.cached_b2b_try) if recipe.cached_b2b_try else None,
            "b2c_try": str(recipe.cached_b2c_try) if recipe.cached_b2c_try else None,
        },
    )
    return recipe, output


@transaction.atomic
def create_live_quote(
    *,
    product: ProductModel,
    channel: str,
    variant: ProductVariant | None = None,
    variant_id: str | None = None,
    variant_sku: str | None = None,
    purity_code: str | None = None,
    metal_color: str | None = None,
    organization: Organization | None = None,
    snapshot: RateSnapshot | None = None,
    size: int | None = None,
) -> tuple[PriceQuote, PricingEngineOutput]:
    recipe = (
        PricingRecipe.objects.filter(product=product, status=PricingRecipe.Status.PUBLISHED)
        .prefetch_related("cost_lines", "channel_rules", "product__stone_lines")
        .select_related("product")
        .first()
    )
    if recipe is None:
        raise DomainError(
            f"{product.parent_sku} için yayınlanmış fiyat reçetesi bulunamadı.",
            code="RECIPE_NOT_PUBLISHED",
            status_code=400,
        )

    resolved_variant = resolve_product_variant(
        product,
        variant=variant,
        variant_id=variant_id,
        variant_sku=variant_sku,
        purity_code=purity_code,
        metal_color=metal_color,
        size=size,
    )
    effective_size = (
        size
        if size is not None
        else (resolved_variant.size if resolved_variant is not None else product.variant_size)
    )

    snap = snapshot or get_current_rate_snapshot()
    adjusted_gross = compute_size_adjusted_gross_weight(
        product, effective_size, variant=resolved_variant
    )
    output = evaluate_recipe(
        recipe,
        snap,
        variant=resolved_variant,
        enforce_mount_range=True,
        gross_weight_override=adjusted_gross,
    )
    ch = output.resolve_channel(channel)
    if ch is None:
        raise DomainError(
            f"{product.parent_sku} ürünü {channel} satış kanalına açık değil.",
            code="CHANNEL_NOT_CONFIGURED",
            status_code=400,
        )

    quote = PriceQuote.objects.create(
        product=product,
        variant=resolved_variant,
        recipe=recipe,
        rate_snapshot=snap,
        organization=organization,
        channel=channel,
        lc_currency=output.lc_currency,
        list_price_try=ch.liste_fiyati_try,
        final_price_lc=ch.nihai_fiyat_lc,
        final_price_try=ch.nihai_fiyat_try,
        effective_discount_pct=ch.effective_discount_pct,
        internal_audit_json={
            "recipe_version": recipe.version,
            "snapshot_code": snap.snapshot_code,
            "variant_id": str(resolved_variant.id) if resolved_variant else None,
            "variant_sku": resolved_variant.sku if resolved_variant else None,
            "purity_code": resolved_variant.purity_code if resolved_variant else product.purity_code,
            "metal_color": resolved_variant.metal_color if resolved_variant else product.metal_color,
            "size": effective_size,
            "gross_weight_gram": str(adjusted_gross),
            "total_stone_carat": str(output.total_stone_carat),
            "total_cost_lc": str(output.total_cost_lc),
            "servis_bedeli_lc": str(ch.servis_bedeli_lc),
            "fire_included_fine_metal_gram": str(output.fire_included_fine_metal_gram),
        },
    )
    return quote, output


def get_active_price_lock(user) -> PriceLock | None:
    now = timezone.now()
    return (
        PriceLock.objects.filter(user=user, is_active=True, expires_at__gt=now)
        .select_related("rate_snapshot")
        .order_by("-created_at")
        .first()
    )


def get_latest_price_lock(user) -> PriceLock | None:
    return (
        PriceLock.objects.filter(user=user, is_active=True)
        .select_related("rate_snapshot")
        .order_by("-created_at")
        .first()
    )


def get_or_refresh_price_lock(user, *, force_refresh: bool = False) -> PriceLock:
    now = timezone.now()
    if not force_refresh:
        active = get_active_price_lock(user)
        if active is not None:
            return active

    PriceLock.objects.filter(user=user, is_active=True).update(is_active=False)
    snap = get_current_rate_snapshot()
    return PriceLock.objects.create(
        user=user,
        rate_snapshot=snap,
        expires_at=now + timedelta(minutes=15),
        is_active=True,
    )

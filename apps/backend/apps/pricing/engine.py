"""
Tara Gold — Pure Python Decimal Pricing Engine (DB & HTTP independent).

Normative formula (ADR-0045 aligned):
1. 13-unit TRY-pivoted cross-rate matrix (TRY..CHF + XAU/XAG/XPT/XPD), 1 Troy Oz = 31.1034768 gr.
   Scoped fail-closed check: raises MissingRateError only when a currency actually used is missing/<=0.
2. Physical weight, multi-stone line tare, net metal, fine metal, and fire (waste) calculation.
   Validates actual center stone carat against Montür allowed carat range (FULL / HEAD_BAND).
3. Mode 1 (Detailed 5-line ledger: MADEN auto/manual + ISCILIK + TAS + MONTUR + DIGER)
   and Mode 2 (Supplier single-line price) with per-line optional rate_override.
4. Dynamic channel rules (B2B | B2C | BOTH) with % or fixed FX/metal adjustments:
   profit_lc -> ara_toplam_lc -> discount_lc -> net_satis_lc -> servis_bedeli_lc -> nihai_fiyat_lc/try.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Sequence

TROY_OZ_TO_GRAM = Decimal("31.1034768")
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

GRAM_Q = Decimal("0.0001")
MONEY_Q = Decimal("0.01")
RATE_Q = Decimal("0.000001")

FX_CURRENCIES: tuple[str, ...] = (
    "TRY",
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "CNY",
    "AUD",
    "CAD",
    "CHF",
    "XAU",
    "XAG",
    "XPT",
    "XPD",
)

PURITY_FINENESS: dict[str, Decimal] = {
    "8K": Decimal("0.333"),
    "9K": Decimal("0.375"),
    "10K": Decimal("0.417"),
    "14K": Decimal("0.585"),
    "18K": Decimal("0.750"),
    "21K": Decimal("0.875"),
    "22K": Decimal("0.916"),
    "24K": Decimal("0.995"),
    "24K_HAS": Decimal("0.995"),
    "24K_SAF": Decimal("0.999"),
    "24K (Has)": Decimal("0.995"),
    "24K (Saf)": Decimal("0.999"),
    "925": Decimal("0.925"),
    "999": Decimal("0.999"),
    "999 (Has)": Decimal("0.999"),
    "900": Decimal("0.900"),
    "950": Decimal("0.950"),
    "AYARSIZ": Decimal("0"),
}


class PricingEngineError(ValueError):
    pass


class MissingRateError(PricingEngineError):
    pass


class MountCaratRangeError(PricingEngineError):
    pass


@dataclass(frozen=True)
class StoneLineInput:
    role: Literal["MERKEZ", "YAN", "PAVE", "AKSAN"]
    stone_type: str
    measure_unit: Literal["ct", "gr", "mm"]
    count: int
    carat: Decimal


@dataclass(frozen=True)
class MountRangeInput:
    structure: Literal["FULL", "HEAD_BAND"]
    allowed_carat_min: Decimal
    allowed_carat_max: Decimal


@dataclass(frozen=True)
class CostLineInput:
    line_type: Literal["MADEN", "ISCILIK", "TAS", "MONTUR", "DIGER", "TEDARIKCI"]
    fc_currency: str
    fc_price: Decimal = ZERO
    fc_price_manual: Decimal | None = None
    rate_override: Decimal | None = None


@dataclass(frozen=True)
class AdjustmentInput:
    unit: str  # "%" or one of FX_CURRENCIES
    value: Decimal


@dataclass(frozen=True)
class ChannelRuleInput:
    channel: Literal["B2B", "B2B_API", "B2C_API"]
    profit: AdjustmentInput
    discount: AdjustmentInput
    servis_bedeli: AdjustmentInput


@dataclass(frozen=True)
class PricingEngineInput:
    pricing_mode: Literal["1", "2"]
    lc_currency: str
    purity_code: str
    gross_weight_gram: Decimal
    fire_rate_pct: Decimal
    has_gold_try_per_gram: Decimal
    fx_base_rates: dict[str, Decimal]
    stone_lines: Sequence[StoneLineInput]
    cost_lines: Sequence[CostLineInput]
    channel_rules: Sequence[ChannelRuleInput]
    mount_range: MountRangeInput | None = None
    enforce_mount_range: bool = False


@dataclass(frozen=True)
class ComputedLineResult:
    line_type: str
    fc_currency: str
    fc_price: Decimal
    matrix_rate: Decimal
    effective_rate: Decimal
    is_rate_overridden: bool
    lc_price: Decimal


@dataclass(frozen=True)
class ComputedChannelResult:
    channel: str
    profit_lc: Decimal
    ara_toplam_lc: Decimal
    discount_lc: Decimal
    net_satis_lc: Decimal
    servis_bedeli_lc: Decimal
    nihai_fiyat_lc: Decimal
    nihai_fiyat_try: Decimal
    liste_fiyati_try: Decimal
    effective_discount_pct: Decimal


@dataclass(frozen=True)
class PricingEngineOutput:
    fineness: Decimal
    total_stone_carat: Decimal
    stone_tare_gram: Decimal
    net_metal_gram: Decimal
    fine_metal_gram: Decimal
    fire_weight_gram: Decimal
    fire_included_metal_gram: Decimal
    fire_included_fine_metal_gram: Decimal
    is_carat_within_mount_range: bool
    lc_currency: str
    lc_to_try_rate: Decimal
    lines: dict[str, ComputedLineResult]
    total_cost_lc: Decimal
    channels: dict[str, ComputedChannelResult]
    # Populated when type-strategy pricing (PRICING_READ_FROM_DETAILS) is active
    product_kind: str | None = None
    pure_gold_equivalent: Decimal | None = None
    labor_only_usd: Decimal | None = None

    def resolve_channel(self, target: str) -> ComputedChannelResult | None:
        """
        Resolve a sales-channel price. Accepts B2B / B2B_API / B2C_API.
        Legacy 'B2C' maps to B2C_API for backward compatibility.
        """
        key = (target or "").strip().upper()
        if key == "B2C":
            key = "B2C_API"
        return self.channels.get(key)


def q_gram(val: Decimal) -> Decimal:
    return val.quantize(GRAM_Q, rounding=ROUND_HALF_UP)


def q_money(val: Decimal) -> Decimal:
    return val.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def get_matrix_rate(from_ccy: str, to_ccy: str, fx_base_rates: dict[str, Decimal]) -> Decimal:
    if from_ccy == to_ccy:
        return ONE
    from_try = fx_base_rates.get(from_ccy)
    to_try = fx_base_rates.get(to_ccy)
    if from_try is None or from_try <= ZERO:
        raise MissingRateError(f"Kur matrisinde geçerli {from_ccy} kuru bulunamadı.")
    if to_try is None or to_try <= ZERO:
        raise MissingRateError(f"Kur matrisinde geçerli {to_ccy} kuru bulunamadı.")
    return from_try / to_try


def resolve_stone_tare_factor(stone_type: str, measure_unit: str) -> Decimal:
    if stone_type in ("Taşsız", "Zirkon"):
        return ZERO
    if measure_unit == "gr":
        return ONE
    if measure_unit == "mm":
        return Decimal("0.05")
    return Decimal("0.2")


def resolve_adjustment_lc(
    rule: AdjustmentInput,
    percent_base_lc: Decimal,
    lc_currency: str,
    fx_base_rates: dict[str, Decimal],
) -> Decimal:
    if rule.unit == "%":
        return (percent_base_lc * rule.value) / HUNDRED
    rate = get_matrix_rate(rule.unit, lc_currency, fx_base_rates)
    return rule.value * rate


def calculate_pricing(inp: PricingEngineInput) -> PricingEngineOutput:
    fineness = PURITY_FINENESS.get(inp.purity_code)
    if fineness is None:
        raise PricingEngineError(f"Desteklenmeyen maden ayarı: {inp.purity_code}")

    # 1. Physical weights, multi-stone count * carat tare & fire
    total_stone_carat = ZERO
    center_carat = ZERO
    has_center_line = False
    stone_tare_raw = ZERO

    for line in inp.stone_lines:
        if line.count < 0 or line.carat < ZERO:
            raise PricingEngineError("Taş adedi ve karat değeri negatif olamaz.")
        line_total_carat = Decimal(line.count) * line.carat
        total_stone_carat += line_total_carat
        if line.role == "MERKEZ":
            has_center_line = True
            center_carat += line_total_carat
        stone_tare_raw += line_total_carat * resolve_stone_tare_factor(line.stone_type, line.measure_unit)

    stone_tare_gram = q_gram(stone_tare_raw)
    net_metal_gram = max(ZERO, q_gram(inp.gross_weight_gram - stone_tare_gram))
    fine_metal_gram = q_gram(net_metal_gram * fineness)

    fire_rate = max(ZERO, inp.fire_rate_pct)
    fire_weight_gram = q_gram((net_metal_gram * fire_rate) / HUNDRED)
    fire_included_metal_gram = q_gram(net_metal_gram + fire_weight_gram)
    fire_included_fine_metal_gram = q_gram(fire_included_metal_gram * fineness)

    is_carat_within_mount_range = True
    if inp.mount_range is not None and inp.stone_lines:
        checked_carat = center_carat if has_center_line else total_stone_carat
        is_carat_within_mount_range = (
            inp.mount_range.allowed_carat_min <= checked_carat <= inp.mount_range.allowed_carat_max
        )
        if inp.enforce_mount_range and not is_carat_within_mount_range:
            raise MountCaratRangeError(
                f"Taş karatı ({q_gram(checked_carat)} ct) montür izin verilen aralığı "
                f"({inp.mount_range.allowed_carat_min}–{inp.mount_range.allowed_carat_max} ct) dışında."
            )

    # 2. Cost ledger lines (FC -> LC)
    lc = inp.lc_currency
    lc_to_try_rate = get_matrix_rate(lc, "TRY", inp.fx_base_rates)
    line_map = {line.line_type: line for line in inp.cost_lines}
    computed_lines: dict[str, ComputedLineResult] = {}

    def compute_line(line_type: str, default_fc: Decimal = ZERO) -> ComputedLineResult:
        raw = line_map.get(line_type)
        if raw is None:
            return ComputedLineResult(
                line_type=line_type,
                fc_currency=lc,
                fc_price=default_fc,
                matrix_rate=ONE,
                effective_rate=ONE,
                is_rate_overridden=False,
                lc_price=q_money(default_fc),
            )

        if line_type == "MADEN" and raw.fc_price_manual is None:
            if inp.has_gold_try_per_gram <= ZERO:
                raise MissingRateError("Otomatik maden hesabı için geçerli Has Altın TL/gr kuru zorunludur.")
            metal_fc_try = get_matrix_rate(raw.fc_currency, "TRY", inp.fx_base_rates)
            fc_price = (fire_included_fine_metal_gram * inp.has_gold_try_per_gram) / metal_fc_try
        elif line_type == "MADEN" and raw.fc_price_manual is not None:
            fc_price = raw.fc_price_manual
        else:
            fc_price = max(ZERO, raw.fc_price)

        matrix_rate = get_matrix_rate(raw.fc_currency, lc, inp.fx_base_rates)
        is_overridden = raw.rate_override is not None
        effective_rate = raw.rate_override if is_overridden else matrix_rate
        lc_price = fc_price * effective_rate

        return ComputedLineResult(
            line_type=line_type,
            fc_currency=raw.fc_currency,
            fc_price=q_money(fc_price),
            matrix_rate=matrix_rate.quantize(RATE_Q, rounding=ROUND_HALF_UP),
            effective_rate=effective_rate.quantize(RATE_Q, rounding=ROUND_HALF_UP),
            is_rate_overridden=is_overridden,
            lc_price=lc_price,
        )

    if inp.pricing_mode == "1":
        for key in ("MADEN", "ISCILIK", "TAS", "MONTUR", "DIGER"):
            computed_lines[key] = compute_line(key)
        total_cost_lc = sum((computed_lines[k].lc_price for k in ("MADEN", "ISCILIK", "TAS", "MONTUR", "DIGER")), ZERO)
    else:
        computed_lines["TEDARIKCI"] = compute_line("TEDARIKCI")
        total_cost_lc = computed_lines["TEDARIKCI"].lc_price

    # 3. Dynamic channel rules (B2B / B2B_API / B2C_API) + Servis Bedeli
    computed_channels: dict[str, ComputedChannelResult] = {}
    for rule in inp.channel_rules:
        profit_lc = resolve_adjustment_lc(rule.profit, total_cost_lc, lc, inp.fx_base_rates)
        ara_toplam_lc = total_cost_lc + profit_lc
        discount_lc = resolve_adjustment_lc(rule.discount, ara_toplam_lc, lc, inp.fx_base_rates)
        net_satis_lc = max(ZERO, ara_toplam_lc - discount_lc)
        servis_bedeli_lc = resolve_adjustment_lc(rule.servis_bedeli, total_cost_lc, lc, inp.fx_base_rates)
        nihai_fiyat_lc = net_satis_lc + servis_bedeli_lc
        nihai_fiyat_try = nihai_fiyat_lc * lc_to_try_rate
        liste_fiyati_try = (ara_toplam_lc + servis_bedeli_lc) * lc_to_try_rate
        discount_try = discount_lc * lc_to_try_rate
        effective_discount_pct = (
            ((discount_try / liste_fiyati_try) * HUNDRED).quantize(MONEY_Q, rounding=ROUND_HALF_UP)
            if liste_fiyati_try > ZERO
            else ZERO
        )

        computed_channels[rule.channel] = ComputedChannelResult(
            channel=rule.channel,
            profit_lc=q_money(profit_lc),
            ara_toplam_lc=q_money(ara_toplam_lc),
            discount_lc=q_money(discount_lc),
            net_satis_lc=q_money(net_satis_lc),
            servis_bedeli_lc=q_money(servis_bedeli_lc),
            nihai_fiyat_lc=q_money(nihai_fiyat_lc),
            nihai_fiyat_try=q_money(nihai_fiyat_try),
            liste_fiyati_try=q_money(liste_fiyati_try),
            effective_discount_pct=effective_discount_pct,
        )

    return PricingEngineOutput(
        fineness=fineness,
        total_stone_carat=q_gram(total_stone_carat),
        stone_tare_gram=stone_tare_gram,
        net_metal_gram=net_metal_gram,
        fine_metal_gram=fine_metal_gram,
        fire_weight_gram=fire_weight_gram,
        fire_included_metal_gram=fire_included_metal_gram,
        fire_included_fine_metal_gram=fire_included_fine_metal_gram,
        is_carat_within_mount_range=is_carat_within_mount_range,
        lc_currency=lc,
        lc_to_try_rate=lc_to_try_rate.quantize(RATE_Q, rounding=ROUND_HALF_UP),
        lines={
            k: ComputedLineResult(
                line_type=v.line_type,
                fc_currency=v.fc_currency,
                fc_price=v.fc_price,
                matrix_rate=v.matrix_rate,
                effective_rate=v.effective_rate,
                is_rate_overridden=v.is_rate_overridden,
                lc_price=q_money(v.lc_price),
            )
            for k, v in computed_lines.items()
        },
        total_cost_lc=q_money(total_cost_lc),
        channels=computed_channels,
    )

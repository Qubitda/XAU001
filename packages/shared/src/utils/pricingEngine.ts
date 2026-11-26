import {
  AdjustmentRule,
  AudienceRole,
  ChannelPricingRule,
  ComputedChannelPricing,
  ComputedJewelryMetrics,
  ComputedLedgerLine,
  FxBaseRates,
  FxCurrencyCode,
  LiveRates,
  MetalColor,
  PricingCurrency,
  ProductState,
  PurityCode,
  StoneLineItem,
  StoneMeasureUnit,
  StoneType,
} from '../types/jewelry';

export interface StoneUnitGuideRow {
  stoneType: StoneType;
  allowedUnitsLabel: string;
  defaultUnit: StoneMeasureUnit;
}

export const STONE_UNIT_GUIDE: StoneUnitGuideRow[] = [
  { stoneType: 'Pırlanta', allowedUnitsLabel: 'Karat (ct)', defaultUnit: 'ct' },
  { stoneType: 'Zümrüt', allowedUnitsLabel: 'Karat (ct) / mm', defaultUnit: 'ct' },
  { stoneType: 'Yakut', allowedUnitsLabel: 'Karat (ct) / mm', defaultUnit: 'ct' },
  { stoneType: 'Safir', allowedUnitsLabel: 'Karat (ct) / mm', defaultUnit: 'ct' },
  { stoneType: 'Doğal Zirkon', allowedUnitsLabel: 'Karat (ct) / mm', defaultUnit: 'ct' },
  { stoneType: 'Turkuaz', allowedUnitsLabel: 'mm / ct / gram', defaultUnit: 'ct' },
  { stoneType: 'Kehribar', allowedUnitsLabel: 'Gram (gr) / mm', defaultUnit: 'gr' },
  { stoneType: 'Diğer taşlar', allowedUnitsLabel: 'Taşın ölçüm standardına göre', defaultUnit: 'ct' },
];

export function deriveSalesChannelsFromRules(rules: ChannelPricingRule[]): string[] {
  const seen = new Set<string>();
  const list: string[] = [];
  for (const r of rules) {
    const raw = r.channel as string;
    const ch = raw === 'B2C' || raw === 'BOTH' ? 'B2C_API' : r.channel;
    if (!seen.has(ch)) {
      seen.add(ch);
      list.push(ch);
    }
  }
  return list;
}

export function findChannelRule(
  rules: ChannelPricingRule[],
  target: 'B2B' | 'B2B_API' | 'B2C_API' | 'B2C'
): ChannelPricingRule | undefined {
  const normalized = target === 'B2C' ? 'B2C_API' : target;
  return rules.find((r) => r.channel === normalized);
}

export const FX_CURRENCIES: FxCurrencyCode[] = [
  'TRY',
  'USD',
  'EUR',
  'JPY',
  'GBP',
  'CNY',
  'AUD',
  'CAD',
  'CHF',
  'XAU',
  'XAG',
  'XPT',
  'XPD',
];

export const FX_CURRENCY_LABELS: Record<FxCurrencyCode, string> = {
  TRY: 'TRY (Türk Lirası)',
  USD: 'USD (Amerikan Doları)',
  EUR: 'EUR (Euro)',
  JPY: 'JPY (Japon Yeni)',
  GBP: 'GBP (İngiliz Sterlini)',
  CNY: 'CNY (Çin Yuanı)',
  AUD: 'AUD (Avustralya Doları)',
  CAD: 'CAD (Kanada Doları)',
  CHF: 'CHF (İsviçre Frangı)',
  XAU: 'XAU (Altın Ons)',
  XAG: 'XAG (Gümüş Ons)',
  XPT: 'XPT (Platin Ons)',
  XPD: 'XPD (Paladyum Ons)',
};

export const TROY_OZ_TO_GRAM = 31.1034768;

export const PURITY_MAP: Record<string, { value: number; fineness: number; label: string }> = {
  '8K': { value: 8, fineness: 0.333, label: '8 Ayar (333)' },
  '9K': { value: 9, fineness: 0.375, label: '9 Ayar (375)' },
  '10K': { value: 10, fineness: 0.417, label: '10 Ayar (417)' },
  '14K': { value: 14, fineness: 0.585, label: '14 Ayar (585)' },
  '18K': { value: 18, fineness: 0.75, label: '18 Ayar (750)' },
  '21K': { value: 21, fineness: 0.875, label: '21 Ayar (875)' },
  '22K': { value: 22, fineness: 0.916, label: '22 Ayar (916)' },
  '24K': { value: 24, fineness: 0.995, label: '24 Ayar Has (995)' },
  '24K_HAS': { value: 24, fineness: 0.995, label: '24K (Has)' },
  '24K_SAF': { value: 24, fineness: 0.999, label: '24K (Saf)' },
  '925': { value: 925, fineness: 0.925, label: '925 Ayar Gümüş' },
  '999': { value: 999, fineness: 0.999, label: '999 Has Gümüş' },
  '900': { value: 900, fineness: 0.9, label: '900 Platin' },
  '950': { value: 950, fineness: 0.95, label: '950 Platin/Paladyum' },
  AYARSIZ: { value: 0, fineness: 0, label: 'Ayarsız' },
};

export const COLOR_CODE_MAP: Record<string, string> = {
  Beyaz: 'BYZ',
  Sarı: 'SRY',
  Rose: 'RSE',
  'Rose (Kırmızı)': 'RSE',
  'İki Renkli (Beyaz-Sarı)': 'BYS',
  'İki Renkli (Beyaz-Rose)': 'BYR',
  'Üç Renkli': 'UCR',
  'Siyah (Zirkonyum)': 'SYH',
  'Doğal Metal Rengi': 'DGL',
};

/**
 * Computes exact cross-currency rate: 1 unit of `from` in `to` currency.
 * Derived deterministically from base TRY rates: baseTry[from] / baseTry[to].
 */
export function getMatrixRate(
  from: FxCurrencyCode,
  to: FxCurrencyCode,
  fxBaseRates: FxBaseRates
): number {
  if (from === to) return 1;
  const fromTry = fxBaseRates[from] ?? 1;
  const toTry = fxBaseRates[to] ?? 1;
  return toTry > 0 ? fromTry / toTry : 0;
}

export function getCurrencyToTryRate(currency: PricingCurrency, rates: LiveRates): number {
  switch (currency) {
    case 'USD':
      return rates.fxBaseRates.USD;
    case 'EUR':
      return rates.fxBaseRates.EUR;
    case 'HAS_ALTIN_GR':
      return rates.liveHasGoldTrySell;
    case 'TRY':
    default:
      return 1;
  }
}

export function getCurrencySymbol(currency: PricingCurrency | FxCurrencyCode): string {
  switch (currency) {
    case 'USD':
      return '$';
    case 'EUR':
      return '€';
    case 'GBP':
      return '£';
    case 'JPY':
      return '¥';
    case 'CHF':
      return 'CHF';
    case 'XAU':
      return 'XAU';
    case 'XAG':
      return 'XAG';
    case 'XPT':
      return 'XPT';
    case 'XPD':
      return 'XPD';
    case 'HAS_ALTIN_GR':
      return 'Has Gr';
    case 'TRY':
    default:
      return 'TL';
  }
}

export function formatTrNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number.isFinite(value) ? value : 0);
}

export function formatCurrencyValue(
  value: number,
  currency: PricingCurrency | FxCurrencyCode
): string {
  if (currency === 'TRY') return `${formatTrNumber(value, 2)} TL`;
  if (currency === 'USD') return `$${formatTrNumber(value, 2)}`;
  if (currency === 'EUR') return `€${formatTrNumber(value, 2)}`;
  if (currency === 'GBP') return `£${formatTrNumber(value, 2)}`;
  if (currency === 'HAS_ALTIN_GR') return `${formatTrNumber(value, 3)} Has Gr`;
  if (currency === 'XAU' || currency === 'XAG' || currency === 'XPT' || currency === 'XPD') {
    return `${formatTrNumber(value, 5)} ${currency}`;
  }
  return `${formatTrNumber(value, 2)} ${currency}`;
}

function resolveAdjustmentInLc(
  rule: AdjustmentRule,
  percentBaseLc: number,
  lcCurrency: FxCurrencyCode,
  fxBaseRates: FxBaseRates
): number {
  if (rule.unit === '%') {
    return (percentBaseLc * rule.value) / 100;
  }
  const convRate = getMatrixRate(rule.unit, lcCurrency, fxBaseRates);
  return rule.value * convRate;
}

function buildLedgerLine(
  currency: FxCurrencyCode,
  fcPrice: number,
  rateOverride: number | null,
  lcCurrency: FxCurrencyCode,
  fxBaseRates: FxBaseRates
): ComputedLedgerLine {
  const matrixRate = getMatrixRate(currency, lcCurrency, fxBaseRates);
  const isRateOverridden = rateOverride !== null && Number.isFinite(rateOverride);
  const effectiveRate = isRateOverridden ? (rateOverride as number) : matrixRate;
  return {
    currency,
    fcPrice,
    matrixRate,
    effectiveRate,
    isRateOverridden,
    lcPrice: fcPrice * effectiveRate,
  };
}

export function computeJewelryMetrics(
  product: ProductState,
  rates: LiveRates
): ComputedJewelryMetrics {
  const purity = PURITY_MAP[product.purityCode] ?? {
    value: 0,
    fineness: 0,
    label: product.purityCode,
  };
  const colorCode = COLOR_CODE_MAP[product.metalColor] ?? 'XXX';
  const fx = rates.fxBaseRates;

  const totalStoneCarat = Number((product.centerStoneCarat + product.sideStoneCarat).toFixed(2));
  const caratSkuPart = Math.round(totalStoneCarat * 100)
    .toString()
    .padStart(3, '0');

  const sku = `${product.parentSku}-${product.purityCode}-${colorCode}-${caratSkuPart}`;
  const optionKey = `${product.purityCode}|${colorCode}|${product.variantSize}|${totalStoneCarat.toFixed(2)}`;
  const displayWeightText = `${formatTrNumber(product.grossWeightGram, 2)} gr`;

  const resolveStoneTareFactor = (stoneType: StoneType, unit: StoneMeasureUnit): number => {
    if (stoneType === 'Taşsız' || stoneType === 'Zirkon') return 0;
    if (unit === 'gr') return 1;
    if (unit === 'mm') return 0.05;
    return 0.2;
  };

  // Taş Hesaplaması, Çoklu Taş Satırları, Ağırlık / Gramaj & Fire Hesaplaması
  const stoneUnit = product.stoneMeasureUnit ?? 'ct';
  const stoneTareFactor = resolveStoneTareFactor(product.stoneType, stoneUnit);

  const resolvedStoneLines: StoneLineItem[] =
    product.stoneLines && product.stoneLines.length > 0
      ? (() => {
          const centerLineCount = product.stoneLines.filter((l) => l.role === 'MERKEZ').length;
          return product.stoneLines.map((line) => {
            if (line.role === 'MERKEZ' && centerLineCount === 1) {
              const safeCount = Math.max(1, line.count || 1);
              return {
                ...line,
                count: safeCount,
                carat: Number((product.centerStoneCarat / safeCount).toFixed(4)),
              };
            }
            return line;
          });
        })()
      : [
          ...(product.centerStoneCarat > 0
            ? [
                {
                  id: `${product.parentSku}-center`,
                  role: 'MERKEZ' as const,
                  stoneType: product.stoneType,
                  measureUnit: stoneUnit,
                  count: Math.max(1, product.sideStoneCarat > 0 ? 1 : product.stoneCount),
                  carat: Number(
                    (
                      product.centerStoneCarat /
                      Math.max(1, product.sideStoneCarat > 0 ? 1 : product.stoneCount)
                    ).toFixed(4)
                  ),
                  clarity: product.stoneClarity,
                  colorGrade: product.stoneColorGrade,
                  cutShape: product.stoneCutShape,
                },
              ]
            : []),
          ...(product.sideStoneCarat > 0
            ? [
                {
                  id: `${product.parentSku}-side`,
                  role: 'YAN' as const,
                  stoneType: product.stoneType,
                  measureUnit: stoneUnit,
                  count: Math.max(1, product.stoneCount - 1),
                  carat: Number(
                    (product.sideStoneCarat / Math.max(1, product.stoneCount - 1)).toFixed(4)
                  ),
                  clarity: product.stoneClarity,
                  colorGrade: product.stoneColorGrade,
                  cutShape: product.stoneCutShape,
                },
              ]
            : []),
        ];

  const isCaratWithinMountRange = product.mountSpec
    ? product.centerStoneCarat >= product.mountSpec.allowedCaratMin &&
      product.centerStoneCarat <= product.mountSpec.allowedCaratMax
    : true;

  const stoneTareGram =
    product.stoneLines && product.stoneLines.length > 0
      ? Number(
          resolvedStoneLines
            .reduce(
              (acc, line) =>
                acc +
                Math.max(0, line.count) *
                  Math.max(0, line.carat) *
                  resolveStoneTareFactor(line.stoneType, line.measureUnit),
              0
            )
            .toFixed(4)
        )
      : Number((totalStoneCarat * stoneTareFactor).toFixed(4));
  const netMetalGram = Math.max(0, Number((product.grossWeightGram - stoneTareGram).toFixed(4)));
  const fineMetalGram = Number((netMetalGram * purity.fineness).toFixed(4));

  const fireRatePct = Math.max(0, product.fireRatePct ?? 0);
  const fireWeightGram = Number(((netMetalGram * fireRatePct) / 100).toFixed(4));
  const fireIncludedMetalGram = Number((netMetalGram + fireWeightGram).toFixed(4));
  const fireIncludedFineMetalGram = Number((fireIncludedMetalGram * purity.fineness).toFixed(4));

  // Has Altın TL/Gr
  const hasGoldTryPerGram = rates.liveHasGoldTrySell;
  const liveHasGoldUsdSell = fx.USD > 0 ? hasGoldTryPerGram / fx.USD : 0;
  const selectedCurrencyToTry = getCurrencyToTryRate(product.pricingCurrency, rates);

  // =========================================================================
  // ÇAPRAZ KUR MATRİSİ & FC → LC SATIR BAZLI FİYATLANDIRMA MOTORU
  // (Kör Havuz koruması: B2C/B2B API yanıtlarında ledger gizliyse sunucu fiyatını kullanır)
  // =========================================================================
  const cfg = product.ledger;
  if (!cfg) {
    const lc: FxCurrencyCode = product.b2bPricing?.lcCurrency ?? 'TRY';
    const lcToTryRate = getMatrixRate(lc, 'TRY', fx);
    const emptyLine = buildLedgerLine(lc, 0, null, lc, fx);
    const b2cListPriceTry = product.b2cPricing?.listPriceTry ?? 0;
    const b2cFinalPriceTry = product.b2cPricing?.finalPriceTry ?? b2cListPriceTry;
    const b2cDiscountTry = Math.max(0, b2cListPriceTry - b2cFinalPriceTry);
    const effectiveB2cDiscountPct =
      product.b2cPricing?.effectiveDiscountPct ??
      (b2cListPriceTry > 0 ? Number(((b2cDiscountTry / b2cListPriceTry) * 100).toFixed(2)) : 0);

    const b2bFinalPriceTry = product.b2bPricing?.finalPriceTry ?? 0;
    const b2bFinalPriceLc = product.b2bPricing?.finalPriceLc ?? (lcToTryRate > 0 ? b2bFinalPriceTry / lcToTryRate : 0);
    const finalB2bPriceCurrency =
      selectedCurrencyToTry > 0 ? b2bFinalPriceTry / selectedCurrencyToTry : b2bFinalPriceLc;

    const srvNetMetal = product.metalSummary?.netMetalGram ?? netMetalGram;
    const srvFineMetal = product.metalSummary?.fineMetalGram ?? fineMetalGram;
    const srvFireFine = product.metalSummary?.fireIncludedFineMetalGram ?? fireIncludedFineMetalGram;

    const rawFineness = product.metalSummary?.fineness;
    const normalizedFineness =
      rawFineness != null ? (rawFineness > 1 ? rawFineness / 1000 : rawFineness) : purity.fineness;

    return {
      sku,
      optionKey,
      displayWeightText,
      purityValue: purity.value,
      millesimalFineness: normalizedFineness,
      totalStoneCarat,
      stoneTareFactor,
      stoneTareGram,
      resolvedStoneLines,
      isCaratWithinMountRange,
      netMetalGram: srvNetMetal,
      fineMetalGram: srvFineMetal,
      fireWeightGram: 0,
      fireIncludedMetalGram: srvNetMetal,
      fireIncludedFineMetalGram: srvFireFine,
      liveHasGoldUsdSell,
      selectedCurrencyToTry,
      ledger: {
        lcCurrency: lc,
        lcToTryRate,
        metalLine: emptyLine,
        metalAutoFcPrice: 0,
        laborLine: emptyLine,
        laborEffectiveGram: srvNetMetal,
        stoneLine: emptyLine,
        mountingLine: emptyLine,
        otherCostLine: emptyLine,
        supplierLine: emptyLine,
        totalCostLc: 0,
        channels: [],
        hasB2bChannel: product.b2bPricing?.finalPriceTry !== null && product.b2bPricing?.finalPriceTry !== undefined,
        hasB2cChannel: product.b2cPricing?.finalPriceTry !== null && product.b2cPricing?.finalPriceTry !== undefined,
        b2bProfitLc: 0,
        b2cProfitLc: 0,
        b2bDiscountLc: 0,
        b2cDiscountLc: 0,
        b2bSubtotalBeforeDiscountLc: 0,
        b2cSubtotalBeforeDiscountLc: 0,
        b2bTotalSalesLc: b2bFinalPriceLc,
        b2cTotalSalesLc: lcToTryRate > 0 ? b2cFinalPriceTry / lcToTryRate : b2cFinalPriceTry,
        b2bPlatformFeeLc: 0,
        b2cPlatformFeeLc: 0,
        platformFeeLc: 0,
        b2bFinalPriceLc,
        b2cFinalPriceLc: lcToTryRate > 0 ? b2cFinalPriceTry / lcToTryRate : b2cFinalPriceTry,
        b2bFinalPriceTry,
        b2cFinalPriceTry,
        b2cListPriceTry,
        b2cDiscountTry,
        effectiveB2cDiscountPct,
      },
      p1MetalCostTry: 0,
      p1TotalLaborCostTry: 0,
      p1StoneCostTry: 0,
      p1TotalCostTry: 0,
      p1TotalCostCurrency: 0,
      p1B2bPriceCurrency: finalB2bPriceCurrency,
      p1B2bPriceTry: b2bFinalPriceTry,
      p1B2cPriceTry: b2cListPriceTry,
      p2SupplierPriceTry: 0,
      p2B2bPriceCurrency: finalB2bPriceCurrency,
      p2B2bPriceTry: b2bFinalPriceTry,
      p2B2cPriceTry: b2cListPriceTry,
      finalB2bPriceCurrency,
      finalB2bPriceTry: b2bFinalPriceTry,
      finalB2cPriceTry: b2cListPriceTry,
      discountAmountTry: b2cDiscountTry,
      discountedB2cPriceTry: b2cFinalPriceTry,
    };
  }

  const lc = cfg.lcCurrency;
  const lcToTryRate = getMatrixRate(lc, 'TRY', fx);

  // 1. Maden Maliyeti (Otomatik: Fire Dahil Has Maden Ağırlığı × Has Altın TL ÷ seçili FC TRY kuru)
  const metalFcTryRate = fx[cfg.metalCurrency] ?? 1;
  const metalAutoFcPrice =
    metalFcTryRate > 0 ? (fireIncludedFineMetalGram * hasGoldTryPerGram) / metalFcTryRate : 0;
  const metalFcPrice =
    cfg.metalFcManual !== null && Number.isFinite(cfg.metalFcManual)
      ? cfg.metalFcManual
      : Number(metalAutoFcPrice.toFixed(2));

  const metalLine = buildLedgerLine(
    cfg.metalCurrency,
    metalFcPrice,
    cfg.metalRateOverride,
    lc,
    fx
  );

  // 2. Toplam İşçilik Maliyeti (doğrudan FC Fiyat × Kur → LC Fiyat)
  const laborEffectiveGram = netMetalGram;
  const laborFcPrice = Math.max(0, cfg.laborFcPrice ?? 0);
  const laborLine = buildLedgerLine(
    cfg.laborCurrency,
    laborFcPrice,
    cfg.laborRateOverride,
    lc,
    fx
  );

  // 3. Taş Maliyeti (bağımsız para birimi ve opsiyonel satır içi manuel kur)
  const stoneLine = buildLedgerLine(
    cfg.stoneCurrency,
    cfg.stoneFcPrice,
    cfg.stoneRateOverride,
    lc,
    fx
  );

  // 4. Montür Maliyeti
  const mountingLine = buildLedgerLine(
    cfg.mountingCurrency ?? 'TRY',
    cfg.mountingFcPrice ?? 0,
    cfg.mountingRateOverride ?? null,
    lc,
    fx
  );

  // 5. Diğer Maliyetler
  const otherCostLine = buildLedgerLine(
    cfg.otherCostCurrency ?? 'TRY',
    cfg.otherCostFcPrice ?? 0,
    cfg.otherCostRateOverride ?? null,
    lc,
    fx
  );

  // Model 2 (Sade Tedarikçi Hazır Fiyatı)
  const supplierLine = buildLedgerLine(
    cfg.supplierCurrency,
    cfg.supplierFcPrice,
    cfg.supplierRateOverride,
    lc,
    fx
  );

  // Toplam Maliyet (LC)
  const totalCostLc =
    product.pricingMode === '1'
      ? metalLine.lcPrice +
        laborLine.lcPrice +
        stoneLine.lcPrice +
        mountingLine.lcPrice +
        otherCostLine.lcPrice
      : supplierLine.lcPrice;

  // Dinamik Satış Kanalı Kuralları Hesabı (B2B, B2C veya Her İkisi)
  const computedChannels: ComputedChannelPricing[] = cfg.channelRules.map((rule) => {
    const profitLc = resolveAdjustmentInLc(rule.profit, totalCostLc, lc, fx);
    const subtotalBeforeDiscountLc = totalCostLc + profitLc;
    const discountLc = resolveAdjustmentInLc(rule.discount, subtotalBeforeDiscountLc, lc, fx);
    const totalSalesLc = Math.max(0, subtotalBeforeDiscountLc - discountLc);
    const platformFeeLc = resolveAdjustmentInLc(rule.platformFee, totalCostLc, lc, fx);
    const finalPriceLc = totalSalesLc + platformFeeLc;
    const finalPriceTry = finalPriceLc * lcToTryRate;
    const listPriceTry = (subtotalBeforeDiscountLc + platformFeeLc) * lcToTryRate;
    const discountTry = discountLc * lcToTryRate;
    const effectiveDiscountPct =
      listPriceTry > 0 ? Number(((discountTry / listPriceTry) * 100).toFixed(2)) : 0;

    return {
      id: rule.id,
      channel: rule.channel,
      profitLc,
      discountLc,
      subtotalBeforeDiscountLc,
      totalSalesLc,
      platformFeeLc,
      finalPriceLc,
      finalPriceTry,
      listPriceTry,
      discountTry,
      effectiveDiscountPct,
    };
  });

  const resolvedB2b =
    computedChannels.find((c) => c.channel === 'B2B') ??
    computedChannels.find((c) => c.channel === 'B2B_API');
  const resolvedB2c = computedChannels.find((c) => c.channel === 'B2C_API');

  const hasB2bChannel = Boolean(resolvedB2b);
  const hasB2cChannel = Boolean(resolvedB2c);

  const b2bProfitLc = resolvedB2b?.profitLc ?? 0;
  const b2cProfitLc = resolvedB2c?.profitLc ?? 0;
  const b2bDiscountLc = resolvedB2b?.discountLc ?? 0;
  const b2cDiscountLc = resolvedB2c?.discountLc ?? 0;
  const b2bSubtotalBeforeDiscountLc = resolvedB2b?.subtotalBeforeDiscountLc ?? 0;
  const b2cSubtotalBeforeDiscountLc = resolvedB2c?.subtotalBeforeDiscountLc ?? 0;
  const b2bTotalSalesLc = resolvedB2b?.totalSalesLc ?? 0;
  const b2cTotalSalesLc = resolvedB2c?.totalSalesLc ?? 0;
  const b2bPlatformFeeLc = resolvedB2b?.platformFeeLc ?? 0;
  const b2cPlatformFeeLc = resolvedB2c?.platformFeeLc ?? 0;
  const platformFeeLc = resolvedB2c?.platformFeeLc ?? resolvedB2b?.platformFeeLc ?? 0;
  const b2bFinalPriceLc = resolvedB2b?.finalPriceLc ?? 0;
  const b2cFinalPriceLc = resolvedB2c?.finalPriceLc ?? 0;
  const b2bFinalPriceTry = resolvedB2b?.finalPriceTry ?? 0;
  const b2cFinalPriceTry = resolvedB2c?.finalPriceTry ?? 0;
  const b2cListPriceTry = resolvedB2c?.listPriceTry ?? 0;
  const b2cDiscountTry = resolvedB2c?.discountTry ?? 0;
  const effectiveB2cDiscountPct = resolvedB2c?.effectiveDiscountPct ?? 0;

  // Model 1 & Model 2 özet TL eşlenikleri (Veri sözlüğü ve B2B/B2C kartlar için)
  const p1MetalCostTry = metalLine.lcPrice * lcToTryRate;
  const p1TotalLaborCostTry = laborLine.lcPrice * lcToTryRate;
  const p1StoneCostTry = stoneLine.lcPrice * lcToTryRate;
  const p1MountingCostTry = mountingLine.lcPrice * lcToTryRate;
  const p1OtherCostTry = otherCostLine.lcPrice * lcToTryRate;
  const p1TotalCostTry =
    p1MetalCostTry + p1TotalLaborCostTry + p1StoneCostTry + p1MountingCostTry + p1OtherCostTry;
  const p1TotalCostCurrency =
    selectedCurrencyToTry > 0 ? p1TotalCostTry / selectedCurrencyToTry : 0;

  const p2SupplierPriceTry = supplierLine.lcPrice * lcToTryRate;

  const finalB2bPriceCurrency =
    selectedCurrencyToTry > 0 ? b2bFinalPriceTry / selectedCurrencyToTry : b2bFinalPriceLc;

  return {
    sku,
    optionKey,
    displayWeightText,
    purityValue: purity.value,
    millesimalFineness: purity.fineness,
    totalStoneCarat,
    stoneTareFactor,
    stoneTareGram,
    resolvedStoneLines,
    isCaratWithinMountRange,
    netMetalGram,
    fineMetalGram,
    fireWeightGram,
    fireIncludedMetalGram,
    fireIncludedFineMetalGram,
    liveHasGoldUsdSell,
    selectedCurrencyToTry,

    ledger: {
      lcCurrency: lc,
      lcToTryRate,
      metalLine,
      metalAutoFcPrice,
      laborLine,
      laborEffectiveGram,
      stoneLine,
      mountingLine,
      otherCostLine,
      supplierLine,
      totalCostLc,
      channels: computedChannels,
      hasB2bChannel,
      hasB2cChannel,
      b2bProfitLc,
      b2cProfitLc,
      b2bDiscountLc,
      b2cDiscountLc,
      b2bSubtotalBeforeDiscountLc,
      b2cSubtotalBeforeDiscountLc,
      b2bTotalSalesLc,
      b2cTotalSalesLc,
      b2bPlatformFeeLc,
      b2cPlatformFeeLc,
      platformFeeLc,
      b2bFinalPriceLc,
      b2cFinalPriceLc,
      b2bFinalPriceTry,
      b2cFinalPriceTry,
      b2cListPriceTry,
      b2cDiscountTry,
      effectiveB2cDiscountPct,
    },

    p1MetalCostTry,
    p1TotalLaborCostTry,
    p1StoneCostTry,
    p1TotalCostTry,
    p1TotalCostCurrency,
    p1B2bPriceCurrency: finalB2bPriceCurrency,
    p1B2bPriceTry: b2bFinalPriceTry,
    p1B2cPriceTry: b2cListPriceTry,

    p2SupplierPriceTry,
    p2B2bPriceCurrency: finalB2bPriceCurrency,
    p2B2bPriceTry: b2bFinalPriceTry,
    p2B2cPriceTry: b2cListPriceTry,

    finalB2bPriceCurrency,
    finalB2bPriceTry: b2bFinalPriceTry,
    finalB2cPriceTry: b2cListPriceTry,
    discountAmountTry: b2cDiscountTry,
    discountedB2cPriceTry: b2cFinalPriceTry,
  };
}

export function buildScopedJsonPayload(
  role: AudienceRole,
  product: ProductState,
  rates: LiveRates,
  computed: ComputedJewelryMetrics
): Record<string, unknown> {
  const basePublic: Record<string, unknown> = {
    product_type: product.productType,
    parent_sku: product.parentSku,
    barcode: product.barcode,
    sku: computed.sku,
    option_key: computed.optionKey,
    title: product.title,
    display_weight_text: computed.displayWeightText,
    description: product.description,
    taxonomy: {
      collection: product.collection,
      category: product.category,
      sub_category: product.subCategory,
      metal_color: product.metalColor,
      style_technique: product.styleTechnique,
      occasion: product.occasion,
      age_group: product.ageGroup,
    },
    availability: {
      sales_channels: product.salesChannels,
      stock_status: product.stockStatus,
      lead_time_days: product.leadTimeDays,
    },
    metal: {
      metal_name: product.metalName,
      purity_code: product.purityCode,
      gross_weight_gram: product.grossWeightGram,
    },
    pricing: {
      lc_currency: computed.ledger.lcCurrency,
      final_b2c_price_try: Number(computed.finalB2cPriceTry.toFixed(2)),
      discount_rate_pct: computed.ledger.effectiveB2cDiscountPct,
      discount_amount_try: Number(computed.discountAmountTry.toFixed(2)),
      discounted_b2c_price_try: Number(computed.discountedB2cPriceTry.toFixed(2)),
    },
    stone_certificate: {
      stone_type: product.stoneType,
      stone_count: product.stoneCount,
      center_stone_carat: product.centerStoneCarat,
      side_stone_carat: product.sideStoneCarat,
      total_stone_carat: computed.totalStoneCarat,
      stone_cut_shape: product.stoneCutShape,
      stone_clarity: product.stoneClarity,
      stone_color_grade: product.stoneColorGrade,
      stone_cut_grade: product.stoneCutGrade,
      stone_origin: product.stoneOrigin,
      setting_type: product.settingType,
      has_certificate: product.hasCertificate,
      certificate_agency: product.certificateAgency,
      certificate_number: product.certificateNumber,
      certificate_file_url: product.certificateFileUrl,
    },
    dimensions: {
      variant_size: product.variantSize,
      available_sizes: product.availableSizes,
      width_mm: product.widthMm,
      thickness_mm: product.thicknessMm,
      height_mm: product.heightMm,
      chain_type: product.chainType,
      clasp_type: product.claspType,
      is_resizable: product.isResizable,
      size_guide_url: product.sizeGuideUrl,
    },
    media: {
      gallery_images: product.galleryImages,
      reels_video_9x16_url: product.reelsVideoUrl,
      spin_360_url: product.spin360Url,
      social_share_caption: product.socialShareCaption,
    },
    policies: {
      warranty_months: product.warrantyMonths,
      lifetime_maintenance: product.lifetimeMaintenance,
      insured_shipping_info: product.insuredShippingInfo,
      return_policy_text: product.returnPolicyText,
    },
  };

  if (role === 'b2c') {
    return {
      _scope: 'B2C_STOREFRONT_API',
      ...basePublic,
      seo: {
        seo_slug: product.seoSlug,
        meta_title: product.metaTitle,
      },
    };
  }

  const b2bPayload: Record<string, unknown> = {
    _scope: 'B2B_DEALER_PORTAL_API',
    ...basePublic,
    availability: {
      ...(basePublic.availability as Record<string, unknown>),
      ownership_type: product.ownershipType,
      stock_qty: product.stockQty,
    },
    metal: {
      ...(basePublic.metal as Record<string, unknown>),
      millesimal_fineness: computed.millesimalFineness,
      net_metal_gram: computed.netMetalGram,
      fine_metal_gram: computed.fineMetalGram,
    },
    live_rates_snapshot: {
      snapshot_id: rates.snapshotId,
      fx_base_try_rates: rates.fxBaseRates,
      live_has_gold_try_sell: rates.liveHasGoldTrySell,
      live_has_gold_usd_sell: Number(computed.liveHasGoldUsdSell.toFixed(4)),
    },
    pricing: {
      ...(basePublic.pricing as Record<string, unknown>),
      final_b2b_price_lc: Number(computed.ledger.b2bFinalPriceLc.toFixed(2)),
      final_b2b_price_currency: Number(computed.finalB2bPriceCurrency.toFixed(2)),
      final_b2b_price_try: Number(computed.finalB2bPriceTry.toFixed(2)),
    },
    b2b_catalog_tools: {
      catalog_clean_image_url: product.catalogCleanImageUrl,
      b2b_share_permission: product.b2bSharePermission,
      dynamic_dealer_watermark: product.dynamicDealerWatermark,
      b2b_catalog_share_endpoint: product.b2bCatalogShareEndpoint,
    },
  };

  if (role === 'b2b') {
    return b2bPayload;
  }

  return {
    _scope: 'ERP_INTERNAL_FULL_RECORD',
    ...b2bPayload,
    internal_audit: {
      created_by: product.createdBy,
      supplier_name: product.supplierName,
      warehouse_location: product.warehouseLocation,
      marketplace_category: product.marketplaceCategory,
      purity_value: computed.purityValue,
      stone_tare_factor: computed.stoneTareFactor,
      stone_tare_gram: computed.stoneTareGram,
    },
    internal_fx_ledger: {
      pricing_mode:
        product.pricingMode === '1'
          ? '1 - Detaylı (Maden + İşçilik + Taş)'
          : '2 - Sade (Tedarikçi Hazır Fiyatı)',
      lc_currency: computed.ledger.lcCurrency,
      cost_lines: {
        metal: {
          fc_currency: computed.ledger.metalLine.currency,
          fc_price: Number(computed.ledger.metalLine.fcPrice.toFixed(2)),
          rate_used: Number(computed.ledger.metalLine.effectiveRate.toFixed(4)),
          rate_overridden: computed.ledger.metalLine.isRateOverridden,
          lc_price: Number(computed.ledger.metalLine.lcPrice.toFixed(2)),
        },
        labor: {
          fc_currency: computed.ledger.laborLine.currency,
          fc_price: Number(computed.ledger.laborLine.fcPrice.toFixed(2)),
          rate_used: Number(computed.ledger.laborLine.effectiveRate.toFixed(4)),
          rate_overridden: computed.ledger.laborLine.isRateOverridden,
          lc_price: Number(computed.ledger.laborLine.lcPrice.toFixed(2)),
        },
        stone: {
          fc_currency: computed.ledger.stoneLine.currency,
          fc_price: Number(computed.ledger.stoneLine.fcPrice.toFixed(2)),
          rate_used: Number(computed.ledger.stoneLine.effectiveRate.toFixed(4)),
          rate_overridden: computed.ledger.stoneLine.isRateOverridden,
          lc_price: Number(computed.ledger.stoneLine.lcPrice.toFixed(2)),
        },
        mounting: {
          fc_currency: computed.ledger.mountingLine.currency,
          fc_price: Number(computed.ledger.mountingLine.fcPrice.toFixed(2)),
          rate_used: Number(computed.ledger.mountingLine.effectiveRate.toFixed(4)),
          rate_overridden: computed.ledger.mountingLine.isRateOverridden,
          lc_price: Number(computed.ledger.mountingLine.lcPrice.toFixed(2)),
        },
        other_costs: {
          fc_currency: computed.ledger.otherCostLine.currency,
          fc_price: Number(computed.ledger.otherCostLine.fcPrice.toFixed(2)),
          rate_used: Number(computed.ledger.otherCostLine.effectiveRate.toFixed(4)),
          rate_overridden: computed.ledger.otherCostLine.isRateOverridden,
          lc_price: Number(computed.ledger.otherCostLine.lcPrice.toFixed(2)),
        },
      },
      fire_calculation: {
        fire_rate_pct: product.fireRatePct,
        fire_weight_gram: computed.fireWeightGram,
        fire_included_metal_gram: computed.fireIncludedMetalGram,
        fire_included_fine_metal_gram: computed.fireIncludedFineMetalGram,
      },
      total_cost_lc: Number(computed.ledger.totalCostLc.toFixed(2)),
      sales_channel_rules: product.ledger.channelRules.map((rule) => {
        const calc = computed.ledger.channels.find((c) => c.id === rule.id);
        return {
          channel: rule.channel,
          profit: { ...rule.profit, lc_amount: Number((calc?.profitLc ?? 0).toFixed(2)) },
          discount: { ...rule.discount, lc_amount: Number((calc?.discountLc ?? 0).toFixed(2)) },
          platform_fee: { ...rule.platformFee, lc_amount: Number((calc?.platformFeeLc ?? 0).toFixed(2)) },
          total_sales_lc: Number((calc?.totalSalesLc ?? 0).toFixed(2)),
          final_price_lc: Number((calc?.finalPriceLc ?? 0).toFixed(2)),
          final_price_try: Number((calc?.finalPriceTry ?? 0).toFixed(2)),
        };
      }),
      active_channel_outputs: {
        b2b: computed.ledger.hasB2bChannel
          ? Number(computed.ledger.b2bFinalPriceLc.toFixed(2))
          : null,
        b2c: computed.ledger.hasB2cChannel
          ? Number(computed.ledger.b2cFinalPriceLc.toFixed(2))
          : null,
      },
    },
    seo: {
      seo_slug: product.seoSlug,
      meta_title: product.metaTitle,
    },
  };
}

/** Resolve product kind from explicit field or legacy productType label. */
export function resolveProductKind(
  product: Pick<ProductState, 'productKind' | 'productType'>
): 'FINISHED' | 'MOUNTING' | 'LOOSE_STONE' {
  if (product.productKind) return product.productKind;
  const t = (product.productType || '').toLowerCase();
  if (t.includes('montür') || t.includes('montur') || t.includes('yarı')) return 'MOUNTING';
  if (t.includes('taş') || t.includes('tas ') || t.startsWith('taş')) return 'LOOSE_STONE';
  return 'FINISHED';
}

/**
 * Client-side mirror of backend type strategies (PRICING_READ_FROM_DETAILS).
 * Returns base cost TRY estimate before channel rules.
 */
export function estimateTypeBaseCostTry(
  product: ProductState,
  rates: { hasGoldTryPerGram: number; usdTry: number }
): {
  kind: 'FINISHED' | 'MOUNTING' | 'LOOSE_STONE';
  baseCostTry: number;
  pureGoldEquivalent: number;
  laborOnlyUsd: number;
} {
  const kind = resolveProductKind(product);
  if (kind === 'LOOSE_STONE') {
    const net = product.looseStoneDetail?.netCostUsd ?? product.ledger.stoneFcPrice ?? 0;
    return {
      kind,
      baseCostTry: net * rates.usdTry,
      pureGoldEquivalent: 0,
      laborOnlyUsd: 0,
    };
  }
  if (kind === 'MOUNTING' && product.mountingDetail) {
    const d = product.mountingDetail;
    const pure = d.netWeightGr * d.fineness;
    const laborUsd =
      d.laborCostType === 'PER_GRAM' ? d.netWeightGr * d.laborCostValue : d.laborCostValue;
    return {
      kind,
      baseCostTry: pure * rates.hasGoldTryPerGram + laborUsd * rates.usdTry,
      pureGoldEquivalent: pure,
      laborOnlyUsd: laborUsd,
    };
  }
  if (kind === 'FINISHED' && product.finishedDetail) {
    const d = product.finishedDetail;
    const pure = d.baseWeightGr * d.fineness;
    const laborUsd =
      d.laborCostType === 'PER_GRAM' ? d.baseWeightGr * d.laborCostValue : d.laborCostValue;
    return {
      kind,
      baseCostTry:
        pure * rates.hasGoldTryPerGram +
        laborUsd * rates.usdTry +
        (d.fixedStoneCostUsd || 0) * rates.usdTry,
      pureGoldEquivalent: pure,
      laborOnlyUsd: laborUsd,
    };
  }
  // Legacy fallback: use ledger totals already computed elsewhere
  return { kind, baseCostTry: 0, pureGoldEquivalent: 0, laborOnlyUsd: 0 };
}

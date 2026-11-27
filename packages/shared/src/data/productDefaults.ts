/**
 * Structural blank defaults for forms and optimistic merges.
 * These are NOT catalog/sample data — all domain values start empty/zero.
 * Seed/demo catalog lives only under demoMockHandler + jewelryData (demo opt-in).
 */
import type {
  FxBaseRates,
  LiveRates,
  PricingLedgerConfig,
  ProductState,
} from '../types/jewelry';
import { FX_CURRENCIES } from '../utils/pricingEngine';

export function createEmptyFxBaseRates(): FxBaseRates {
  const rates = {} as FxBaseRates;
  for (const code of FX_CURRENCIES) {
    rates[code] = code === 'TRY' ? 1 : 0;
  }
  return rates;
}

export function createEmptyLedger(): PricingLedgerConfig {
  return {
    lcCurrency: 'TRY',
    metalCurrency: 'USD',
    metalFcManual: null,
    metalRateOverride: null,
    laborCurrency: 'EUR',
    laborFcPrice: 0,
    laborUnitFee: 0,
    laborGramOverride: null,
    laborRateOverride: null,
    stoneCurrency: 'USD',
    stoneFcPrice: 0,
    stoneRateOverride: null,
    mountingCurrency: 'TRY',
    mountingFcPrice: 0,
    mountingRateOverride: null,
    otherCostCurrency: 'TRY',
    otherCostFcPrice: 0,
    otherCostRateOverride: null,
    supplierCurrency: 'USD',
    supplierFcPrice: 0,
    supplierRateOverride: null,
    channelRules: [],
  };
}

export function createEmptyRates(): LiveRates {
  return {
    sourceMode: 'auto',
    entryUsdRate: 0,
    entryHasGoldTry: 0,
    liveUsdSell: 0,
    liveEurSell: 0,
    liveHasGoldTrySell: 0,
    fxBaseRates: createEmptyFxBaseRates(),
    snapshotId: '',
    updatedAt: '',
  };
}

/** Blank product draft for create forms — no sample jewelry content. */
export function createBlankProduct(overrides: Partial<ProductState> = {}): ProductState {
  const parentSku =
    overrides.parentSku ?? `KY${Math.floor(100 + Math.random() * 899)}`;
  return {
    catalogStatus: 'DRAFT',
    visualType: 'solitaire_ring',
    variantCount: 0,
    availableColors: [],
    productType: '',
    productKind: 'FINISHED',
    parentSku,
    barcode: overrides.barcode ?? `P${Math.floor(700000 + Math.random() * 299999)}`,
    title: '',
    createdBy: '',
    description: '',
    collection: '',
    category: '',
    subCategory: '',
    metalColor: '' as ProductState['metalColor'],
    styleTechnique: '',
    occasion: '',
    ageGroup: '',
    salesChannels: [],
    supplierName: '',
    ownershipType: 'Öz Mal',
    stockStatus: 'Stokta',
    stockQty: 0,
    warehouseLocation: '',
    leadTimeDays: 0,
    metalName: '',
    purityCode: '' as ProductState['purityCode'],
    mountSpec: {
      structure: 'FULL',
      allowedCaratMin: 0,
      allowedCaratMax: 0,
      headCode: '',
      bandCode: '',
      headWeightGram: 0,
      bandWeightGram: 0,
    },
    centerStoneCarat: 0,
    sideStoneCarat: 0,
    grossWeightGram: 0,
    fireRatePct: 0,
    stoneMeasureUnit: 'ct',
    stoneLines: [],
    pricingMode: '1',
    pricingCurrency: 'TRY',
    ledger: createEmptyLedger(),
    p1UnitLaborFee: 0,
    p1StoneCostCurrency: 0,
    p1B2bMarginPct: 0,
    p1B2cMarginPct: 0,
    p1PlatformFeeTry: 0,
    p2SupplierPriceCurrency: 0,
    p2B2bMarginPct: 0,
    p2B2cMarginPct: 0,
    p2PlatformFeeTry: 0,
    discountRatePct: 0,
    stoneType: '' as ProductState['stoneType'],
    stoneCount: 0,
    stoneCutShape: '',
    stoneClarity: '',
    stoneColorGrade: '',
    stoneCutGrade: '',
    stoneOrigin: '',
    settingType: '',
    hasCertificate: false,
    certificateAgency: '',
    certificateNumber: '',
    certificateFileUrl: '',
    variantSize: 0,
    availableSizes: [],
    widthMm: 0,
    thicknessMm: 0,
    heightMm: 0,
    chainType: '',
    claspType: '',
    isResizable: false,
    sizeGuideUrl: '',
    galleryImages: [],
    reelsVideoUrl: '',
    spin360Url: '',
    catalogCleanImageUrl: '',
    b2bSharePermission: '',
    dynamicDealerWatermark: false,
    socialShareCaption: '',
    b2bCatalogShareEndpoint: '',
    warrantyMonths: 0,
    lifetimeMaintenance: '',
    insuredShippingInfo: '',
    returnPolicyText: '',
    seoSlug: '',
    metaTitle: '',
    marketplaceCategory: '',
    ...overrides,
  };
}

export function cloneLedger(ledger?: PricingLedgerConfig | null): PricingLedgerConfig {
  const src = ledger ?? createEmptyLedger();
  return {
    ...src,
    channelRules: (src.channelRules ?? []).map((r) => ({
      ...r,
      profit: { ...r.profit },
      discount: { ...r.discount },
      platformFee: { ...r.platformFee },
    })),
  };
}

/** Ensure select still shows the product's current value while defs load / if inactive. */
export function withCurrentValue<T extends string>(options: T[], current: T | string): T[] {
  if (!current) return options;
  if (options.some((o) => o === current)) return options;
  return [current as T, ...options];
}

export function withCurrentSelectOption(
  options: { value: string; label: string }[],
  current: string
): { value: string; label: string }[] {
  if (!current) return options;
  if (options.some((o) => o.value === current)) return options;
  return [{ value: current, label: current }, ...options];
}

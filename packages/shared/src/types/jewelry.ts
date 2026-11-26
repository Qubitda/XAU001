export type ActiveTab = 'vitrin' | 'product' | 'pricing' | 'architecture' | 'dictionary';

export type JewelryVisualType =
  | 'solitaire_ring'
  | 'baguette_ring'
  | 'pendant_necklace'
  | 'tennis_bracelet'
  | 'emerald_earring'
  | 'eternity_ring';

export type AudienceRole = 'erp' | 'b2b' | 'b2c';

export type PricingCurrency = 'USD' | 'TRY' | 'EUR' | 'HAS_ALTIN_GR';

export type FxCurrencyCode =
  | 'TRY'
  | 'USD'
  | 'EUR'
  | 'JPY'
  | 'GBP'
  | 'CNY'
  | 'AUD'
  | 'CAD'
  | 'CHF'
  | 'XAU'
  | 'XAG'
  | 'XPT'
  | 'XPD';

export type FxBaseRates = Record<FxCurrencyCode, number>;

export type AdjustmentUnit = '%' | FxCurrencyCode;

export interface AdjustmentRule {
  unit: AdjustmentUnit;
  value: number;
}

/** Hardcoded product sales channels (ops flow). No BOTH / free-form channels. */
export type PricingChannelTarget = 'B2B' | 'B2B_API' | 'B2C_API';

export interface ChannelPricingRule {
  id: string;
  channel: PricingChannelTarget;
  profit: AdjustmentRule;
  discount: AdjustmentRule;
  platformFee: AdjustmentRule;
}

export interface PricingLedgerConfig {
  lcCurrency: FxCurrencyCode;

  // Line 1: Maden Maliyeti
  metalCurrency: FxCurrencyCode;
  metalFcManual: number | null; // null = Has Altın × Milyem'den otomatik hesaplanır
  metalRateOverride: number | null; // null = Çapraz kur tablosundan otomatik gelir

  // Line 2: Toplam İşçilik Maliyeti (doğrudan FC fiyat girişi)
  laborCurrency: FxCurrencyCode;
  laborFcPrice: number;
  laborUnitFee: number; // Geriye dönük uyumluluk
  laborGramOverride: number | null; // Geriye dönük uyumluluk
  laborRateOverride: number | null;

  // Line 3: Taş Maliyeti
  stoneCurrency: FxCurrencyCode;
  stoneFcPrice: number;
  stoneRateOverride: number | null;

  // Line 4: Montür Maliyeti
  mountingCurrency: FxCurrencyCode;
  mountingFcPrice: number;
  mountingRateOverride: number | null;

  // Line 5: Diğer Maliyetler
  otherCostCurrency: FxCurrencyCode;
  otherCostFcPrice: number;
  otherCostRateOverride: number | null;

  // Model 2 (Sade Tedarikçi Tek Kalem)
  supplierCurrency: FxCurrencyCode;
  supplierFcPrice: number;
  supplierRateOverride: number | null;

  // Dinamik Satış Kanalı Fiyatlandırma Kuralları (B2B / B2B_API / B2C_API)
  channelRules: ChannelPricingRule[];
}

export type PricingMode = '1' | '2';

export type RateSourceMode = 'auto' | 'manual';

export type PurityCode =
  | '8K'
  | '9K'
  | '10K'
  | '14K'
  | '18K'
  | '21K'
  | '22K'
  | '24K'
  | '24K_HAS'
  | '24K_SAF'
  | '925'
  | '999'
  | '900'
  | '950'
  | 'AYARSIZ'
  | (string & {});

export type MetalColor = 'Beyaz' | 'Sarı' | 'Rose' | (string & {});

export type StoneType =
  | 'Pırlanta'
  | 'Safir'
  | 'Yakut'
  | 'Zümrüt'
  | 'Doğal Zirkon'
  | 'Turkuaz'
  | 'Kehribar'
  | 'Diğer taşlar'
  | 'Zirkon'
  | 'Taşsız';

export type StoneMeasureUnit = 'ct' | 'gr' | 'mm';

export type VisibilityLevel = 'EVET' | 'EVET (Pırlantada)' | 'HAYIR (Gizli)';

export interface LiveRates {
  sourceMode: RateSourceMode;
  entryUsdRate: number;
  entryHasGoldTry: number;
  liveUsdSell: number;
  liveEurSell: number;
  liveHasGoldTrySell: number;
  fxBaseRates: FxBaseRates;
  snapshotId: string;
  updatedAt: string;
}

export type MountStructureType = 'FULL' | 'HEAD_BAND';

export interface MountSpec {
  structure: MountStructureType;
  allowedCaratMin: number;
  allowedCaratMax: number;
  headCode?: string;
  bandCode?: string;
  headWeightGram?: number;
  bandWeightGram?: number;
}

export type StoneLineRole = 'MERKEZ' | 'YAN' | 'PAVE' | 'AKSAN';

export interface StoneLineItem {
  id: string;
  role: StoneLineRole;
  stoneType: StoneType;
  measureUnit: StoneMeasureUnit;
  count: number;
  carat: number;
  clarity?: string;
  colorGrade?: string;
  cutShape?: string;
}

export type ProductKind = 'FINISHED' | 'MOUNTING' | 'LOOSE_STONE';

export type LaborCostType = 'PER_GRAM' | 'FIXED';

export interface FinishedDetailState {
  metalName: string;
  purityCode: string;
  metalColor: string;
  fineness: number;
  baseWeightGr: number;
  fireRatePct: number;
  laborCostType: LaborCostType;
  laborCostValue: number;
  stoneSummary?: Record<string, unknown>;
  fixedStoneCostUsd: number;
}

export interface MountingDetailState {
  metalName: string;
  purityCode: string;
  metalColor: string;
  fineness: number;
  netWeightGr: number;
  laborCostType: LaborCostType;
  laborCostValue: number;
  mountStructure?: 'FULL' | 'HEAD_BAND';
  compatibleShapes: string[];
  minCarat: number | null;
  maxCarat: number | null;
  minLengthMm?: number | null;
  maxLengthMm?: number | null;
  minWidthMm?: number | null;
  maxWidthMm?: number | null;
  settingLaborUsd?: number;
  settingTypeCode?: string;
  headCode?: string;
  bandCode?: string;
  headWeightGram?: number | null;
  bandWeightGram?: number | null;
}

export interface LooseStoneDetailState {
  stoneCategory: string;
  shape: string;
  carat: number;
  color: string;
  clarity: string;
  cutGrade: string;
  certLab: string;
  certNumber: string;
  certUrl: string;
  measurementsMm: string;
  rapaportPriceUsd: number | null;
  discountPercent: number | null;
  netCostUsd: number;
  supplierId: string;
}

export interface ProductState {
  // Görsel & Vitrin Model Özeti
  visualType: JewelryVisualType;
  variantCount: number;
  availableColors: MetalColor[];

  // 1. Temel Bilgi
  productType: string;
  productKind?: ProductKind;
  erpCode?: string | null;
  finishedDetail?: FinishedDetailState | null;
  mountingDetail?: MountingDetailState | null;
  looseStoneDetail?: LooseStoneDetailState | null;
  parentSku: string;
  barcode: string;
  title: string;
  createdBy: string;
  description: string;

  // 2. Kategori
  collection: string;
  category: string;
  subCategory: string;
  metalColor: MetalColor;
  styleTechnique: string;
  occasion: string;
  ageGroup: string;

  // 3. Stok & Operasyon
  salesChannels: string[];
  supplierName: string;
  ownershipType: 'Öz Mal' | 'Konsinye (Emanet)';
  stockStatus: 'Stokta' | 'Tükendi' | 'Siparişe Özel';
  stockQty: number;
  warehouseLocation: string;
  leadTimeDays: number;

  // 4. Değerli Metal & Montür (FULL vs HEAD+BAND)
  metalName: string;
  purityCode: PurityCode;
  mountSpec?: MountSpec;

  // 5. Ağırlık, Taş Darası & Fire (+ Çoklu Taş Satırları)
  centerStoneCarat: number;
  sideStoneCarat: number;
  grossWeightGram: number;
  fireRatePct: number;
  stoneMeasureUnit: StoneMeasureUnit;
  stoneLines?: StoneLineItem[];

  // 6. Fiyatlandırma Ayarları
  pricingMode: PricingMode;
  pricingCurrency: PricingCurrency;

  // Yeni Çapraz Kur & Satır Bazlı FC→LC Fiyatlama Defteri
  ledger: PricingLedgerConfig;

  // 7. Model 1 (Geriye dönük / özet uyumluluk alanları)
  p1UnitLaborFee: number;
  p1StoneCostCurrency: number;
  p1B2bMarginPct: number;
  p1B2cMarginPct: number;
  p1PlatformFeeTry: number;

  // 8. Model 2 (Sade)
  p2SupplierPriceCurrency: number;
  p2B2bMarginPct: number;
  p2B2cMarginPct: number;
  p2PlatformFeeTry: number;

  // 9. Kampanya
  discountRatePct: number;

  // 10. Taş & Sertifika
  stoneType: StoneType;
  stoneCount: number;
  stoneCutShape: string;
  stoneClarity: string;
  stoneColorGrade: string;
  stoneCutGrade: string;
  stoneOrigin: string;
  settingType: string;
  hasCertificate: boolean;
  certificateAgency: string;
  certificateNumber: string;
  certificateFileUrl: string;

  // 11. Ölçü & Fiziksel
  variantSize: number;
  availableSizes: number[];
  widthMm: number;
  thicknessMm: number;
  heightMm: number;
  chainType: string;
  claspType: string;
  isResizable: boolean;
  sizeGuideUrl: string;

  // 12. Medya & B2B Katalog
  galleryImages: string[];
  reelsVideoUrl: string;
  spin360Url: string;
  catalogCleanImageUrl: string;
  b2bSharePermission: string;
  dynamicDealerWatermark: boolean;
  socialShareCaption: string;
  b2bCatalogShareEndpoint: string;

  // 13. Garanti, Kargo & SEO
  warrantyMonths: number;
  lifetimeMaintenance: string;
  insuredShippingInfo: string;
  returnPolicyText: string;
  seoSlug: string;
  metaTitle: string;
  marketplaceCategory: string;

  // Sunucu taraflı (Kör Havuz uyumlu) fiyat, varyant & metal özet alanları
  ownerOrganizationId?: string | null;
  recipeId?: string | null;
  variants?: ProductVariantSummary[];
  b2cPricing?: {
    snapshotId: string;
    listPriceTry: number | null;
    finalPriceTry: number | null;
    effectiveDiscountPct: number;
  };
  b2bPricing?: {
    snapshotId: string;
    lcCurrency: FxCurrencyCode;
    finalPriceLc: number | null;
    finalPriceTry: number | null;
  };
  metalSummary?: {
    netMetalGram: number;
    fineMetalGram: number;
    fireIncludedFineMetalGram?: number;
    fineness: number;
  };
}

export interface ProductVariantSummary {
  id: string;
  sku: string;
  purityCode: PurityCode;
  metalColor: MetalColor;
  size: number;
  centerStoneCarat: number;
  grossWeightGram: number;
  stockQty: number;
  isDefault: boolean;
  isActive?: boolean;
  b2cPricing?: {
    snapshotId: string;
    listPriceTry: number | null;
    finalPriceTry: number | null;
    effectiveDiscountPct: number;
  };
  b2bPricing?: {
    snapshotId: string;
    lcCurrency: FxCurrencyCode;
    finalPriceLc: number | null;
    finalPriceTry: number | null;
  };
}

export interface ComputedLedgerLine {
  currency: FxCurrencyCode;
  fcPrice: number;
  matrixRate: number;
  effectiveRate: number;
  isRateOverridden: boolean;
  lcPrice: number;
}

export interface ComputedChannelPricing {
  id: string;
  channel: PricingChannelTarget;
  profitLc: number;
  discountLc: number;
  subtotalBeforeDiscountLc: number;
  totalSalesLc: number;
  platformFeeLc: number;
  finalPriceLc: number;
  finalPriceTry: number;
  listPriceTry: number;
  discountTry: number;
  effectiveDiscountPct: number;
}

export interface ComputedLedgerOutputs {
  lcCurrency: FxCurrencyCode;
  lcToTryRate: number;

  metalLine: ComputedLedgerLine;
  metalAutoFcPrice: number;
  laborLine: ComputedLedgerLine;
  laborEffectiveGram: number;
  stoneLine: ComputedLedgerLine;
  mountingLine: ComputedLedgerLine;
  otherCostLine: ComputedLedgerLine;
  supplierLine: ComputedLedgerLine;

  totalCostLc: number;

  // Dinamik Satış Kanalı Çıktıları
  channels: ComputedChannelPricing[];
  hasB2bChannel: boolean;
  hasB2cChannel: boolean;

  b2bProfitLc: number;
  b2cProfitLc: number;
  b2bDiscountLc: number;
  b2cDiscountLc: number;
  b2bSubtotalBeforeDiscountLc: number;
  b2cSubtotalBeforeDiscountLc: number;
  b2bTotalSalesLc: number;
  b2cTotalSalesLc: number;
  b2bPlatformFeeLc: number;
  b2cPlatformFeeLc: number;
  platformFeeLc: number;
  b2bFinalPriceLc: number;
  b2cFinalPriceLc: number;
  b2bFinalPriceTry: number;
  b2cFinalPriceTry: number;
  b2cListPriceTry: number;
  b2cDiscountTry: number;
  effectiveB2cDiscountPct: number;
}

export interface ComputedJewelryMetrics {
  sku: string;
  optionKey: string;
  displayWeightText: string;
  purityValue: number;
  millesimalFineness: number;
  totalStoneCarat: number;
  stoneTareFactor: number;
  stoneTareGram: number;
  resolvedStoneLines: StoneLineItem[];
  isCaratWithinMountRange: boolean;
  netMetalGram: number;
  fineMetalGram: number;
  fireWeightGram: number;
  fireIncludedMetalGram: number;
  fireIncludedFineMetalGram: number;
  liveHasGoldUsdSell: number;
  selectedCurrencyToTry: number;

  // Yeni Çapraz Kur & FC→LC Motor Çıktısı
  ledger: ComputedLedgerOutputs;

  // Model 1 (TL özet uyumluluğu)
  p1MetalCostTry: number;
  p1TotalLaborCostTry: number;
  p1StoneCostTry: number;
  p1TotalCostTry: number;
  p1TotalCostCurrency: number;
  p1B2bPriceCurrency: number;
  p1B2bPriceTry: number;
  p1B2cPriceTry: number;

  // Model 2 (TL özet uyumluluğu)
  p2SupplierPriceTry: number;
  p2B2bPriceCurrency: number;
  p2B2bPriceTry: number;
  p2B2cPriceTry: number;

  // Final outputs (Vitrin, Ürün Kartı, Sözlük, JSON tarafından tüketilir)
  finalB2bPriceCurrency: number;
  finalB2bPriceTry: number;
  finalB2cPriceTry: number;
  discountAmountTry: number;
  discountedB2cPriceTry: number;
}

export interface SchemaTableDefinition {
  id: string;
  layerNumber: number;
  layerName: string;
  tableName: string;
  purpose: string;
  primaryKey: string;
  foreignKeys: string;
  keyFields: string[];
  variantBehavior: string;
  changesPerVariant: 'EVET' | 'HAYIR' | 'KOŞULLU';
}

export interface InheritanceRule {
  code: string;
  title: string;
  description: string;
  example: string;
}

export interface VariantPreset {
  sku: string;
  optionKey: string;
  purityCode: PurityCode;
  metalColor: MetalColor;
  variantSize: number;
  centerStoneCarat: number;
  sideStoneCarat: number;
  grossWeightGram: number;
  stockStatus: 'Stokta' | 'Tükendi' | 'Siparişe Özel';
  stockQty: number;
  barcode: string;
  ownershipType: 'Öz Mal' | 'Konsinye (Emanet)';
  warehouseLocation: string;
  hasMarginOverride: boolean;
  b2cMarginOverride?: number;
  b2bMarginOverride?: number;
  unitLaborOverride?: number;
  stoneCostOverride?: number;
  isDefault: boolean;
}

export interface StockItemRecord {
  barcode: string;
  variantSku: string;
  actualGrossWeightGram: number;
  itemStatus: 'STOKTA' | 'REZERVE' | 'KONSİNYE_İADE' | 'TAMİRDE';
  ownershipType: 'Konsinye (Emanet)' | 'Öz Mal';
  supplierName: string;
  entryUsdRate: number;
  entryHasGoldTry: number;
  entryCostTry: number;
  locationCode: string;
  certificateNumber: string;
  consignmentDueDate?: string;
}

export interface StockMovementRecord {
  movementId: string;
  variantSku: string;
  barcode?: string;
  movementType: 'GİRİŞ_KONSİNYE' | 'TRANSFER' | 'REZERVASYON' | 'SAYIM_DOĞRULAMA';
  qtyDelta: number;
  fromLocation: string;
  toLocation: string;
  refDoc: string;
  reason: string;
  createdBy: string;
  createdAt: string;
}

export interface DataDictionaryField {
  sectionId: number;
  sectionTitle: string;
  label: string;
  sampleOrFormula: string;
  unit: string;
  apiKey: string;
  b2cVisible: VisibilityLevel;
  b2bVisible: VisibilityLevel;
  businessRule: string;
  getLiveValue: (product: ProductState, rates: LiveRates, computed: ComputedJewelryMetrics) => string;
}

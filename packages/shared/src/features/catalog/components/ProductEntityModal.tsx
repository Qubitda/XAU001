import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowUpRight,
  Calculator,
  CheckCircle2,
  Diamond,
  EyeOff,
  Globe,
  History,
  Image as ImageIcon,
  Layers,
  Loader2,
  Package,
  Plus,
  Save,
  Shield,
  Trash2,
  Warehouse,
  X,
} from 'lucide-react';
import { ProductVariantsPanel, type PendingMatrixConfig } from './ProductVariantsPanel';
import { ProductStockPanel } from './ProductStockPanel';
import { ProductMediaPanel } from './ProductMediaPanel';
import { ProductSeoPanel } from './ProductSeoPanel';
import { ProductSalesWarrantyPanel } from './ProductSalesWarrantyPanel';
import {
  cloneLedger,
  createBlankProduct,
  createEmptyRates,
  withCurrentSelectOption,
} from '../../../data/productDefaults';
import { isRenderableMediaUrl } from '../../../data/productMedia';
import { ConfirmDialog } from '../../../components/crud/ConfirmDialog';
import { EntityModal } from '../../../components/crud/EntityModal';
import { Button, Input, Label } from '../../../components/ui';
import { cn } from '../../../lib/utils';
import { ApiClientError } from '../../../lib/api/client';
import { catalogService } from '../services/catalogService';
import {
  computeJewelryMetrics,
  deriveSalesChannelsFromRules,
  formatCurrencyValue,
  formatTrNumber,
  FX_CURRENCIES,
  FX_CURRENCY_LABELS,
  resolveProductKind,
} from '../../../utils/pricingEngine';
import { productFormSchema } from '../schemas/productSchema';
import { formatPublishError } from '../utils/publishMessages';
import {
  useCreateProductMutation,
  useLiveRatesQuery,
  usePublishProductMutation,
  useUnpublishProductMutation,
  useUpdateProductMutation,
} from '../hooks/useCatalogQueries';
import { useBulkCreateOpsVariantsMutation } from '../../ops/hooks/useOpsQueries';
import {
  filterOptionsByParent,
  useDefinitionOptions,
  useDefinitionTablesMap,
  usePurityFinenessMap,
  useRelatedDefinitionOptions,
} from '../../definitions/hooks/useDefinitionsQuery';
import { getActiveSalesChannels } from '../../../constants/salesChannels';
import type {
  AdjustmentUnit,
  CatalogStatus,
  ChannelPricingRule,
  FinishedDetailState,
  FxCurrencyCode,
  JewelryVisualType,
  LooseStoneDetailState,
  MetalColor,
  MountingDetailState,
  MountSpec,
  MountStructureType,
  PricingChannelTarget,
  PricingLedgerConfig,
  PricingMode,
  ProductKind,
  ProductState,
  PurityCode,
  StoneLineItem,
  StoneLineRole,
  StoneMeasureUnit,
  StoneType,
} from '../../../types/jewelry';

/** Canonical DYO shape codes stored on MountingDetail.compatibleShapes */
const DYO_COMPATIBLE_SHAPE_OPTIONS = [
  'ROUND',
  'OVAL',
  'PRINCESS',
  'PEAR',
  'EMERALD',
  'MARQUISE',
  'CUSHION',
  'RADIANT',
  'ASSCHER',
  'HEART',
] as const;

function resolveFinenessFromMap(
  purityCode: string,
  finenessMap?: Record<string, number>
): number {
  if (finenessMap && finenessMap[purityCode] != null) return finenessMap[purityCode];
  return 0;
}

function buildDetailPayload(
  draft: ProductState,
  finenessMap?: Record<string, number>
): Pick<ProductState, 'productKind' | 'finishedDetail' | 'mountingDetail' | 'looseStoneDetail'> {
  const kind = resolveProductKind(draft);
  const fineness = resolveFinenessFromMap(draft.purityCode, finenessMap);
  if (kind === 'FINISHED') {
    const finishedDetail: FinishedDetailState = draft.finishedDetail ?? {
      metalName: draft.metalName,
      purityCode: draft.purityCode,
      metalColor: draft.metalColor,
      fineness,
      baseWeightGr: draft.grossWeightGram,
      fireRatePct: draft.fireRatePct,
      laborCostType: 'FIXED',
      laborCostValue: draft.ledger.laborFcPrice ?? 0,
      fixedStoneCostUsd: draft.ledger.stoneFcPrice ?? 0,
      stoneSummary: {},
    };
    return {
      productKind: kind,
      finishedDetail: {
        ...finishedDetail,
        metalName: draft.metalName,
        purityCode: draft.purityCode,
        metalColor: draft.metalColor,
        fineness,
        baseWeightGr: draft.grossWeightGram,
        fireRatePct: draft.fireRatePct,
      },
      mountingDetail: null,
      looseStoneDetail: null,
    };
  }
  if (kind === 'MOUNTING') {
    const mountingDetail: MountingDetailState = draft.mountingDetail ?? {
      metalName: draft.metalName,
      purityCode: draft.purityCode,
      metalColor: draft.metalColor,
      fineness,
      netWeightGr: draft.grossWeightGram,
      laborCostType: 'FIXED',
      laborCostValue: draft.ledger.laborFcPrice ?? 0,
      mountStructure: draft.mountSpec?.structure ?? 'FULL',
      compatibleShapes: [],
      minCarat: draft.mountSpec?.allowedCaratMin ?? null,
      maxCarat: draft.mountSpec?.allowedCaratMax ?? null,
      minLengthMm: null,
      maxLengthMm: null,
      minWidthMm: null,
      maxWidthMm: null,
      settingLaborUsd: 0,
      settingTypeCode: draft.settingType || '',
      headCode: draft.mountSpec?.headCode,
      bandCode: draft.mountSpec?.bandCode,
      headWeightGram: draft.mountSpec?.headWeightGram,
      bandWeightGram: draft.mountSpec?.bandWeightGram,
    };
    return {
      productKind: kind,
      finishedDetail: null,
      mountingDetail: {
        ...mountingDetail,
        metalName: draft.metalName,
        purityCode: draft.purityCode,
        metalColor: draft.metalColor,
        fineness,
        netWeightGr: draft.grossWeightGram,
        compatibleShapes: mountingDetail.compatibleShapes ?? [],
        minCarat: draft.mountSpec?.allowedCaratMin ?? mountingDetail.minCarat,
        maxCarat: draft.mountSpec?.allowedCaratMax ?? mountingDetail.maxCarat,
        minLengthMm: mountingDetail.minLengthMm ?? null,
        maxLengthMm: mountingDetail.maxLengthMm ?? null,
        minWidthMm: mountingDetail.minWidthMm ?? null,
        maxWidthMm: mountingDetail.maxWidthMm ?? null,
        settingLaborUsd: mountingDetail.settingLaborUsd ?? 0,
        settingTypeCode: mountingDetail.settingTypeCode || draft.settingType || '',
        mountStructure: draft.mountSpec?.structure ?? mountingDetail.mountStructure,
      },
      looseStoneDetail: null,
    };
  }
  const center = (draft.stoneLines ?? []).find((s) => s.role === 'MERKEZ');
  const looseStoneDetail: LooseStoneDetailState = draft.looseStoneDetail ?? {
    stoneCategory: draft.stoneType,
    shape: draft.stoneCutShape || center?.cutShape || '',
    carat: center?.carat ?? draft.centerStoneCarat,
    color: draft.stoneColorGrade || center?.colorGrade || '',
    clarity: draft.stoneClarity || center?.clarity || '',
    cutGrade: draft.stoneCutGrade || '',
    certLab: draft.certificateAgency || '',
    certNumber: draft.certificateNumber || '',
    certUrl: draft.certificateFileUrl || '',
    measurementsMm: '',
    rapaportPriceUsd: null,
    discountPercent: null,
    netCostUsd: draft.ledger.stoneFcPrice ?? 0,
    supplierId: draft.supplierName || 'INTERNAL',
  };
  return {
    productKind: kind,
    finishedDetail: null,
    mountingDetail: null,
    looseStoneDetail: {
      ...looseStoneDetail,
      stoneCategory: draft.stoneType,
      shape: draft.stoneCutShape || looseStoneDetail.shape,
      carat: center?.carat ?? draft.centerStoneCarat,
      color: draft.stoneColorGrade || looseStoneDetail.color,
      clarity: draft.stoneClarity || looseStoneDetail.clarity,
      cutGrade: draft.stoneCutGrade || looseStoneDetail.cutGrade,
      certLab: draft.certificateAgency || looseStoneDetail.certLab,
      certNumber: draft.certificateNumber || looseStoneDetail.certNumber,
      netCostUsd: draft.ledger.stoneFcPrice ?? looseStoneDetail.netCostUsd,
    },
  };
}

export type ProductModalTab =
  | 'genel'
  | 'varyantlar'
  | 'stok'
  | 'tas-montur'
  | 'fiyatlandirma'
  | 'medya'
  | 'seo'
  | 'satis';

interface ProductEntityModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: 'create' | 'edit';
  initialProduct?: ProductState;
  initialTab?: ProductModalTab;
  onSaved?: (saved: ProductState) => void;
}

type SelectOption = { value: string; label: string };

function withCurrentOption(options: SelectOption[], current: string): SelectOption[] {
  return withCurrentSelectOption(options, current);
}
const STONE_ROLES: { value: StoneLineRole; label: string }[] = [
  { value: 'MERKEZ', label: 'Merkez' },
  { value: 'YAN', label: 'Yan' },
  { value: 'PAVE', label: 'Pavé' },
  { value: 'AKSAN', label: 'Aksan' },
];
const ADJUSTMENT_UNITS: AdjustmentUnit[] = [
  '%',
  'TRY',
  'USD',
  'EUR',
  'GBP',
  'CHF',
  'XAU',
  'XAG',
  'XPT',
  'XPD',
];
const VISUAL_OPTIONS: { value: JewelryVisualType; label: string }[] = [
  { value: 'solitaire_ring', label: 'Tektaş Yüzük Stüdyo Şablonu' },
  { value: 'baguette_ring', label: 'Baget Yüzük Stüdyo Şablonu' },
  { value: 'pendant_necklace', label: 'Tektaş Kolye Stüdyo Şablonu' },
  { value: 'tennis_bracelet', label: 'Su Yolu Bileklik Stüdyo Şablonu' },
  { value: 'emerald_earring', label: 'Zümrüt Küpe Stüdyo Şablonu' },
  { value: 'eternity_ring', label: 'Tamtur Alyans Stüdyo Şablonu' },
];
const FIELD_SELECT_CLASS =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50';

const FIELD_TEXTAREA_CLASS =
  'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50';

const CERT_AGENCIES = ['GIA', 'HRD', 'IGI', 'EGL', 'Tara Gold Sertifikası', ''];

const TABS: { id: ProductModalTab; label: string; icon: typeof Package }[] = [
  { id: 'genel', label: 'Genel Bilgiler', icon: Package },
  { id: 'varyantlar', label: 'Varyantlar', icon: Layers },
  { id: 'stok', label: 'Stok & Depo', icon: Warehouse },
  { id: 'tas-montur', label: 'Taş, Montür & Sertifika', icon: Diamond },
  { id: 'fiyatlandirma', label: 'Fiyatlandırma', icon: Calculator },
  { id: 'medya', label: 'Görsel & Video', icon: ImageIcon },
  { id: 'seo', label: 'SEO', icon: Globe },
  { id: 'satis', label: 'Satış & Garanti', icon: Shield },
];

const FIELD_TO_TAB: Record<string, ProductModalTab> = {
  grossWeightGram: 'tas-montur',
  centerStoneCarat: 'tas-montur',
  sideStoneCarat: 'tas-montur',
  fireRatePct: 'tas-montur',
  stoneType: 'tas-montur',
  stoneLines: 'tas-montur',
  mountSpec: 'tas-montur',
  stockQty: 'stok',
  stockStatus: 'stok',
  ownershipType: 'stok',
  leadTimeDays: 'stok',
  ledger: 'fiyatlandirma',
  pricingMode: 'fiyatlandirma',
  galleryImages: 'medya',
  mediaItems: 'medya',
  reelsVideoUrl: 'medya',
  spin360Url: 'medya',
  catalogCleanImageUrl: 'medya',
  certificateFileUrl: 'medya',
  seoSlug: 'seo',
  metaTitle: 'seo',
  metaDescription: 'seo',
  marketplaceCategory: 'seo',
  sizeGuideUrl: 'seo',
  ogImage: 'seo',
  canonicalUrl: 'seo',
  robots: 'seo',
  keywords: 'seo',
  warrantyMonths: 'satis',
  lifetimeMaintenance: 'satis',
  insuredShippingInfo: 'satis',
  returnPolicyText: 'satis',
  supplierName: 'satis',
};

function resolveTabForField(field: string): ProductModalTab {
  if (field in FIELD_TO_TAB) return FIELD_TO_TAB[field];
  const root = field.split('.')[0];
  return FIELD_TO_TAB[root] ?? 'genel';
}

function slugifyTurkish(input: string): string {
  const map: Record<string, string> = {
    ç: 'c',
    Ç: 'c',
    ğ: 'g',
    Ğ: 'g',
    ı: 'i',
    İ: 'i',
    ö: 'o',
    Ö: 'o',
    ş: 's',
    Ş: 's',
    ü: 'u',
    Ü: 'u',
  };
  return input
    .split('')
    .map((ch) => map[ch] ?? ch)
    .join('')
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

function cloneProductDraft(mode: 'create' | 'edit', product?: ProductState): ProductState {
  if (mode === 'edit' && product) {
    const base = createBlankProduct();
    return {
      ...base,
      ...product,
      productKind: resolveProductKind(product),
      availableColors: [...(product.availableColors ?? [])],
      availableSizes: [...(product.availableSizes ?? [])],
      salesChannels: [...(product.salesChannels ?? [])],
      galleryImages: [...(product.galleryImages ?? [])],
      mountSpec: product.mountSpec
        ? { ...product.mountSpec }
        : {
            structure: 'FULL',
            allowedCaratMin: 0,
            allowedCaratMax: 0,
            headCode: '',
            bandCode: '',
            headWeightGram: 0,
            bandWeightGram: 0,
          },
      mountingDetail: product.mountingDetail
        ? {
            ...product.mountingDetail,
            compatibleShapes: [...(product.mountingDetail.compatibleShapes ?? [])],
          }
        : product.mountingDetail,
      stoneLines: (product.stoneLines ?? []).map((s) => ({ ...s })),
      ledger: cloneLedger(product.ledger),
    };
  }

  return createBlankProduct({
    productKind: 'FINISHED' as ProductKind,
    stoneMeasureUnit: 'ct',
    stockStatus: 'Stokta',
    ownershipType: 'Öz Mal',
    visualType: 'solitaire_ring',
  });
}

function summarizeStoneLines(lines: StoneLineItem[]): {
  centerCarat: number;
  sideCarat: number;
  totalCount: number;
} {
  let center = 0;
  let side = 0;
  let count = 0;
  for (const line of lines) {
    const qty = Math.max(0, Number(line.count) || 0);
    const ct = Math.max(0, Number(line.carat) || 0);
    count += qty;
    if (line.role === 'MERKEZ') {
      center += qty * ct;
    } else {
      side += qty * ct;
    }
  }
  return {
    centerCarat: Number(center.toFixed(3)),
    sideCarat: Number(side.toFixed(3)),
    totalCount: count,
  };
}

async function fileToCompressedDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Dosya okunamadı.'));
    reader.onload = () => {
      const rawUrl = String(reader.result ?? '');
      if (!file.type.startsWith('image/')) {
        resolve(rawUrl);
        return;
      }
      const img = new Image();
      img.onload = () => {
        const maxDim = 960;
        const scale = Math.min(1, maxDim / Math.max(img.width, img.height, 1));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          resolve(rawUrl);
          return;
        }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.82));
      };
      img.onerror = () => resolve(rawUrl);
      img.src = rawUrl;
    };
    reader.readAsDataURL(file);
  });
}

export function ProductEntityModal({
  open,
  onOpenChange,
  mode,
  initialProduct,
  initialTab = 'genel',
  onSaved,
}: ProductEntityModalProps) {
  const [activeTab, setActiveTab] = useState<ProductModalTab>(initialTab);
  const [baseline, setBaseline] = useState<ProductState>(() =>
    cloneProductDraft(mode, initialProduct)
  );
  const [draft, setDraft] = useState<ProductState>(() =>
    cloneProductDraft(mode, initialProduct)
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [priceConfirmOpen, setPriceConfirmOpen] = useState(false);
  const [pendingPriceConfirmStatus, setPendingPriceConfirmStatus] = useState<CatalogStatus | undefined>(
    undefined
  );
  const [newImageUrl, setNewImageUrl] = useState('');
  const [newSizeInput, setNewSizeInput] = useState('');
  const [pendingMatrix, setPendingMatrix] = useState<PendingMatrixConfig>({
    purities: [],
    colors: [],
    sizes: [],
    initialStockQty: 0,
  });

  const liveRatesQuery = useLiveRatesQuery();
  const rates = liveRatesQuery.data ?? createEmptyRates();
  const defsEnabled = open;
  const { map: finenessMap } = usePurityFinenessMap(defsEnabled);
  const { salesChannels: salesChannelDefs } = useDefinitionTablesMap(defsEnabled);
  const productTypeOpts = useDefinitionOptions('urun_tipi', defsEnabled);
  const collectionOpts = useDefinitionOptions('koleksiyon', defsEnabled);
  const categoryOpts = useDefinitionOptions('kategori', defsEnabled);
  const subCategoryOpts = useRelatedDefinitionOptions(
    'alt_kategori',
    draft.category,
    defsEnabled
  );
  const metalColorOpts = useRelatedDefinitionOptions(
    'metal_rengi',
    draft.metalName,
    defsEnabled
  );
  const styleOpts = useDefinitionOptions('teknik_stil', defsEnabled);
  const occasionOpts = useDefinitionOptions('ozel_gun', defsEnabled);
  const ageGroupOpts = useRelatedDefinitionOptions('yas_grubu', draft.collection, defsEnabled);
  const metalNameOpts = useDefinitionOptions('metal_adi', defsEnabled);
  const purityOpts = useRelatedDefinitionOptions('ayar_kodu', draft.metalName, defsEnabled);
  const stoneTypeOpts = useDefinitionOptions('tas_tipi', defsEnabled);
  const stoneCutAllOpts = useDefinitionOptions('tas_kesimi', defsEnabled);
  const clarityAllOpts = useDefinitionOptions('berraklik', defsEnabled);
  const colorGradeAllOpts = useDefinitionOptions('renk_derecesi', defsEnabled);
  const cutGradeOpts = useRelatedDefinitionOptions(
    'kesim_kalitesi',
    draft.stoneType,
    defsEnabled
  );
  const stoneOriginOpts = useRelatedDefinitionOptions('tas_mensei', draft.stoneType, defsEnabled);
  const settingOpts = useRelatedDefinitionOptions('mihlama_tipi', draft.stoneType, defsEnabled);
  const chainOpts = useRelatedDefinitionOptions('zincir_tipi', draft.category, defsEnabled);
  const claspOpts = useRelatedDefinitionOptions('kopca_tipi', draft.category, defsEnabled);
  const ownershipOpts = useDefinitionOptions('stok_mulkiyet_tipi', defsEnabled);
  const stockStatusOpts = useDefinitionOptions('stok_durumu', defsEnabled);

  const categoryOptions = withCurrentOption(categoryOpts.options, draft.category);
  const subCategoryOptions = withCurrentOption(subCategoryOpts.options, draft.subCategory);
  const collectionOptions = withCurrentOption(collectionOpts.options, draft.collection);
  const purityOptions = withCurrentOption(purityOpts.options, draft.purityCode);
  const colorOptions = withCurrentOption(metalColorOpts.options, draft.metalColor);
  const COLORS = colorOptions.map((o) => o.value as MetalColor);
  const stoneOptions = withCurrentOption(stoneTypeOpts.options, draft.stoneType);
  const channelOptions = salesChannelDefs.length
    ? salesChannelDefs
    : getActiveSalesChannels().map((c) => ({ ...c, isSystem: true }));

  const createMutation = useCreateProductMutation();
  const updateMutation = useUpdateProductMutation();
  const publishMutation = usePublishProductMutation();
  const unpublishMutation = useUnpublishProductMutation();
  const bulkVariantsMutation = useBulkCreateOpsVariantsMutation();
  const isSubmitting =
    createMutation.isPending ||
    updateMutation.isPending ||
    publishMutation.isPending ||
    unpublishMutation.isPending ||
    bulkVariantsMutation.isPending;

  useEffect(() => {
    if (open) {
      const next = cloneProductDraft(mode, initialProduct);
      setBaseline(next);
      setDraft(next);
      setActiveTab(initialTab);
      setFieldErrors({});
      setServerError(null);
      setNewSizeInput('');
      setPendingMatrix({
        purities: next.purityCode ? [next.purityCode] : [],
        colors: next.availableColors?.length ? next.availableColors : next.metalColor ? [next.metalColor] : [],
        sizes: next.availableSizes?.length ? next.availableSizes : next.variantSize ? [next.variantSize] : [14],
        initialStockQty: 0,
      });
    }
  }, [open, mode, initialProduct, initialTab]);

  // Sensible auto-defaults for create mode so the form isn't stuck with empty state
  useEffect(() => {
    if (!open || mode !== 'create') return;

    setDraft((prev) => {
      let changed = false;
      const updates: Partial<ProductState> = {};

      if (!prev.productType && productTypeOpts.options.length > 0) {
        updates.productType = productTypeOpts.options[0].value;
        updates.productKind = resolveProductKind({ productType: updates.productType });
        changed = true;
      }

      if (!prev.stoneType) {
        updates.stoneType = 'Pırlanta';
        changed = true;
      }

      if ((!prev.salesChannels || prev.salesChannels.length === 0) && channelOptions.length > 0) {
        updates.salesChannels = channelOptions.map((c) => c.code);
        changed = true;
      }

      if (!prev.metalName && metalNameOpts.options.length > 0) {
        const goldOpt = metalNameOpts.options.find(
          (o) =>
            o.label.toLocaleLowerCase('tr-TR') === 'altın' ||
            o.value.toLocaleLowerCase('tr-TR') === 'altın' ||
            o.code.toLocaleLowerCase('tr-TR') === 'altin'
        );
        updates.metalName = (goldOpt ?? metalNameOpts.options[0]).value;
        changed = true;
      }

      return changed ? { ...prev, ...updates } : prev;
    });
  }, [open, mode, productTypeOpts.options, metalNameOpts.options, channelOptions]);

  useEffect(() => {
    if (!open || mode !== 'create' || !draft.metalName) return;

    setDraft((prev) => {
      let changed = false;
      const updates: Partial<ProductState> = {};

      if (!prev.purityCode && purityOpts.options.length > 0) {
        const p14k = purityOpts.options.find(
          (o) => o.code === '14K' || o.value === '14K' || o.label.includes('14')
        );
        updates.purityCode = (p14k ?? purityOpts.options[0]).value as PurityCode;
        changed = true;
      }

      if (metalColorOpts.options.length > 0) {
        if (!prev.metalColor) {
          updates.metalColor = metalColorOpts.options[0].value as MetalColor;
          changed = true;
        }
        if (prev.availableColors.length === 0) {
          const firstColor = (updates.metalColor ?? prev.metalColor ?? metalColorOpts.options[0].value) as MetalColor;
          updates.availableColors = [firstColor];
          changed = true;
        }
      }

      return changed ? { ...prev, ...updates } : prev;
    });
  }, [open, mode, draft.metalName, purityOpts.options, metalColorOpts.options]);

  const isDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(baseline),
    [draft, baseline]
  );

  const liveComputed = useMemo(() => computeJewelryMetrics(draft, rates), [draft, rates]);
  const baselineComputed = useMemo(() => computeJewelryMetrics(baseline, rates), [baseline, rates]);
  const hasPriceAffectingChange = useMemo(() => {
    if (mode !== 'edit') return false;
    return (
      draft.pricingMode !== baseline.pricingMode ||
      Number(draft.grossWeightGram) !== Number(baseline.grossWeightGram) ||
      Number(draft.fireRatePct) !== Number(baseline.fireRatePct) ||
      draft.purityCode !== baseline.purityCode ||
      Number(draft.centerStoneCarat) !== Number(baseline.centerStoneCarat) ||
      Number(draft.sideStoneCarat) !== Number(baseline.sideStoneCarat) ||
      draft.productKind !== baseline.productKind ||
      JSON.stringify(draft.ledger) !== JSON.stringify(baseline.ledger) ||
      JSON.stringify(draft.stoneLines ?? []) !== JSON.stringify(baseline.stoneLines ?? []) ||
      JSON.stringify(draft.mountSpec ?? null) !== JSON.stringify(baseline.mountSpec ?? null) ||
      JSON.stringify(draft.finishedDetail ?? null) !== JSON.stringify(baseline.finishedDetail ?? null) ||
      JSON.stringify(draft.mountingDetail ?? null) !== JSON.stringify(baseline.mountingDetail ?? null) ||
      JSON.stringify(draft.looseStoneDetail ?? null) !== JSON.stringify(baseline.looseStoneDetail ?? null)
    );
  }, [mode, draft, baseline]);

  const patchDraft = <K extends keyof ProductState>(key: K, value: ProductState[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      if (!prev[key]) return prev;
      const copy = { ...prev };
      delete copy[key];
      return copy;
    });
    setServerError(null);
  };

  const patchMountingDetail = (patch: Partial<MountingDetailState>) => {
    setDraft((prev) => {
      const fineness = resolveFinenessFromMap(prev.purityCode, finenessMap);
      const base: MountingDetailState = prev.mountingDetail ?? {
        metalName: prev.metalName,
        purityCode: prev.purityCode,
        metalColor: prev.metalColor,
        fineness,
        netWeightGr: prev.grossWeightGram,
        laborCostType: 'FIXED',
        laborCostValue: prev.ledger.laborFcPrice ?? 0,
        mountStructure: prev.mountSpec?.structure ?? 'FULL',
        compatibleShapes: [],
        minCarat: prev.mountSpec?.allowedCaratMin ?? null,
        maxCarat: prev.mountSpec?.allowedCaratMax ?? null,
        minLengthMm: null,
        maxLengthMm: null,
        minWidthMm: null,
        maxWidthMm: null,
        settingLaborUsd: 0,
        settingTypeCode: prev.settingType || '',
      };
      return { ...prev, mountingDetail: { ...base, ...patch } };
    });
    setServerError(null);
  };

  const patchLedger = (patch: Partial<PricingLedgerConfig>) => {
    setDraft((prev) => {
      const nextLedger: PricingLedgerConfig = { ...prev.ledger, ...patch };
      return {
        ...prev,
        ledger: nextLedger,
        pricingCurrency: (nextLedger.lcCurrency === 'USD' || nextLedger.lcCurrency === 'EUR' || nextLedger.lcCurrency === 'TRY'
          ? nextLedger.lcCurrency
          : prev.pricingCurrency),
        ...(patch.channelRules
          ? { salesChannels: deriveSalesChannelsFromRules(patch.channelRules) }
          : {}),
      };
    });
    setServerError(null);
  };

  const updateStoneLines = (nextLines: StoneLineItem[]) => {
    const summary = summarizeStoneLines(nextLines);
    setDraft((prev) => ({
      ...prev,
      stoneLines: nextLines,
      centerStoneCarat: summary.centerCarat,
      sideStoneCarat: summary.sideCarat,
      stoneCount: summary.totalCount,
    }));
  };

  const handleAddStoneLine = () => {
    const current = draft.stoneLines ?? [];
    const nextRole: StoneLineRole = current.some((s) => s.role === 'MERKEZ') ? 'PAVE' : 'MERKEZ';
    updateStoneLines([
      ...current,
      {
        id: `st-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role: nextRole,
        stoneType: draft.stoneType === 'Taşsız' ? 'Pırlanta' : draft.stoneType,
        measureUnit: draft.stoneMeasureUnit ?? 'ct',
        count: nextRole === 'MERKEZ' ? 1 : 10,
        carat: nextRole === 'MERKEZ' ? 0.5 : 0.01,
        clarity: draft.stoneClarity || 'VS1',
        colorGrade: draft.stoneColorGrade || 'F',
        cutShape: draft.stoneCutShape || 'Yuvarlak (Round)',
      },
    ]);
  };

  const handleRemoveStoneLine = (id: string) => {
    updateStoneLines((draft.stoneLines ?? []).filter((s) => s.id !== id));
  };

  const handleUpdateStoneLine = (id: string, patch: Partial<StoneLineItem>) => {
    updateStoneLines(
      (draft.stoneLines ?? []).map((s) => (s.id === id ? { ...s, ...patch } : s))
    );
  };

  const handleAddChannelRule = (target: PricingChannelTarget) => {
    const existing = draft.ledger.channelRules;
    if (existing.some((r) => r.channel === target)) return;
    const newRule: ChannelPricingRule = {
      id: `ch-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      channel: target,
      profit: { unit: '%', value: target === 'B2C_API' ? 45 : 15 },
      discount: { unit: '%', value: 0 },
      platformFee: { unit: '%', value: 1 },
    };
    patchLedger({
      channelRules: [...existing, newRule],
    });
  };

  const handleUpdateChannelRule = (id: string, patch: Partial<ChannelPricingRule>) => {
    patchLedger({
      channelRules: draft.ledger.channelRules.map((r) => (r.id === id ? { ...r, ...patch } : r)),
    });
  };

  const handleRemoveChannelRule = (id: string) => {
    patchLedger({
      channelRules: draft.ledger.channelRules.filter((r) => r.id !== id),
    });
  };

  const handleToggleColor = (color: MetalColor) => {
    const exists = draft.availableColors.includes(color);
    if (exists && draft.availableColors.length <= 1) return;
    const next = exists
      ? draft.availableColors.filter((c) => c !== color)
      : [...draft.availableColors, color];
    setDraft((prev) => ({
      ...prev,
      availableColors: next,
      metalColor: next.includes(prev.metalColor) ? prev.metalColor : next[0],
    }));
  };

  const handleAddSize = () => {
    const parsed = Number(newSizeInput);
    if (!Number.isInteger(parsed) || parsed < 6 || parsed > 70) return;
    if (draft.availableSizes.includes(parsed)) {
      setNewSizeInput('');
      return;
    }
    patchDraft(
      'availableSizes',
      [...draft.availableSizes, parsed].sort((a, b) => a - b)
    );
    setNewSizeInput('');
  };

  const handleRemoveSize = (size: number) => {
    if (draft.availableSizes.length <= 1) return;
    const next = draft.availableSizes.filter((s) => s !== size);
    setDraft((prev) => ({
      ...prev,
      availableSizes: next,
      variantSize: next.includes(prev.variantSize) ? prev.variantSize : next[0],
    }));
  };

  const handleSubmit = async (targetStatus?: CatalogStatus, bypassPriceConfirm = false) => {
    if (mode === 'edit' && initialProduct && hasPriceAffectingChange && !bypassPriceConfirm) {
      setPendingPriceConfirmStatus(targetStatus);
      setPriceConfirmOpen(true);
      return;
    }
    setServerError(null);
    const parsed = productFormSchema.safeParse({
      parentSku: draft.parentSku,
      title: draft.title,
      category: draft.category,
      subCategory: draft.subCategory,
      collection: draft.collection,
      purityCode: draft.purityCode,
      metalColor: draft.metalColor,
      stoneType: draft.stoneType || 'Taşsız',
      grossWeightGram: Number(draft.grossWeightGram) || 0,
      centerStoneCarat: Number(draft.centerStoneCarat) || 0,
      sideStoneCarat: Number(draft.sideStoneCarat) || 0,
      fireRatePct: Number(draft.fireRatePct) || 0,
      stockStatus: draft.stockStatus || 'Stokta',
      stockQty: Number(draft.stockQty) || 0,
      ownershipType: draft.ownershipType || 'Öz Mal',
      visualType: draft.visualType || 'solitaire_ring',
      description: draft.description || '',
      salesChannels: draft.salesChannels ?? [],
    });

    if (!parsed.success) {
      const nextErrors: Record<string, string> = {};
      const errorLabels: string[] = [];
      for (const issue of parsed.error.issues) {
        const key = String(issue.path[0] ?? 'form');
        if (!nextErrors[key]) {
          nextErrors[key] = issue.message;
          errorLabels.push(issue.message);
        }
      }
      setFieldErrors(nextErrors);
      setServerError(`Lütfen formu kontrol edin: ${errorLabels.slice(0, 3).join(', ')}`);
      const firstKey = Object.keys(nextErrors)[0];
      setActiveTab(firstKey ? resolveTabForField(firstKey) : 'genel');
      return;
    }

    const normalizedSku = draft.parentSku.trim().toUpperCase();
    const resolvedSlug =
      slugifyTurkish(draft.seoSlug || '') ||
      slugifyTurkish(`${normalizedSku}-${draft.title}`) ||
      `${normalizedSku.toLowerCase()}-mucevher`;
    const resolvedMetaTitle = draft.metaTitle.trim() || `${draft.title.trim()} | Tara Gold`;
    const resolvedDescription =
      draft.description.trim() ||
      `${draft.title.trim()} (${draft.purityCode} ${draft.metalColor})`;

    const resolvedStatus: CatalogStatus =
      targetStatus ?? draft.catalogStatus ?? 'DRAFT';

    const selectedChannels = draft.salesChannels ?? [];
    const existingRules = draft.ledger.channelRules.filter((r) =>
      selectedChannels.includes(r.channel)
    );
    const syncedRules: ChannelPricingRule[] = [...existingRules];
    for (const ch of selectedChannels) {
      if (
        (ch === 'B2B' || ch === 'B2B_API' || ch === 'B2C_API') &&
        !syncedRules.some((r) => r.channel === ch)
      ) {
        syncedRules.push({
          id: `ch-${Date.now()}-${ch.toLowerCase()}`,
          channel: ch,
          profit: { unit: '%', value: ch === 'B2C_API' ? 45 : 15 },
          discount: { unit: '%', value: 0 },
          platformFee: { unit: '%', value: 1 },
        });
      }
    }
    const syncedDraft: ProductState = {
      ...draft,
      ledger: {
        ...draft.ledger,
        channelRules: syncedRules,
      },
    };

    const payload: ProductState = {
      ...syncedDraft,
      ...buildDetailPayload(syncedDraft, finenessMap),
      catalogStatus: resolvedStatus,
      parentSku: normalizedSku,
      title: draft.title.trim(),
      description: resolvedDescription,
      seoSlug: resolvedSlug,
      metaTitle: resolvedMetaTitle,
      hasCertificate: Boolean(draft.certificateAgency.trim()),
    };

    try {
      if (mode === 'create') {
        // POST never creates ACTIVE directly; always create as DRAFT then run publish gate if requested.
        const createPayload: ProductState = {
          ...payload,
          catalogStatus: 'DRAFT',
        };
        const created = await createMutation.mutateAsync(createPayload);
        if (
          pendingMatrix.purities.length > 0 &&
          pendingMatrix.colors.length > 0 &&
          pendingMatrix.sizes.length > 0
        ) {
          try {
            await bulkVariantsMutation.mutateAsync({
              parentSku: created.parentSku,
              purities: pendingMatrix.purities,
              colors: pendingMatrix.colors,
              sizes: pendingMatrix.sizes,
              centerStoneCarat: String(draft.centerStoneCarat ?? 0),
              grossWeightGram: String(Math.max(0.01, Number(draft.grossWeightGram) || 3)),
              initialStockQty: pendingMatrix.initialStockQty,
            });
          } catch {
            // Non-blocking: default variant already exists
          }
        }
        if (resolvedStatus === 'ACTIVE') {
          try {
            const pubRes = await publishMutation.mutateAsync(created.parentSku);
            onSaved?.({ ...created, catalogStatus: pubRes.catalogStatus as CatalogStatus });
            onOpenChange(false);
          } catch (pubErr) {
            onSaved?.(created);
            setServerError(
              `Ürün taslak olarak kaydedildi ancak yayınlanamadı: ${formatPublishError(pubErr)}`
            );
          }
          return;
        }
        onSaved?.(created);
        onOpenChange(false);
      } else if (initialProduct) {
        const wasPublished = initialProduct.catalogStatus === 'ACTIVE';
        const wantsPublish = resolvedStatus === 'ACTIVE' && !wasPublished;
        const wantsUnpublish = resolvedStatus === 'DRAFT' && wasPublished;
        const {
          catalogStatus: _omittedStatus,
          stockQty: _omittedStockQty,
          ...patchBase
        } = payload;
        const patchPayload: Partial<ProductState> =
          resolvedStatus === 'ACTIVE' || wantsUnpublish
            ? patchBase
            : { ...patchBase, catalogStatus: resolvedStatus };
        const updated = await updateMutation.mutateAsync({
          parentSku: initialProduct.parentSku,
          patch: patchPayload,
        });
        if (wantsPublish) {
          try {
            const pubRes = await publishMutation.mutateAsync(initialProduct.parentSku);
            onSaved?.({ ...updated, catalogStatus: pubRes.catalogStatus as CatalogStatus });
            onOpenChange(false);
          } catch (pubErr) {
            onSaved?.(updated);
            setServerError(formatPublishError(pubErr));
          }
          return;
        }
        if (wantsUnpublish) {
          const unpubRes = await unpublishMutation.mutateAsync(initialProduct.parentSku);
          onSaved?.({ ...updated, catalogStatus: unpubRes.catalogStatus as CatalogStatus });
          onOpenChange(false);
          return;
        }
        onSaved?.(updated);
        onOpenChange(false);
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        const detailLines = err.details
          ? Object.entries(err.details)
              .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : String(msgs)}`)
              .filter(Boolean)
          : [];
        if (err.details) {
          const mapped: Record<string, string> = {};
          for (const [field, msgs] of Object.entries(err.details)) {
            mapped[field] = Array.isArray(msgs) ? msgs.join(', ') : String(msgs);
          }
          setFieldErrors((prev) => ({ ...prev, ...mapped }));
          const firstApiField = Object.keys(mapped)[0];
          if (firstApiField) {
            setActiveTab(resolveTabForField(firstApiField));
          }
        }
        setServerError(
          detailLines.length > 0 ? `${err.message} (${detailLines.join(' · ')})` : err.message
        );
      } else {
        setServerError('Kayıt sırasında beklenmeyen bir hata oluştu.');
      }
    }
  };

  const usedChannels = new Set(draft.ledger.channelRules.map((r) => r.channel));
  const hasB2bRule = usedChannels.has('B2B');
  const hasB2bApiRule = usedChannels.has('B2B_API');
  const hasB2cApiRule = usedChannels.has('B2C_API');
  const stoneLines = draft.stoneLines ?? [];
  const mountSpec: MountSpec = draft.mountSpec ?? {
    structure: 'FULL' as MountStructureType,
    allowedCaratMin: 0.1,
    allowedCaratMax: 2.0,
  };
  const mountingDetail: MountingDetailState = draft.mountingDetail ?? {
    metalName: draft.metalName,
    purityCode: draft.purityCode,
    metalColor: draft.metalColor,
    fineness: resolveFinenessFromMap(draft.purityCode, finenessMap),
    netWeightGr: draft.grossWeightGram,
    laborCostType: 'FIXED',
    laborCostValue: draft.ledger.laborFcPrice ?? 0,
    mountStructure: mountSpec.structure,
    compatibleShapes: [],
    minCarat: mountSpec.allowedCaratMin,
    maxCarat: mountSpec.allowedCaratMax,
    minLengthMm: null,
    maxLengthMm: null,
    minWidthMm: null,
    maxWidthMm: null,
    settingLaborUsd: 0,
    settingTypeCode: draft.settingType || '',
  };
  const isMountingKind = resolveProductKind(draft) === 'MOUNTING';

  const currentStatus: CatalogStatus = draft.catalogStatus ?? 'DRAFT';
  const isPublished = currentStatus === 'ACTIVE';

  return (
    <EntityModal
      open={open}
      onOpenChange={onOpenChange}
      size="2xl"
      title={
        mode === 'create'
          ? 'Yeni Mücevher Modeli Oluştur'
          : `Ürün Kartını Düzenle · ${initialProduct?.parentSku ?? draft.parentSku}`
      }
      description="Ürün bilgileri, varyantlar, stok, taş/montür, fiyatlandırma ve satış ayarları. Katalog kartı ile fiziksel stok ayrıdır."
      isDirty={isDirty}
      isSubmitting={isSubmitting}
      onSubmit={() => void handleSubmit(currentStatus)}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3 w-full">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">Durum:</span>
            {isPublished ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium text-[11px]">
                <CheckCircle2 className="w-3 h-3" />
                Yayında (Vitrin & B2B Açık)
              </span>
            ) : currentStatus === 'ARCHIVED' ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zinc-200 text-zinc-700 font-medium text-[11px]">
                Arşivde
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium text-[11px]">
                Taslak (Henüz Yayında Değil)
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isSubmitting}
              onClick={() => onOpenChange(false)}
            >
              Vazgeç
            </Button>

            {mode === 'create' ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit('DRAFT')}
                >
                  {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  Taslak Olarak Kaydet
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit('ACTIVE')}
                >
                  {isSubmitting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  )}
                  Kaydet ve Yayınla
                </Button>
              </>
            ) : isPublished ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit('DRAFT')}
                >
                  <EyeOff className="w-3.5 h-3.5" />
                  Yayından Kaldır (Taslağa Al)
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit('ACTIVE')}
                >
                  {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  Değişiklikleri Kaydet
                </Button>
              </>
            ) : (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit('DRAFT')}
                >
                  {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  Taslak Olarak Kaydet
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit('ACTIVE')}
                >
                  {isSubmitting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  )}
                  Kaydet ve Yayınla
                </Button>
              </>
            )}
          </div>
        </div>
      }
    >
      <div className="space-y-5 text-xs">
        {serverError && (
          <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-800 font-medium">
            {serverError}
          </div>
        )}

        {/* Segmented tab navigation */}
        <div
          role="tablist"
          aria-label="Ürün düzenleme sekmeleri"
          className="flex overflow-x-auto sm:flex-wrap gap-1 p-1 bg-muted/60 border border-border rounded-lg"
        >
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            const hasTabError = Object.keys(fieldErrors).some(
              (key) => resolveTabForField(key) === tab.id
            );
            const countHint =
              tab.id === 'medya'
                ? draft.galleryImages.length +
                  (draft.reelsVideoUrl.trim() ? 1 : 0) +
                  (draft.spin360Url.trim() ? 1 : 0)
                : tab.id === 'tas-montur'
                  ? stoneLines.length
                  : tab.id === 'varyantlar'
                    ? draft.variants?.length ?? 0
                    : null;
            return (
              <Button
                key={tab.id}
                type="button"
                role="tab"
                variant="ghost"
                size="xs"
                aria-selected={active}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'h-auto px-2.5 py-2 rounded-md text-xs font-medium whitespace-nowrap gap-1.5 shrink-0',
                  active && 'bg-card text-foreground shadow-xs border border-border'
                )}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                <span>{tab.label}</span>
                {countHint !== null && countHint > 0 && (
                  <span className="font-mono text-[11px] text-muted-foreground">({countHint})</span>
                )}
                {hasTabError && (
                  <span className="w-1.5 h-1.5 rounded-full bg-red-600 shrink-0" title="Bu sekmede hata var" />
                )}
              </Button>
            );
          })}
        </div>

        {/* ===================================================================
            TAB 1: GENEL, STOK, ÖLÇÜ & FİZİKSEL ÖZELLİKLER
           =================================================================== */}
        {activeTab === 'genel' && (
          <div className="space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">Ana Model Kodu (Parent SKU)</Label>
                <Input
                  type="text"
                  value={draft.parentSku}
                  disabled={mode === 'edit'}
                  onChange={(e) => patchDraft('parentSku', e.target.value)}
                  placeholder="Örn. SE055"
                  className="font-mono"
                />
                {fieldErrors.parentSku && (
                  <p className="text-[11px] text-red-700">{fieldErrors.parentSku}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Barkod</Label>
                <Input
                  type="text"
                  value={draft.barcode}
                  onChange={(e) => patchDraft('barcode', e.target.value)}
                  placeholder="Örn. P692105"
                  className="font-mono"
                />
              </div>

              <div className="sm:col-span-2 space-y-1.5">
                <Label className="font-medium block">Ürün Başlığı</Label>
                <Input
                  type="text"
                  value={draft.title}
                  onChange={(e) => patchDraft('title', e.target.value)}
                  placeholder="Örn. 0.70 Karat F/VS1 Pırlanta Tektaş Yüzük"
                />
                {fieldErrors.title && (
                  <p className="text-[11px] text-red-700">{fieldErrors.title}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">Ürün Tipi</Label>
                <select
                  value={draft.productType}
                  onChange={(e) => {
                    const productType = e.target.value;
                    const productKind = resolveProductKind({ productType });
                    setDraft((prev) => ({ ...prev, productType, productKind }));
                    setServerError(null);
                  }}
                  className={FIELD_SELECT_CLASS}
                >
                  <option value="">
                    {productTypeOpts.isLoading ? 'Tanımlar yükleniyor...' : 'Seçiniz'}
                  </option>
                  {withCurrentOption(productTypeOpts.options, draft.productType).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-muted-foreground">
                  Kind: {resolveProductKind(draft)}
                  {resolveProductKind(draft) === 'FINISHED' && ' · Bitmiş ürün detayı'}
                  {resolveProductKind(draft) === 'MOUNTING' && ' · Montür detayı + karat aralığı'}
                  {resolveProductKind(draft) === 'LOOSE_STONE' && ' · Serbest taş 4C / maliyet'}
                </p>
              </div>
              <div className="space-y-1.5">
                <Label className="font-medium block">Kategori</Label>
                <select
                  value={draft.category}
                  onChange={(e) => {
                    const category = e.target.value;
                    setDraft((prev) => ({
                      ...prev,
                      category,
                      subCategory: '',
                      chainType: '',
                      claspType: '',
                    }));
                    setFieldErrors((prev) => {
                      const copy = { ...prev };
                      delete copy.category;
                      delete copy.subCategory;
                      return copy;
                    });
                    setServerError(null);
                  }}
                  className={FIELD_SELECT_CLASS}
                  disabled={categoryOpts.isLoading || categoryOpts.isError}
                >
                  <option value="">
                    {categoryOpts.isLoading
                      ? 'Tanımlar yükleniyor...'
                      : categoryOpts.options.length === 0
                        ? 'Tanım tablosunda aktif kayıt bulunamadı'
                        : 'Seçiniz'}
                  </option>
                  {categoryOptions.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Alt Kategori</Label>
                <select
                  value={draft.subCategory}
                  onChange={(e) => patchDraft('subCategory', e.target.value)}
                  className={FIELD_SELECT_CLASS}
                  disabled={!draft.category}
                >
                  <option value="">
                    {draft.category ? 'Seçiniz' : 'Önce kategori seçin'}
                  </option>
                  {subCategoryOptions.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
                {fieldErrors.subCategory && (
                  <p className="text-[11px] text-red-700">{fieldErrors.subCategory}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Koleksiyon</Label>
                <select
                  value={draft.collection}
                  onChange={(e) => {
                    const collection = e.target.value;
                    setDraft((prev) => ({ ...prev, collection, ageGroup: '' }));
                    setFieldErrors((prev) => {
                      const copy = { ...prev };
                      delete copy.collection;
                      delete copy.ageGroup;
                      return copy;
                    });
                    setServerError(null);
                  }}
                  className={FIELD_SELECT_CLASS}
                >
                  <option value="">
                    {collectionOpts.isLoading ? 'Tanımlar yükleniyor...' : 'Seçiniz'}
                  </option>
                  {collectionOptions.map((col) => (
                    <option key={col.value} value={col.value}>
                      {col.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">Teknik / Stil</Label>
                <select
                  value={draft.styleTechnique}
                  onChange={(e) => patchDraft('styleTechnique', e.target.value)}
                  className={FIELD_SELECT_CLASS}
                >
                  <option value="">Seçiniz</option>
                  {withCurrentOption(styleOpts.options, draft.styleTechnique).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="font-medium block">Özel Gün</Label>
                <select
                  value={draft.occasion}
                  onChange={(e) => patchDraft('occasion', e.target.value)}
                  className={FIELD_SELECT_CLASS}
                >
                  <option value="">Seçiniz</option>
                  {withCurrentOption(occasionOpts.options, draft.occasion).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="font-medium block">Yaş Grubu</Label>
                <select
                  value={draft.ageGroup}
                  onChange={(e) => patchDraft('ageGroup', e.target.value)}
                  className={FIELD_SELECT_CLASS}
                  disabled={!draft.collection}
                >
                  <option value="">
                    {draft.collection ? 'Seçiniz' : 'Önce koleksiyon seçin'}
                  </option>
                  {withCurrentOption(ageGroupOpts.options, draft.ageGroup).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="font-medium block">Metal Adı</Label>
                <select
                  value={draft.metalName}
                  onChange={(e) => {
                    const metalName = e.target.value;
                    setDraft((prev) => ({
                      ...prev,
                      metalName,
                      purityCode: '' as PurityCode,
                      metalColor: '' as MetalColor,
                      availableColors: [],
                    }));
                    setFieldErrors((prev) => {
                      const copy = { ...prev };
                      delete copy.metalName;
                      delete copy.purityCode;
                      delete copy.metalColor;
                      return copy;
                    });
                    setServerError(null);
                  }}
                  className={FIELD_SELECT_CLASS}
                >
                  <option value="">
                    {metalNameOpts.isLoading ? 'Tanımlar yükleniyor...' : 'Seçiniz'}
                  </option>
                  {withCurrentOption(metalNameOpts.options, draft.metalName).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Metal, Colors & Stock */}
            <div className="pt-4 border-t border-border space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Maden Ayarı</Label>
                  <select
                    value={draft.purityCode}
                    onChange={(e) => patchDraft('purityCode', e.target.value as PurityCode)}
                    className={cn(FIELD_SELECT_CLASS, 'w-full font-mono')}
                    disabled={!draft.metalName || purityOpts.isLoading || purityOpts.isError}
                  >
                    <option value="">
                      {purityOpts.isLoading
                        ? 'Tanımlar yükleniyor...'
                        : !draft.metalName
                          ? 'Önce metal seçin'
                          : purityOpts.options.length === 0
                            ? 'Tanım tablosunda aktif kayıt bulunamadı'
                            : 'Seçiniz'}
                    </option>
                    {purityOptions.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                  {purityOpts.isError ? (
                    <p className="text-[11px] text-rose-600">
                      Ayar tanımları yüklenemedi.{' '}
                      <button
                        type="button"
                        className="underline font-medium"
                        onClick={() => void purityOpts.refetch()}
                      >
                        Tekrar dene
                      </button>
                    </p>
                  ) : null}
                </div>

                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Varsayılan Renk</Label>
                  <select
                    value={draft.metalColor}
                    onChange={(e) => {
                      const nextColor = e.target.value as MetalColor;
                      setDraft((prev) => ({
                        ...prev,
                        metalColor: nextColor,
                        availableColors:
                          nextColor && !prev.availableColors.includes(nextColor)
                            ? [...prev.availableColors, nextColor]
                            : prev.availableColors,
                      }));
                      setFieldErrors((prev) => {
                        const copy = { ...prev };
                        delete copy.metalColor;
                        return copy;
                      });
                      setServerError(null);
                    }}
                    className={FIELD_SELECT_CLASS}
                    disabled={!draft.metalName || metalColorOpts.isLoading}
                  >
                    <option value="">
                      {!draft.metalName
                        ? 'Önce metal seçin'
                        : metalColorOpts.isLoading
                          ? 'Tanımlar yükleniyor...'
                          : 'Seçiniz'}
                    </option>
                    {colorOptions.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Satışa Açık Maden Renkleri</Label>
                <div className="flex flex-wrap items-center gap-2">
                  {metalColorOpts.isLoading ? (
                    <span className="text-xs text-muted-foreground">Tanımlar yükleniyor...</span>
                  ) : null}
                  {!metalColorOpts.isLoading && !draft.metalName ? (
                    <span className="text-xs text-muted-foreground">Önce maden adı seçin.</span>
                  ) : null}
                  {!metalColorOpts.isLoading && draft.metalName && COLORS.length === 0 ? (
                    <span className="text-xs text-rose-600">
                      Seçilen metal ({draft.metalName}) için tanım tablosunda aktif renk bulunamadı.{' '}
                      <Link to="/ops/tanimlar" className="underline text-foreground">
                        Tanım Yönetimi
                      </Link>
                    </span>
                  ) : null}
                  {COLORS.map((c) => {
                    const selected = draft.availableColors.includes(c as MetalColor);
                    return (
                      <button
                        key={c}
                        type="button"
                        onClick={() => handleToggleColor(c as MetalColor)}
                        className={`px-3 py-1.5 rounded-md border text-xs font-medium transition-colors cursor-pointer shrink-0 ${
                          selected
                            ? 'bg-foreground text-primary-foreground border-foreground'
                            : 'bg-card text-muted-foreground border-input hover:border-foreground/50'
                        }`}
                      >
                        {c}
                      </button>
                    );
                  })}
                </div>
              </div>

              <p className="text-[11px] text-muted-foreground rounded-md border border-dashed border-border px-3 py-2">
                Varsayılan ayar/renk katalog varsayılanıdır. Satılabilir kombinasyonlar{' '}
                <button
                  type="button"
                  className="underline font-medium text-foreground cursor-pointer"
                  onClick={() => setActiveTab('varyantlar')}
                >
                  Varyantlar
                </button>{' '}
                sekmesinde; fiziksel stok{' '}
                <button
                  type="button"
                  className="underline font-medium text-foreground cursor-pointer"
                  onClick={() => setActiveTab('stok')}
                >
                  Stok &amp; Depo
                </button>{' '}
                sekmesinde yönetilir.
              </p>
            </div>

            {/* Physical Dimensions & Sizes */}
            <div className="pt-4 border-t border-border space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">
                    Brüt Ağırlık (gr) <span className="text-rose-500">*</span>
                  </Label>
                  <Input
                    type="number"
                    step="0.01"
                    min={0.01}
                    value={draft.grossWeightGram || ''}
                    placeholder="ör. 3.50"
                    onChange={(e) => {
                      const val = Number(e.target.value) || 0;
                      patchDraft('grossWeightGram', val);
                      if (val > 0) {
                        setFieldErrors((prev) => {
                          const copy = { ...prev };
                          delete copy.grossWeightGram;
                          return copy;
                        });
                      }
                    }}
                    className="text-right font-mono tabular-nums"
                  />
                  {fieldErrors.grossWeightGram && (
                    <p className="text-[11px] text-red-700 font-medium">{fieldErrors.grossWeightGram}</p>
                  )}
                </div>
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Varsayılan Ölçü</Label>
                  <Input
                    type="number"
                    min={6}
                    max={70}
                    value={draft.variantSize}
                    onChange={(e) =>
                      patchDraft('variantSize', Math.max(6, Math.round(Number(e.target.value) || 14)))
                    }
                    className="text-right font-mono tabular-nums"
                  />
                </div>
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Genişlik (mm)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    value={draft.widthMm}
                    onChange={(e) => patchDraft('widthMm', Number(e.target.value) || 0)}
                    className="text-right font-mono tabular-nums"
                  />
                </div>
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Kalınlık (mm)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    value={draft.thicknessMm}
                    onChange={(e) => patchDraft('thicknessMm', Number(e.target.value) || 0)}
                    className="text-right font-mono tabular-nums"
                  />
                </div>
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Yükseklik (mm)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    value={draft.heightMm}
                    onChange={(e) => patchDraft('heightMm', Number(e.target.value) || 0)}
                    className="text-right font-mono tabular-nums"
                  />
                </div>
                <div className="flex items-end pb-2 col-span-2 sm:col-span-1">
                  <Label className="inline-flex items-center gap-2 font-medium cursor-pointer">
                    <input
                      type="checkbox"
                      checked={draft.isResizable}
                      onChange={(e) => patchDraft('isResizable', e.target.checked)}
                      className="rounded border-input"
                    />
                    <span>Ölçü Değişebilir</span>
                  </Label>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Zincir Tipi</Label>
                  <select
                    value={draft.chainType}
                    onChange={(e) => patchDraft('chainType', e.target.value)}
                    className={FIELD_SELECT_CLASS}
                    disabled={!draft.category}
                  >
                    <option value="">
                      {draft.category ? '—' : 'Önce kategori seçin'}
                    </option>
                    {withCurrentOption(chainOpts.options, draft.chainType).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">Kopça Tipi</Label>
                  <select
                    value={draft.claspType}
                    onChange={(e) => patchDraft('claspType', e.target.value)}
                    className={FIELD_SELECT_CLASS}
                    disabled={!draft.category}
                  >
                    <option value="">
                      {draft.category ? '—' : 'Önce kategori seçin'}
                    </option>
                    {withCurrentOption(claspOpts.options, draft.claspType).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5 min-w-0">
                  <Label className="font-medium block">
                    Ürün Satış Kanalları <span className="text-rose-500">*</span>
                  </Label>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {channelOptions.map((ch) => {
                      const selected = (draft.salesChannels ?? []).includes(ch.code);
                      return (
                        <button
                          key={ch.code}
                          type="button"
                          onClick={() => {
                            const curr = draft.salesChannels ?? [];
                            const next = selected
                              ? curr.filter((c) => c !== ch.code)
                              : [...curr, ch.code];
                            patchDraft('salesChannels', next);
                            if (next.length > 0) {
                              setFieldErrors((prev) => {
                                const copy = { ...prev };
                                delete copy.salesChannels;
                                return copy;
                              });
                            }
                          }}
                          className={`px-2.5 py-1.5 rounded-md border text-[11px] font-medium cursor-pointer shrink-0 ${
                            selected
                              ? 'bg-foreground text-primary-foreground border-foreground'
                              : 'bg-card text-muted-foreground border-input hover:border-foreground/40'
                          }`}
                        >
                          {ch.label}
                        </button>
                      );
                    })}
                  </div>
                  {fieldErrors.salesChannels && (
                    <p className="text-[11px] text-red-700 font-medium">{fieldErrors.salesChannels}</p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Mevcut Ölçüler</Label>
                <div className="flex flex-wrap items-center gap-1.5">
                  {draft.availableSizes.map((sz) => (
                    <span
                      key={sz}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-border bg-muted/50 font-mono text-foreground"
                    >
                      {sz}
                      <button
                        type="button"
                        onClick={() => handleRemoveSize(sz)}
                        aria-label={`${sz} ölçüsünü kaldır`}
                        className="text-muted-foreground hover:text-red-700 cursor-pointer"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  <div className="inline-flex items-center gap-1 ml-1">
                    <Input
                      type="number"
                      min={6}
                      max={70}
                      value={newSizeInput}
                      onChange={(e) => setNewSizeInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddSize();
                        }
                      }}
                      placeholder="Ölçü"
                      className="w-16 font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={handleAddSize}
                      className="px-2.5 py-1 rounded-md border border-input bg-card text-foreground hover:bg-muted/50 cursor-pointer"
                    >
                      Ekle
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="font-medium block">Ürün Açıklaması</Label>
              <textarea
                rows={3}
                value={draft.description}
                onChange={(e) => patchDraft('description', e.target.value)}
                placeholder="Taş kalitesi, ayar, işçilik ve vitrin metnini girin..."
                className={FIELD_TEXTAREA_CLASS}
              />
              {fieldErrors.description && (
                <p className="text-[11px] text-red-700">{fieldErrors.description}</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'varyantlar' && (
          <ProductVariantsPanel
            product={draft}
            productKind={resolveProductKind(draft)}
            purityOptions={purityOptions.map((o) => o.value)}
            colorOptions={colorOptions.map((o) => o.value)}
            mode={mode}
            pendingMatrix={pendingMatrix}
            onPendingMatrixChange={setPendingMatrix}
          />
        )}

        {activeTab === 'stok' && (
          <ProductStockPanel
            parentSku={draft.parentSku}
            mode={mode}
            catalogStockQty={draft.stockQty}
            onInitialStockQtyChange={(qty) => patchDraft('stockQty', qty)}
            stockStatus={draft.stockStatus}
            onStockStatusChange={(v) =>
              patchDraft('stockStatus', v as 'Stokta' | 'Tükendi' | 'Siparişe Özel')
            }
            leadTimeDays={draft.leadTimeDays}
            onLeadTimeChange={(v) => patchDraft('leadTimeDays', v)}
            ownershipType={draft.ownershipType}
            onOwnershipChange={(v) =>
              patchDraft('ownershipType', v as 'Öz Mal' | 'Konsinye (Emanet)')
            }
            ownershipOptions={withCurrentOption(ownershipOpts.options, draft.ownershipType)}
            stockStatusOptions={withCurrentOption(stockStatusOpts.options, draft.stockStatus)}
          />
        )}

        {/* ===================================================================
            TAB: TAŞ SATIRLARI, MONTÜR MÜHENDİSLİĞİ & SERTİFİKA
           =================================================================== */}
        {activeTab === 'tas-montur' && (
          <div className="space-y-5">
            <p className="text-[11px] text-muted-foreground rounded-md border border-dashed border-border px-3 py-2">
              Bu sekme ürün mühendisliği / sertifika şablonudur (Finished · Mounting · LooseStone detail).
              Satılabilir renk/ayar/ölçü/karat kombinasyonları{' '}
              <button
                type="button"
                className="underline font-medium text-foreground cursor-pointer"
                onClick={() => setActiveTab('varyantlar')}
              >
                Varyantlar
              </button>{' '}
              sekmesindedir. Sertifikalı tekil taşlar ayrı LOOSE_STONE ürün + stok olarak ele alınır.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">Brüt Ağırlık (gr)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min={0.1}
                  value={draft.grossWeightGram}
                  onChange={(e) => patchDraft('grossWeightGram', Number(e.target.value) || 0)}
                  className="text-right font-mono tabular-nums"
                />
                {fieldErrors.grossWeightGram && (
                  <p className="text-[11px] text-red-700">{fieldErrors.grossWeightGram}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Fire Oranı (%)</Label>
                <Input
                  type="number"
                  step="0.25"
                  min={0}
                  max={30}
                  value={draft.fireRatePct}
                  onChange={(e) => patchDraft('fireRatePct', Number(e.target.value) || 0)}
                  className="text-right font-mono tabular-nums"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Ana Taş Tipi</Label>
                <select
                  value={draft.stoneType}
                  onChange={(e) => {
                    const stoneType = e.target.value as StoneType;
                    setDraft((prev) => ({
                      ...prev,
                      stoneType,
                      stoneClarity: '',
                      stoneColorGrade: '',
                      stoneCutShape: '',
                      stoneCutGrade: '',
                      stoneOrigin: '',
                      settingType: '',
                    }));
                    setServerError(null);
                  }}
                  className={FIELD_SELECT_CLASS}
                  disabled={stoneTypeOpts.isLoading || stoneTypeOpts.isError}
                >
                  <option value="">
                    {stoneTypeOpts.isLoading
                      ? 'Tanımlar yükleniyor...'
                      : stoneTypeOpts.options.length === 0
                        ? 'Tanım tablosunda aktif kayıt bulunamadı'
                        : 'Seçiniz'}
                  </option>
                  {stoneOptions.map((st) => (
                    <option key={st.value} value={st.value}>
                      {st.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Taş Ölçü Birimi</Label>
                <select
                  value={draft.stoneMeasureUnit}
                  onChange={(e) =>
                    patchDraft('stoneMeasureUnit', e.target.value as StoneMeasureUnit)
                  }
                  className={cn(FIELD_SELECT_CLASS, 'w-full font-mono')}
                >
                  <option value="ct">Karat (ct)</option>
                  <option value="gr">Gram (gr)</option>
                  <option value="mm">Milimetre (mm)</option>
                </select>
              </div>
            </div>

            {/* Multi-Stone Lines Editor */}
            <div className="space-y-3 pt-4 border-t border-border">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Çoklu Taş Satırları</h3>
                  <p className="text-[11px] text-muted-foreground">
                    Merkez: <strong className="font-mono text-foreground">{formatTrNumber(draft.centerStoneCarat, 3)} ct</strong>
                    {' · '}Yan/Pavé: <strong className="font-mono text-foreground">{formatTrNumber(draft.sideStoneCarat, 3)} ct</strong>
                    {' · '}Taş Darası: <strong className="font-mono text-foreground">{formatTrNumber(liveComputed.stoneTareGram, 4)} gr</strong>
                    {' · '}Net Maden: <strong className="font-mono text-foreground">{formatTrNumber(liveComputed.netMetalGram, 4)} gr</strong>
                  </p>
                </div>
                <Button
                  type="button"
                  variant="success"
                  size="sm"
                  onClick={handleAddStoneLine}
                >
                  <Plus className="w-3.5 h-3.5" />
                  Taş Satırı Ekle
                </Button>
              </div>

              {stoneLines.length === 0 ? (
                <div className="px-4 py-5 border border-dashed border-input rounded-md text-center text-muted-foreground">
                  Taş satırı tanımlanmamış. Taşsız bir model değilse yukarıdan satır ekleyebilirsiniz.
                </div>
              ) : (
                <div className="border border-border rounded-md overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead className="bg-muted/50 border-b border-border text-[11px] text-muted-foreground">
                      <tr>
                        <th className="py-2 px-2.5 font-medium">Rol</th>
                        <th className="py-2 px-2.5 font-medium">Taş Tipi</th>
                        <th className="py-2 px-2.5 font-medium">Adet</th>
                        <th className="py-2 px-2.5 font-medium">Birim Karat</th>
                        <th className="py-2 px-2.5 font-medium">Birim</th>
                        <th className="py-2 px-2.5 font-medium">Renk / Berraklık</th>
                        <th className="py-2 px-2.5 font-medium">Kesim</th>
                        <th className="py-2 px-2.5 font-medium text-right">Toplam</th>
                        <th className="py-2 px-2.5" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {stoneLines.map((line) => (
                        <tr key={line.id}>
                          <td className="py-2 px-2">
                            <select
                              value={line.role}
                              onChange={(e) =>
                                handleUpdateStoneLine(line.id, {
                                  role: e.target.value as StoneLineRole,
                                })
                              }
                              className={cn(FIELD_SELECT_CLASS, 'h-8 text-xs')}
                            >
                              {STONE_ROLES.map((r) => (
                                <option key={r.value} value={r.value}>
                                  {r.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 px-2">
                            <select
                              value={line.stoneType}
                              onChange={(e) =>
                                handleUpdateStoneLine(line.id, {
                                  stoneType: e.target.value as StoneType,
                                  colorGrade: '',
                                  clarity: '',
                                  cutShape: '',
                                })
                              }
                              className={cn(FIELD_SELECT_CLASS, 'h-8 text-xs')}
                            >
                              {stoneOptions.map((st) => (
                                <option key={st.value} value={st.value}>
                                  {st.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 px-2">
                            <Input
                              type="number"
                              min={1}
                              value={line.count}
                              onChange={(e) =>
                                handleUpdateStoneLine(line.id, {
                                  count: Math.max(1, Math.round(Number(e.target.value) || 1)),
                                })
                              }
                              className={cn(FIELD_SELECT_CLASS, 'h-8 w-16 text-xs text-right font-mono tabular-nums')}
                            />
                          </td>
                          <td className="py-2 px-2">
                            <Input
                              type="number"
                              step="0.005"
                              min={0}
                              value={line.carat}
                              onChange={(e) =>
                                handleUpdateStoneLine(line.id, {
                                  carat: Math.max(0, Number(e.target.value) || 0),
                                })
                              }
                              className={cn(FIELD_SELECT_CLASS, 'h-8 w-20 text-xs text-right font-mono tabular-nums')}
                            />
                          </td>
                          <td className="py-2 px-2">
                            <select
                              value={line.measureUnit}
                              onChange={(e) =>
                                handleUpdateStoneLine(line.id, {
                                  measureUnit: e.target.value as StoneMeasureUnit,
                                })
                              }
                              className={cn(FIELD_SELECT_CLASS, 'font-mono h-8 text-xs')}
                            >
                              <option value="ct">ct</option>
                              <option value="gr">gr</option>
                              <option value="mm">mm</option>
                            </select>
                          </td>
                          <td className="py-2 px-2">
                            <div className="flex items-center gap-1">
                              <select
                                value={line.colorGrade ?? ''}
                                onChange={(e) =>
                                  handleUpdateStoneLine(line.id, { colorGrade: e.target.value })
                                }
                                className={cn(FIELD_SELECT_CLASS, 'h-8 w-14 text-xs px-1')}
                                disabled={
                                  filterOptionsByParent(colorGradeAllOpts.options, line.stoneType)
                                    .length === 0
                                }
                              >
                                <option value="">—</option>
                                {withCurrentOption(
                                  filterOptionsByParent(colorGradeAllOpts.options, line.stoneType),
                                  line.colorGrade ?? ''
                                ).map((o) => (
                                  <option key={o.value} value={o.value}>
                                    {o.label}
                                  </option>
                                ))}
                              </select>
                              <select
                                value={line.clarity ?? ''}
                                onChange={(e) =>
                                  handleUpdateStoneLine(line.id, { clarity: e.target.value })
                                }
                                className={cn(FIELD_SELECT_CLASS, 'h-8 w-16 text-xs px-1')}
                                disabled={
                                  filterOptionsByParent(clarityAllOpts.options, line.stoneType)
                                    .length === 0
                                }
                              >
                                <option value="">—</option>
                                {withCurrentOption(
                                  filterOptionsByParent(clarityAllOpts.options, line.stoneType),
                                  line.clarity ?? ''
                                ).map((o) => (
                                  <option key={o.value} value={o.value}>
                                    {o.label}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </td>
                          <td className="py-2 px-2">
                            <select
                              value={line.cutShape ?? ''}
                              onChange={(e) =>
                                handleUpdateStoneLine(line.id, { cutShape: e.target.value })
                              }
                              className={cn(FIELD_SELECT_CLASS, 'h-8 w-28 text-xs')}
                              disabled={
                                filterOptionsByParent(stoneCutAllOpts.options, line.stoneType)
                                  .length === 0
                              }
                            >
                              <option value="">—</option>
                              {withCurrentOption(
                                filterOptionsByParent(stoneCutAllOpts.options, line.stoneType),
                                line.cutShape ?? ''
                              ).map((o) => (
                                <option key={o.value} value={o.value}>
                                  {o.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground whitespace-nowrap">
                            {formatTrNumber(line.count * line.carat, 3)} {line.measureUnit}
                          </td>
                          <td className="py-2 px-2 text-right">
                            <button
                              type="button"
                              onClick={() => handleRemoveStoneLine(line.id)}
                              aria-label="Taş satırını sil"
                              data-delete="true"
                              className="p-1 text-destructive hover:bg-destructive/10 cursor-pointer rounded-md"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Mount Engineering */}
            <div className="pt-4 border-t border-border space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-foreground">Montür Teknik Yapısı</h3>
                <span
                  className={`text-[11px] font-medium ${
                    liveComputed.isCaratWithinMountRange ? 'text-emerald-700' : 'text-red-700'
                  }`}
                >
                  {liveComputed.isCaratWithinMountRange
                    ? 'Merkez taş karatı montür aralığına uygun'
                    : 'Uyarı: Merkez taş karatı montür izinli aralığı dışında'}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <div className="space-y-1.5">
                  <Label className="font-medium block">Montür Tipi</Label>
                  <select
                    value={mountSpec.structure}
                    onChange={(e) =>
                      patchDraft('mountSpec', {
                        ...mountSpec,
                        structure: e.target.value as MountStructureType,
                      })
                    }
                    className={cn(FIELD_SELECT_CLASS, 'w-full')}
                  >
                    <option value="FULL">Tek Parça (FULL)</option>
                    <option value="HEAD_BAND">Taç + Kol (HEAD_BAND)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label className="font-medium block">Min Karat (ct)</Label>
                  <Input
                    type="number"
                    step="0.05"
                    min={0}
                    value={mountSpec.allowedCaratMin}
                    onChange={(e) =>
                      patchDraft('mountSpec', {
                        ...mountSpec,
                        allowedCaratMin: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    className="text-right font-mono tabular-nums"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="font-medium block">Max Karat (ct)</Label>
                  <Input
                    type="number"
                    step="0.05"
                    min={0}
                    value={mountSpec.allowedCaratMax}
                    onChange={(e) =>
                      patchDraft('mountSpec', {
                        ...mountSpec,
                        allowedCaratMax: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    className="text-right font-mono tabular-nums"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="font-medium block">Taç Kodu / gr</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    <Input
                      type="text"
                      value={mountSpec.headCode ?? ''}
                      onChange={(e) =>
                        patchDraft('mountSpec', { ...mountSpec, headCode: e.target.value })
                      }
                      placeholder="TAC-050"
                      className="px-2 py-2 font-mono border border-input rounded-md bg-card"
                    />
                    <Input
                      type="number"
                      step="0.01"
                      min={0}
                      value={mountSpec.headWeightGram ?? 0}
                      onChange={(e) =>
                        patchDraft('mountSpec', {
                          ...mountSpec,
                          headWeightGram: Math.max(0, Number(e.target.value) || 0),
                        })
                      }
                      className="px-2 py-2 text-right font-mono tabular-nums border border-input rounded-md bg-card"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="font-medium block">Kol Kodu / gr</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    <Input
                      type="text"
                      value={mountSpec.bandCode ?? ''}
                      onChange={(e) =>
                        patchDraft('mountSpec', { ...mountSpec, bandCode: e.target.value })
                      }
                      placeholder="KOL-18"
                      className="px-2 py-2 font-mono border border-input rounded-md bg-card"
                    />
                    <Input
                      type="number"
                      step="0.01"
                      min={0}
                      value={mountSpec.bandWeightGram ?? 0}
                      onChange={(e) =>
                        patchDraft('mountSpec', {
                          ...mountSpec,
                          bandWeightGram: Math.max(0, Number(e.target.value) || 0),
                        })
                      }
                      className="px-2 py-2 text-right font-mono tabular-nums border border-input rounded-md bg-card"
                    />
                  </div>
                </div>
              </div>

              {isMountingKind && (
                <div className="pt-3 space-y-3 rounded-md border border-border/80 bg-muted/20 p-3">
                  <div>
                    <h4 className="text-sm font-semibold text-foreground">DYO Uyumluluk &amp; Mıhlama</h4>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Serbest taş eşleşmesi: şekil whitelist, karat/mm toleransı ve mıhlama işçiliği.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <Label className="font-medium block">Uyumlu Taş Şekilleri</Label>
                    <div className="flex flex-wrap gap-1.5">
                      {DYO_COMPATIBLE_SHAPE_OPTIONS.map((shape) => {
                        const selected = (mountingDetail.compatibleShapes ?? []).includes(shape);
                        return (
                          <button
                            key={shape}
                            type="button"
                            onClick={() => {
                              const current = mountingDetail.compatibleShapes ?? [];
                              const next = selected
                                ? current.filter((s) => s !== shape)
                                : [...current, shape];
                              patchMountingDetail({ compatibleShapes: next });
                            }}
                            className={cn(
                              'px-2.5 py-1 text-[11px] font-mono tracking-wide border rounded-md cursor-pointer',
                              selected
                                ? 'bg-foreground text-background border-foreground'
                                : 'bg-card text-muted-foreground border-input hover:border-foreground/40'
                            )}
                          >
                            {shape}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Min Karat</Label>
                      <Input
                        type="number"
                        step="0.05"
                        min={0}
                        value={mountingDetail.minCarat ?? mountSpec.allowedCaratMin}
                        onChange={(e) => {
                          const v = Math.max(0, Number(e.target.value) || 0);
                          patchDraft('mountSpec', { ...mountSpec, allowedCaratMin: v });
                          patchMountingDetail({ minCarat: v });
                        }}
                        className="text-right font-mono tabular-nums"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Max Karat</Label>
                      <Input
                        type="number"
                        step="0.05"
                        min={0}
                        value={mountingDetail.maxCarat ?? mountSpec.allowedCaratMax}
                        onChange={(e) => {
                          const v = Math.max(0, Number(e.target.value) || 0);
                          patchDraft('mountSpec', { ...mountSpec, allowedCaratMax: v });
                          patchMountingDetail({ maxCarat: v });
                        }}
                        className="text-right font-mono tabular-nums"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Mıhlama USD</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min={0}
                        value={mountingDetail.settingLaborUsd ?? 0}
                        onChange={(e) =>
                          patchMountingDetail({
                            settingLaborUsd: Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        className="text-right font-mono tabular-nums"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Mıhlama Tip Kodu</Label>
                      <Input
                        type="text"
                        value={mountingDetail.settingTypeCode ?? ''}
                        onChange={(e) => patchMountingDetail({ settingTypeCode: e.target.value })}
                        placeholder="6PRONG"
                        className="font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Min L (mm)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min={0}
                        value={mountingDetail.minLengthMm ?? ''}
                        onChange={(e) =>
                          patchMountingDetail({
                            minLengthMm: e.target.value === '' ? null : Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        className="text-right font-mono tabular-nums"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Max L (mm)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min={0}
                        value={mountingDetail.maxLengthMm ?? ''}
                        onChange={(e) =>
                          patchMountingDetail({
                            maxLengthMm: e.target.value === '' ? null : Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        className="text-right font-mono tabular-nums"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Min W (mm)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min={0}
                        value={mountingDetail.minWidthMm ?? ''}
                        onChange={(e) =>
                          patchMountingDetail({
                            minWidthMm: e.target.value === '' ? null : Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        className="text-right font-mono tabular-nums"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="font-medium block">Max W (mm)</Label>
                      <Input
                        type="number"
                        step="0.01"
                        min={0}
                        value={mountingDetail.maxWidthMm ?? ''}
                        onChange={(e) =>
                          patchMountingDetail({
                            maxWidthMm: e.target.value === '' ? null : Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        className="text-right font-mono tabular-nums"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Certificate & Setting */}
            <div className="pt-4 border-t border-border grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">Sertifika Kurumu</Label>
                <select
                  value={draft.certificateAgency}
                  onChange={(e) => {
                    patchDraft('certificateAgency', e.target.value);
                    patchDraft('hasCertificate', Boolean(e.target.value));
                  }}
                  className="w-full px-3 py-2 border border-input rounded-md bg-card"
                >
                  {CERT_AGENCIES.map((ag) => (
                    <option key={ag || 'none'} value={ag}>
                      {ag || 'Sertifikasız'}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Sertifika Numarası</Label>
                <Input
                  type="text"
                  value={draft.certificateNumber}
                  onChange={(e) => patchDraft('certificateNumber', e.target.value)}
                  placeholder="2141234567"
                  className={cn(FIELD_SELECT_CLASS, 'w-full font-mono')}
                />
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Mıhlama Tipi</Label>
                <select
                  value={draft.settingType}
                  onChange={(e) => patchDraft('settingType', e.target.value)}
                  className={FIELD_SELECT_CLASS}
                  disabled={settingOpts.options.length === 0}
                >
                  <option value="">
                    {draft.stoneType === 'Taşsız' ? 'Taşsız' : 'Seçiniz'}
                  </option>
                  {withCurrentOption(settingOpts.options, draft.settingType).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Taş Menşei / Kesim Kalitesi</Label>
                <div className="grid grid-cols-2 gap-1.5">
                  <select
                    value={draft.stoneOrigin}
                    onChange={(e) => patchDraft('stoneOrigin', e.target.value)}
                    className={FIELD_SELECT_CLASS}
                    disabled={stoneOriginOpts.options.length === 0}
                  >
                    <option value="">Menşei</option>
                    {withCurrentOption(stoneOriginOpts.options, draft.stoneOrigin).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={draft.stoneCutGrade}
                    onChange={(e) => patchDraft('stoneCutGrade', e.target.value)}
                    className={FIELD_SELECT_CLASS}
                    disabled={cutGradeOpts.options.length === 0}
                  >
                    <option value="">Kesim</option>
                    {withCurrentOption(cutGradeOpts.options, draft.stoneCutGrade).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB 3: FİYATLANDIRMA, MALİYET DEFTERİ & KANAL KURALLARI
           =================================================================== */}
        {activeTab === 'fiyatlandirma' && (
          <div className="space-y-5">
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
              <div>
                <span className="font-semibold">Otomatik Canlı Fiyat Yayını:</span>{' '}
                Maliyet, kâr marjı, taş, montür, ağırlık veya ayar alanlarında yapılan değişiklikler kaydedildiğinde ürünün canlı B2B ve B2C fiyatları otomatik olarak güncellenir.
              </div>
            </div>

            {/* Live Price Calculation Strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-muted/50 border border-border rounded-lg p-3.5">
              <div>
                <div className="text-[11px] text-muted-foreground">Fireli Has Altın</div>
                <div className="font-mono font-semibold text-sm text-zinc-600 tabular-nums mt-0.5">
                  {formatTrNumber(liveComputed.fireIncludedFineMetalGram, 4)} gr
                </div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Toplam Maliyet ({draft.ledger.lcCurrency})</div>
                <div className="font-mono font-semibold text-sm text-foreground tabular-nums mt-0.5">
                  {formatCurrencyValue(liveComputed.ledger.totalCostLc, draft.ledger.lcCurrency)}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">B2B Toptan Nihai</div>
                <div className="font-mono font-semibold text-sm text-foreground tabular-nums mt-0.5">
                  {liveComputed.ledger.hasB2bChannel
                    ? `${formatTrNumber(liveComputed.finalB2bPriceTry, 0)} TL`
                    : 'Kapalı'}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">B2C Vitrin Nihai</div>
                <div className="font-mono font-semibold text-sm text-foreground tabular-nums mt-0.5">
                  {liveComputed.ledger.hasB2cChannel
                    ? `${formatTrNumber(liveComputed.discountedB2cPriceTry, 0)} TL`
                    : 'Kapalı'}
                </div>
              </div>
            </div>

            {/* Pricing Mode & LC Currency */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2 space-y-1.5">
                <Label className="font-medium block">Fiyatlandırma Modeli</Label>
                <div className="grid grid-cols-2 gap-2">
                  {(
                    [
                      { id: '1', label: 'Model 1 · Detaylı Maliyet (Maden + İşçilik + Taş)' },
                      { id: '2', label: 'Model 2 · Tedarikçi Alış Fiyatı Üzerinden' },
                    ] as { id: PricingMode; label: string }[]
                  ).map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => patchDraft('pricingMode', opt.id)}
                      className={`px-3 py-2 text-left rounded-md border text-xs font-medium transition-colors cursor-pointer ${
                        draft.pricingMode === opt.id
                          ? 'bg-foreground text-white border-foreground'
                          : 'bg-card text-foreground border-input hover:border-foreground/50'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Defter Para Birimi (LC)</Label>
                <select
                  value={draft.ledger.lcCurrency}
                  onChange={(e) =>
                    patchLedger({ lcCurrency: e.target.value as FxCurrencyCode })
                  }
                  className={cn(FIELD_SELECT_CLASS, 'w-full font-mono')}
                >
                  {FX_CURRENCIES.map((cur) => (
                    <option key={cur} value={cur}>
                      {FX_CURRENCY_LABELS[cur]}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Cost Ledger Lines */}
            {draft.pricingMode === '1' ? (
              <div className="border border-border rounded-md overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="bg-muted/50 border-b border-border text-[11px] text-muted-foreground">
                    <tr>
                      <th className="py-2.5 px-3 font-medium">Maliyet Kalemi</th>
                      <th className="py-2.5 px-3 font-medium">Döviz (FC)</th>
                      <th className="py-2.5 px-3 font-medium text-right">Birim / Tutar (FC)</th>
                      <th className="py-2.5 px-3 font-medium text-right">Özel Kur (Ops.)</th>
                      <th className="py-2.5 px-3 font-medium text-right">
                        Hesaplanan ({draft.ledger.lcCurrency})
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">
                        Maden Maliyeti
                        <div className="text-[11px] font-normal text-muted-foreground">
                          Boş bırakılırsa canlı Has Altın × Fireli Has Gram kullanılır
                        </div>
                      </td>
                      <td className="py-2.5 px-3">
                        <select
                          value={draft.ledger.metalCurrency}
                          onChange={(e) =>
                            patchLedger({ metalCurrency: e.target.value as FxCurrencyCode })
                          }
                          className={cn(FIELD_SELECT_CLASS, 'font-mono')}
                        >
                          {FX_CURRENCIES.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="0.01"
                          value={draft.ledger.metalFcManual ?? ''}
                          onChange={(e) =>
                            patchLedger({
                              metalFcManual: e.target.value === '' ? null : Number(e.target.value),
                            })
                          }
                          placeholder="Otomatik"
                          className={cn(FIELD_SELECT_CLASS, 'w-28 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="0.01"
                          value={draft.ledger.metalRateOverride ?? ''}
                          onChange={(e) =>
                            patchLedger({
                              metalRateOverride:
                                e.target.value === '' ? null : Number(e.target.value),
                            })
                          }
                          placeholder="Matris"
                          className={cn(FIELD_SELECT_CLASS, 'w-24 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-foreground">
                        {formatCurrencyValue(liveComputed.ledger.metalLine.lcPrice, draft.ledger.lcCurrency)}
                      </td>
                    </tr>

                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">İşçilik Maliyeti</td>
                      <td className="py-2.5 px-3">
                        <select
                          value={draft.ledger.laborCurrency}
                          onChange={(e) =>
                            patchLedger({ laborCurrency: e.target.value as FxCurrencyCode })
                          }
                          className={cn(FIELD_SELECT_CLASS, 'font-mono')}
                        >
                          {FX_CURRENCIES.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="0.5"
                          min={0}
                          value={draft.ledger.laborFcPrice}
                          onChange={(e) =>
                            patchLedger({ laborFcPrice: Math.max(0, Number(e.target.value) || 0) })
                          }
                          className={cn(FIELD_SELECT_CLASS, 'w-28 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="0.01"
                          value={draft.ledger.laborRateOverride ?? ''}
                          onChange={(e) =>
                            patchLedger({
                              laborRateOverride:
                                e.target.value === '' ? null : Number(e.target.value),
                            })
                          }
                          placeholder="Matris"
                          className={cn(FIELD_SELECT_CLASS, 'w-24 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-foreground">
                        {formatCurrencyValue(liveComputed.ledger.laborLine.lcPrice, draft.ledger.lcCurrency)}
                      </td>
                    </tr>

                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Taş Maliyeti</td>
                      <td className="py-2.5 px-3">
                        <select
                          value={draft.ledger.stoneCurrency}
                          onChange={(e) =>
                            patchLedger({ stoneCurrency: e.target.value as FxCurrencyCode })
                          }
                          className={cn(FIELD_SELECT_CLASS, 'font-mono')}
                        >
                          {FX_CURRENCIES.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="1"
                          min={0}
                          value={draft.ledger.stoneFcPrice}
                          onChange={(e) =>
                            patchLedger({ stoneFcPrice: Math.max(0, Number(e.target.value) || 0) })
                          }
                          className={cn(FIELD_SELECT_CLASS, 'w-28 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="0.01"
                          value={draft.ledger.stoneRateOverride ?? ''}
                          onChange={(e) =>
                            patchLedger({
                              stoneRateOverride:
                                e.target.value === '' ? null : Number(e.target.value),
                            })
                          }
                          placeholder="Matris"
                          className={cn(FIELD_SELECT_CLASS, 'w-24 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-foreground">
                        {formatCurrencyValue(liveComputed.ledger.stoneLine.lcPrice, draft.ledger.lcCurrency)}
                      </td>
                    </tr>

                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Montür / Kutu / Diğer</td>
                      <td className="py-2.5 px-3">
                        <select
                          value={draft.ledger.mountingCurrency}
                          onChange={(e) =>
                            patchLedger({ mountingCurrency: e.target.value as FxCurrencyCode })
                          }
                          className={cn(FIELD_SELECT_CLASS, 'font-mono')}
                        >
                          {FX_CURRENCIES.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="1"
                          min={0}
                          value={draft.ledger.mountingFcPrice}
                          onChange={(e) =>
                            patchLedger({
                              mountingFcPrice: Math.max(0, Number(e.target.value) || 0),
                            })
                          }
                          className={cn(FIELD_SELECT_CLASS, 'w-28 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Input
                          type="number"
                          step="1"
                          min={0}
                          value={draft.ledger.otherCostFcPrice}
                          onChange={(e) =>
                            patchLedger({
                              otherCostFcPrice: Math.max(0, Number(e.target.value) || 0),
                            })
                          }
                          placeholder="Diğer (TRY)"
                          className={cn(FIELD_SELECT_CLASS, 'w-24 font-mono text-right tabular-nums')}
                        />
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-foreground">
                        {formatCurrencyValue(
                          liveComputed.ledger.mountingLine.lcPrice +
                            liveComputed.ledger.otherCostLine.lcPrice,
                          draft.ledger.lcCurrency
                        )}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 border border-border rounded-md bg-card">
                <div className="space-y-1.5">
                  <Label className="font-medium block">Tedarikçi Döviz Cinsi</Label>
                  <select
                    value={draft.ledger.supplierCurrency}
                    onChange={(e) =>
                      patchLedger({ supplierCurrency: e.target.value as FxCurrencyCode })
                    }
                    className={cn(FIELD_SELECT_CLASS, 'w-full font-mono')}
                  >
                    {FX_CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {FX_CURRENCY_LABELS[c]}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label className="font-medium block">Tedarikçi Alış Fiyatı</Label>
                  <Input
                    type="number"
                    step="1"
                    min={0}
                    value={draft.ledger.supplierFcPrice}
                    onChange={(e) =>
                      patchLedger({ supplierFcPrice: Math.max(0, Number(e.target.value) || 0) })
                    }
                    className="w-full text-right px-3 py-2 font-mono tabular-nums border border-input rounded-md bg-card"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="font-medium block">Özel Kur (Opsiyonel)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={draft.ledger.supplierRateOverride ?? ''}
                    onChange={(e) =>
                      patchLedger({
                        supplierRateOverride:
                          e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                    placeholder="Matris Kuru"
                    className="w-full text-right px-3 py-2 font-mono tabular-nums border border-input rounded-md bg-card"
                  />
                </div>
              </div>
            )}

            {/* Channel Rules (B2B / B2B_API / B2C_API — hardcoded) */}
            <div className="space-y-3 pt-4 border-t border-border">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">
                    Satış Kanalları, Kâr Marjı &amp; İndirim Kuralları
                  </h3>
                  <p className="text-[11px] text-muted-foreground">
                    Sabit kanallar: B2B, B2B API, B2C API. Operasyon akışına bağlıdır.
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  {!hasB2bRule && (
                    <button
                      type="button"
                      onClick={() => handleAddChannelRule('B2B')}
                      className="px-2.5 py-1.5 rounded-md border border-input bg-card text-foreground hover:bg-muted/50 font-medium cursor-pointer"
                    >
                      + B2B
                    </button>
                  )}
                  {!hasB2bApiRule && (
                    <button
                      type="button"
                      onClick={() => handleAddChannelRule('B2B_API')}
                      className="px-2.5 py-1.5 rounded-md border border-input bg-card text-foreground hover:bg-muted/50 font-medium cursor-pointer"
                    >
                      + B2B API
                    </button>
                  )}
                  {!hasB2cApiRule && (
                    <button
                      type="button"
                      onClick={() => handleAddChannelRule('B2C_API')}
                      className="px-2.5 py-1.5 rounded-md border border-input bg-card text-foreground hover:bg-muted/50 font-medium cursor-pointer"
                    >
                      + B2C API
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-2.5">
                {draft.ledger.channelRules.map((rule) => {
                  const computedCh = liveComputed.ledger.channels.find((c) => c.id === rule.id);
                  return (
                    <div
                      key={rule.id}
                      className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end p-3.5 border border-border rounded-md bg-card"
                    >
                      <div className="sm:col-span-2 space-y-1">
                        <Label className="text-[11px] font-medium text-muted-foreground block">Kanal</Label>
                        <select
                          value={rule.channel}
                          onChange={(e) =>
                            handleUpdateChannelRule(rule.id, {
                              channel: e.target.value as PricingChannelTarget,
                            })
                          }
                          className="w-full px-2 py-1.5 font-mono border border-input rounded bg-card"
                        >
                          <option value="B2B">B2B (Bayi Portalı)</option>
                          <option value="B2B_API">B2B API</option>
                          <option value="B2C_API">B2C API</option>
                        </select>
                      </div>

                      <div className="sm:col-span-3 space-y-1">
                        <Label className="text-[11px] font-medium text-muted-foreground block">Kâr Marjı</Label>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            step="0.5"
                            value={rule.profit.value}
                            onChange={(e) =>
                              handleUpdateChannelRule(rule.id, {
                                profit: { ...rule.profit, value: Number(e.target.value) || 0 },
                              })
                            }
                            className="w-full text-right px-2 py-1.5 font-mono tabular-nums border border-input rounded bg-card"
                          />
                          <select
                            value={rule.profit.unit}
                            onChange={(e) =>
                              handleUpdateChannelRule(rule.id, {
                                profit: { ...rule.profit, unit: e.target.value as AdjustmentUnit },
                              })
                            }
                            className="px-1.5 py-1.5 font-mono border border-input rounded bg-card"
                          >
                            {ADJUSTMENT_UNITS.map((u) => (
                              <option key={u} value={u}>
                                {u}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div className="sm:col-span-3 space-y-1">
                        <Label className="text-[11px] font-medium text-muted-foreground block">İndirim</Label>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            step="0.5"
                            value={rule.discount.value}
                            onChange={(e) =>
                              handleUpdateChannelRule(rule.id, {
                                discount: { ...rule.discount, value: Number(e.target.value) || 0 },
                              })
                            }
                            className="w-full text-right px-2 py-1.5 font-mono tabular-nums border border-input rounded bg-card"
                          />
                          <select
                            value={rule.discount.unit}
                            onChange={(e) =>
                              handleUpdateChannelRule(rule.id, {
                                discount: {
                                  ...rule.discount,
                                  unit: e.target.value as AdjustmentUnit,
                                },
                              })
                            }
                            className="px-1.5 py-1.5 font-mono border border-input rounded bg-card"
                          >
                            {ADJUSTMENT_UNITS.map((u) => (
                              <option key={u} value={u}>
                                {u}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div className="sm:col-span-2 space-y-1">
                        <Label className="text-[11px] font-medium text-muted-foreground block">Servis Bedeli</Label>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            step="0.5"
                            value={rule.platformFee.value}
                            onChange={(e) =>
                              handleUpdateChannelRule(rule.id, {
                                platformFee: {
                                  ...rule.platformFee,
                                  value: Number(e.target.value) || 0,
                                },
                              })
                            }
                            className="w-full text-right px-2 py-1.5 font-mono tabular-nums border border-input rounded bg-card"
                          />
                          <select
                            value={rule.platformFee.unit}
                            onChange={(e) =>
                              handleUpdateChannelRule(rule.id, {
                                platformFee: {
                                  ...rule.platformFee,
                                  unit: e.target.value as AdjustmentUnit,
                                },
                              })
                            }
                            className="px-1.5 py-1.5 font-mono border border-input rounded bg-card"
                          >
                            {ADJUSTMENT_UNITS.map((u) => (
                              <option key={u} value={u}>
                                {u}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div className="sm:col-span-2 flex items-center justify-between gap-2 pb-1">
                        <div className="text-right flex-1">
                          <div className="text-[10px] text-muted-foreground">Nihai Fiyat</div>
                          <div className="font-mono font-semibold text-foreground tabular-nums">
                            {computedCh ? `${formatTrNumber(computedCh.finalPriceTry, 0)} TL` : '—'}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveChannelRule(rule.id)}
                          disabled={draft.ledger.channelRules.length <= 1}
                          aria-label="Kanal kuralını sil"
                          data-delete="true"
                          className="p-1.5 text-destructive hover:bg-destructive/10 disabled:opacity-30 cursor-pointer rounded-md"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="space-y-2 border-t border-border pt-4">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                  <History className="w-3.5 h-3.5 text-muted-foreground" />
                  <span>Fiyat Yayın Geçmişi (Son 5 Değişiklik)</span>
                </div>
                {initialProduct?.priceHistory && initialProduct.priceHistory.length > 0 ? (
                  <div className="border border-border rounded-md divide-y divide-border bg-card text-xs">
                    {initialProduct.priceHistory.map((h) => (
                      <div key={h.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                        <div className="flex items-center gap-2">
                          {h.version ? (
                            <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                              v{h.version}
                            </span>
                          ) : null}
                          <span className="font-mono tabular-nums text-foreground">
                            B2C: {h.oldB2cTry ? `${h.oldB2cTry} TL` : '—'} → {h.newB2cTry ? `${h.newB2cTry} TL` : '—'}
                          </span>
                          <span className="text-muted-foreground">|</span>
                          <span className="font-mono tabular-nums text-foreground">
                            B2B: {h.oldB2bTry ? `${h.oldB2bTry} TL` : '—'} → {h.newB2bTry ? `${h.newB2bTry} TL` : '—'}
                          </span>
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          {new Date(h.changedAt).toLocaleString('tr-TR')} · {h.changedBy}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-muted-foreground">
                    Henüz kayıtlı fiyat yayını geçmişi yok.
                  </div>
                )}
              </div>

              <div className="flex justify-end">
                <Link
                  to="/ops/fiyat-motoru"
                  onClick={() => onOpenChange(false)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-600 hover:text-foreground transition-colors"
                >
                  Tam Fiyat Motoru ve 13 Birimli Kur Matrisini Aç
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB 4: GÖRSEL, VİDEO, 360° & MEDYA MATERYALLERİ
           =================================================================== */}
        {activeTab === 'medya' && (
          <ProductMediaPanel
            draft={draft}
            colorOptions={colorOptions.map((o) => o.value)}
            onSyncGallery={(entries) => {
              setDraft((prev) => ({
                ...prev,
                mediaItems: entries,
                galleryImages: entries.map((e) => e.url),
              }));
              setServerError(null);
            }}
            onPatchField={patchDraft}
          />
        )}

        {/* ===================================================================
            TAB: SEO
           =================================================================== */}
        {activeTab === 'seo' && (
          <ProductSeoPanel
            draft={draft}
            fieldErrors={fieldErrors}
            onPatchField={patchDraft}
          />
        )}

        {/* ===================================================================
            TAB: SATIŞ & GARANTİ
           =================================================================== */}
        {activeTab === 'satis' && (
          <ProductSalesWarrantyPanel
            draft={draft}
            fieldErrors={fieldErrors}
            onPatchField={patchDraft}
          />
        )}

        {serverError && (
          <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-800 text-xs font-medium">
            {serverError}
          </div>
        )}
      </div>
      <ConfirmDialog
        open={priceConfirmOpen}
        onOpenChange={setPriceConfirmOpen}
        title="Canlı Fiyat Güncellenecek"
        description={`Fiyatı etkileyen alanlarda değişiklik yaptınız. Eski B2C: ${formatTrNumber(baselineComputed.discountedB2cPriceTry, 0)} TL → Yeni B2C: ${formatTrNumber(liveComputed.discountedB2cPriceTry, 0)} TL | Eski B2B: ${formatTrNumber(baselineComputed.finalB2bPriceTry, 0)} TL → Yeni B2B: ${formatTrNumber(liveComputed.finalB2bPriceTry, 0)} TL${initialProduct?.variants && initialProduct.variants.length > 1 ? ` (${initialProduct.variants.length} varyant dahil)` : ''}. Kaydedildiğinde canlı fiyatlar otomatik olarak yayınlanacaktır. Onaylıyor musunuz?`}
        confirmLabel="Evet, Kaydet ve Yayınla"
        cancelLabel="Vazgeç"
        isLoading={isSubmitting}
        onConfirm={async () => {
          setPriceConfirmOpen(false);
          await handleSubmit(pendingPriceConfirmStatus, true);
        }}
      />
    </EntityModal>
  );
}

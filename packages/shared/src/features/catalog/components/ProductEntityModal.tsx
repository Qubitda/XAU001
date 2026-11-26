import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  Calculator,
  Diamond,
  Film,
  Globe,
  Image as ImageIcon,
  Layers,
  Package,
  Plus,
  Shield,
  Sparkles,
  Trash2,
  Upload,
  Warehouse,
  X,
} from 'lucide-react';
import { ProductVariantsPanel } from './ProductVariantsPanel';
import { ProductStockPanel } from './ProductStockPanel';
import {
  cloneLedger,
  createBlankProduct,
  createEmptyRates,
  withCurrentSelectOption,
} from '../../../data/productDefaults';
import { isRenderableMediaUrl, resolveProductMedia } from '../../../data/productMedia';
import { EntityModal } from '../../../components/crud/EntityModal';
import { Button, Input, Label } from '../../../components/ui';
import { cn } from '../../../lib/utils';
import { ApiClientError } from '../../../lib/api/client';
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
import {
  useCreateProductMutation,
  useLiveRatesQuery,
  useUpdateProductMutation,
} from '../hooks/useCatalogQueries';
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
  const [newImageUrl, setNewImageUrl] = useState('');
  const [newSizeInput, setNewSizeInput] = useState('');
  const [mediaNotice, setMediaNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (open) {
      const next = cloneProductDraft(mode, initialProduct);
      setBaseline(next);
      setDraft(next);
      setActiveTab(initialTab);
      setFieldErrors({});
      setServerError(null);
      setNewImageUrl('');
      setNewSizeInput('');
      setMediaNotice(null);
    }
  }, [open, mode, initialProduct, initialTab]);

  const isDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(baseline),
    [draft, baseline]
  );

  const liveComputed = useMemo(() => computeJewelryMetrics(draft, rates), [draft, rates]);

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

  const handleAddGalleryUrl = () => {
    const trimmed = newImageUrl.trim();
    if (!trimmed) return;
    if (draft.galleryImages.includes(trimmed)) {
      setMediaNotice('Bu görsel zaten galeride mevcut.');
      return;
    }
    patchDraft('galleryImages', [...draft.galleryImages, trimmed]);
    setNewImageUrl('');
    setMediaNotice(null);
  };

  const handleUploadFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    setMediaNotice(null);
    const added: string[] = [];
    for (const file of Array.from(files)) {
      if (!file.type.startsWith('image/')) continue;
      try {
        const dataUrl = await fileToCompressedDataUrl(file);
        added.push(dataUrl);
      } catch {
        setMediaNotice('Görsellerden biri okunamadı.');
      }
    }
    if (added.length > 0) {
      patchDraft('galleryImages', [...draft.galleryImages, ...added]);
      setMediaNotice(`${added.length} görsel galeriye eklendi.`);
    }
    event.target.value = '';
  };

  const handleMoveGalleryImage = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= draft.galleryImages.length) return;
    const copy = [...draft.galleryImages];
    const [item] = copy.splice(index, 1);
    copy.splice(target, 0, item);
    patchDraft('galleryImages', copy);
  };

  const handleRemoveGalleryImage = (index: number) => {
    patchDraft(
      'galleryImages',
      draft.galleryImages.filter((_, idx) => idx !== index)
    );
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

  const handleSubmit = async () => {
    setServerError(null);
    const parsed = productFormSchema.safeParse({
      parentSku: draft.parentSku,
      title: draft.title,
      category: draft.category,
      subCategory: draft.subCategory,
      collection: draft.collection,
      purityCode: draft.purityCode,
      metalColor: draft.metalColor,
      stoneType: draft.stoneType,
      grossWeightGram: draft.grossWeightGram,
      centerStoneCarat: draft.centerStoneCarat,
      sideStoneCarat: draft.sideStoneCarat,
      fireRatePct: draft.fireRatePct,
      stockStatus: draft.stockStatus,
      stockQty: draft.stockQty,
      ownershipType: draft.ownershipType,
      visualType: draft.visualType,
      description: draft.description,
    });

    if (!parsed.success) {
      const nextErrors: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const key = String(issue.path[0] ?? 'form');
        if (!nextErrors[key]) nextErrors[key] = issue.message;
      }
      setFieldErrors(nextErrors);
      const stoneKeys = new Set(['grossWeightGram', 'centerStoneCarat', 'sideStoneCarat', 'fireRatePct', 'stoneType']);
      const firstKey = Object.keys(nextErrors)[0];
      if (firstKey && stoneKeys.has(firstKey)) {
        setActiveTab('tas-montur');
      } else {
        setActiveTab('genel');
      }
      return;
    }

    const normalizedSku = draft.parentSku.trim().toUpperCase();
    const resolvedSlug =
      slugifyTurkish(draft.seoSlug || '') ||
      slugifyTurkish(`${normalizedSku}-${draft.title}`) ||
      `${normalizedSku.toLowerCase()}-mucevher`;
    const resolvedMetaTitle = draft.metaTitle.trim() || `${draft.title.trim()} | Tara Gold`;

    const payload: ProductState = {
      ...draft,
      ...buildDetailPayload(draft, finenessMap),
      parentSku: normalizedSku,
      title: draft.title.trim(),
      description: draft.description.trim(),
      seoSlug: resolvedSlug,
      metaTitle: resolvedMetaTitle,
      hasCertificate: Boolean(draft.certificateAgency.trim()),
    };

    try {
      if (mode === 'create') {
        const created = await createMutation.mutateAsync(payload);
        onSaved?.(created);
        onOpenChange(false);
      } else if (initialProduct) {
        const updated = await updateMutation.mutateAsync({
          parentSku: initialProduct.parentSku,
          patch: payload,
        });
        onSaved?.(updated);
        onOpenChange(false);
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setServerError(err.message);
      } else {
        setServerError('Kayıt sırasında beklenmeyen bir hata oluştu.');
      }
    }
  };

  const fallbackMedia = resolveProductMedia(draft.parentSku, draft.metalColor);
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
      submitLabel={mode === 'create' ? 'Ürünü Oluştur ve Yayınla' : 'Tüm Değişiklikleri Kaydet'}
      onSubmit={handleSubmit}
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
          className="flex flex-wrap gap-1 p-1 bg-muted/60 border border-border rounded-lg"
        >
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
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
                  'h-auto px-2.5 py-2 rounded-md text-xs font-medium whitespace-nowrap gap-1.5',
                  active && 'bg-card text-foreground shadow-xs border border-border'
                )}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                <span>{tab.label}</span>
                {countHint !== null && countHint > 0 && (
                  <span className="font-mono text-[11px] text-muted-foreground">({countHint})</span>
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
                    onChange={(e) => patchDraft('metalColor', e.target.value as MetalColor)}
                    className={FIELD_SELECT_CLASS}
                    disabled={!draft.metalName}
                  >
                    <option value="">
                      {draft.metalName ? 'Seçiniz' : 'Önce metal seçin'}
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
                  {!metalColorOpts.isLoading && COLORS.length === 0 ? (
                    <span className="text-xs text-muted-foreground">
                      Tanım tablosunda aktif metal rengi yok.{' '}
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
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
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
                  <Label className="font-medium block">Ürün Satış Kanalları</Label>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {channelOptions.map((ch) => {
                      const selected = (draft.salesChannels ?? []).includes(ch.code);
                      return (
                        <button
                          key={ch.code}
                          type="button"
                          onClick={() => {
                            const curr = draft.salesChannels ?? [];
                            patchDraft(
                              'salesChannels',
                              selected ? curr.filter((c) => c !== ch.code) : [...curr, ch.code]
                            );
                          }}
                          className={`px-2.5 py-1.5 rounded-md border text-[11px] font-medium cursor-pointer shrink-0 ${
                            selected
                              ? 'bg-foreground text-primary-foreground border-foreground'
                              : 'bg-card text-muted-foreground border-input'
                          }`}
                        >
                          {ch.label}
                        </button>
                      );
                    })}
                  </div>
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
          />
        )}

        {activeTab === 'stok' && (
          <ProductStockPanel
            parentSku={draft.parentSku}
            mode={mode}
            catalogStockQty={draft.stockQty}
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
          <div className="space-y-5">
            {/* Gallery Photos Section */}
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">
                    Ürün Fotoğrafları ve Galeri Sıralaması
                  </h3>
                  <p className="text-[11px] text-muted-foreground">
                    Bilgisayardan görsel yükleyin veya URL ekleyin. İlk sıradaki görsel vitrin ve katalog kapağı olarak kullanılır.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(e) => void handleUploadFiles(e)}
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-foreground text-white hover:bg-slate-800 font-medium cursor-pointer"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    Bilgisayardan Görsel Yükle
                  </button>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <Input
                  type="url"
                  value={newImageUrl}
                  onChange={(e) => setNewImageUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddGalleryUrl();
                    }
                  }}
                  placeholder="https://cdn.taragold.com/urunler/SE009-main.jpg"
                  className="flex-1 px-3 py-2 border border-input rounded-md bg-card text-foreground font-mono text-xs"
                />
                <button
                  type="button"
                  onClick={handleAddGalleryUrl}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 font-medium whitespace-nowrap cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  URL Ekle
                </button>
              </div>

              {mediaNotice && (
                <p className="text-[11px] font-medium text-emerald-700">{mediaNotice}</p>
              )}

              {draft.galleryImages.length === 0 ? (
                <div className="p-5 border border-dashed border-input rounded-lg bg-muted/50/70 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <img
                      src={fallbackMedia.mainUrl}
                      alt={draft.title || 'Varsayılan şablon görseli'}
                      referrerPolicy="no-referrer"
                      className="w-14 h-14 rounded-md object-cover border border-border bg-card shrink-0"
                    />
                    <div>
                      <div className="font-medium text-foreground">
                        Özel galeri görseli henüz eklenmemiş
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Görsel eklediğinizde varsayılan stüdyo şablonunun yerine sizin fotoğraflarınız gösterilir.
                      </p>
                    </div>
                  </div>
                  <div className="w-full sm:w-64 space-y-1">
                    <Label className="text-[11px] font-medium text-muted-foreground block">
                      Yedek Stüdyo Şablonu
                    </Label>
                    <select
                      value={draft.visualType}
                      onChange={(e) =>
                        patchDraft('visualType', e.target.value as JewelryVisualType)
                      }
                      className="w-full px-2.5 py-1.5 border border-input rounded-md bg-card text-xs"
                    >
                      {VISUAL_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {draft.galleryImages.map((imgUrl, idx) => {
                    const renderable = isRenderableMediaUrl(imgUrl);
                    return (
                      <div
                        key={`${idx}-${imgUrl.slice(0, 32)}`}
                        className="border border-border rounded-lg bg-card overflow-hidden flex flex-col"
                      >
                        <div className="aspect-[4/3] bg-muted relative overflow-hidden flex items-center justify-center">
                          {renderable ? (
                            <img
                              src={imgUrl}
                              alt={`Galeri görseli ${idx + 1}`}
                              referrerPolicy="no-referrer"
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="text-center p-4 text-muted-foreground">
                              <ImageIcon className="w-6 h-6 mx-auto mb-1.5 text-muted-foreground" />
                              <div className="font-mono text-[11px] break-all">{imgUrl}</div>
                            </div>
                          )}
                        </div>
                        <div className="p-2.5 border-t border-slate-100 flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="text-[11px] font-semibold text-foreground">
                              {idx === 0 ? 'Ana Vitrin Görseli' : `Görsel #${idx + 1}`}
                            </div>
                            <div className="font-mono text-[10px] text-muted-foreground truncate">
                              {imgUrl.startsWith('data:') ? 'Yerel Yüklenen Dosya' : imgUrl}
                            </div>
                          </div>
                          <div className="flex items-center gap-0.5 shrink-0">
                            <button
                              type="button"
                              disabled={idx === 0}
                              onClick={() => handleMoveGalleryImage(idx, -1)}
                              title="Yukarı taşı"
                              className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-30 cursor-pointer"
                            >
                              <ArrowUp className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              disabled={idx === draft.galleryImages.length - 1}
                              onClick={() => handleMoveGalleryImage(idx, 1)}
                              title="Aşağı taşı"
                              className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-30 cursor-pointer"
                            >
                              <ArrowDown className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleRemoveGalleryImage(idx)}
                              title="Görseli çıkar"
                              data-delete="true"
                              className="p-1 text-destructive hover:bg-destructive/10 cursor-pointer rounded-md"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Video, 360 Spin, Clean Catalog PNG & Certificate PDF */}
            <div className="pt-4 border-t border-border space-y-3">
              <div className="flex items-center gap-2">
                <Film className="w-4 h-4 text-muted-foreground" />
                <h3 className="text-sm font-semibold text-foreground">
                  Video, 360° Görünüm ve Diğer Görsel Materyaller
                </h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="font-medium block">
                    Reels / Ürün Videosu URL (9:16 veya MP4)
                  </Label>
                  <div className="flex items-center gap-1.5">
                    <Input
                      type="text"
                      value={draft.reelsVideoUrl}
                      onChange={(e) => patchDraft('reelsVideoUrl', e.target.value)}
                      placeholder="https://cdn.taragold.com/videos/SE009_reels.mp4"
                      className="flex-1 px-3 py-2 font-mono border border-input rounded-md bg-card text-foreground"
                    />
                    {draft.reelsVideoUrl && (
                      <button
                        type="button"
                        onClick={() => patchDraft('reelsVideoUrl', '')}
                        title="Videoyu kaldır"
                        data-delete="true"
                        className="p-2 border border-input rounded-md text-destructive hover:bg-destructive/10 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="font-medium block">
                    360° Dönen Tabla Video / URL
                  </Label>
                  <div className="flex items-center gap-1.5">
                    <Input
                      type="text"
                      value={draft.spin360Url}
                      onChange={(e) => patchDraft('spin360Url', e.target.value)}
                      placeholder="https://cdn.taragold.com/360/SE009_360.mp4"
                      className="flex-1 px-3 py-2 font-mono border border-input rounded-md bg-card text-foreground"
                    />
                    {draft.spin360Url && (
                      <button
                        type="button"
                        onClick={() => patchDraft('spin360Url', '')}
                        title="360° materyali kaldır"
                        data-delete="true"
                        className="p-2 border border-input rounded-md text-destructive hover:bg-destructive/10 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="font-medium block">
                    Filigransız Katalog Görseli (PNG / Beyaz Fon)
                  </Label>
                  <div className="flex items-center gap-1.5">
                    <Input
                      type="text"
                      value={draft.catalogCleanImageUrl}
                      onChange={(e) => patchDraft('catalogCleanImageUrl', e.target.value)}
                      placeholder="https://cdn.taragold.com/clean/SE009_clean.png"
                      className="flex-1 px-3 py-2 font-mono border border-input rounded-md bg-card text-foreground"
                    />
                    {draft.catalogCleanImageUrl && (
                      <button
                        type="button"
                        onClick={() => patchDraft('catalogCleanImageUrl', '')}
                        title="Temiz görseli kaldır"
                        data-delete="true"
                        className="p-2 border border-input rounded-md text-destructive hover:bg-destructive/10 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="font-medium block">
                    Sertifika Dosyası (PDF URL)
                  </Label>
                  <div className="flex items-center gap-1.5">
                    <Input
                      type="text"
                      value={draft.certificateFileUrl}
                      onChange={(e) => patchDraft('certificateFileUrl', e.target.value)}
                      placeholder="https://cdn.taragold.com/certs/GIA_2141234567.pdf"
                      className="flex-1 px-3 py-2 font-mono border border-input rounded-md bg-card text-foreground"
                    />
                    {draft.certificateFileUrl && (
                      <button
                        type="button"
                        onClick={() => patchDraft('certificateFileUrl', '')}
                        title="Sertifika dosyasını kaldır"
                        data-delete="true"
                        className="p-2 border border-input rounded-md text-destructive hover:bg-destructive/10 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* B2B Media Sharing & Social Copy */}
            <div className="pt-4 border-t border-border grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">B2B Bayi Medya Paylaşım İzni</Label>
                <Input
                  type="text"
                  value={draft.b2bSharePermission}
                  onChange={(e) => patchDraft('b2bSharePermission', e.target.value)}
                  
                />
                <Label className="inline-flex items-center gap-2 pt-1.5 font-medium cursor-pointer">
                  <input
                    type="checkbox"
                    checked={draft.dynamicDealerWatermark}
                    onChange={(e) => patchDraft('dynamicDealerWatermark', e.target.checked)}
                    className="rounded border-input"
                  />
                  <span>Bayi paylaşımında dinamik logo / filigran uygula</span>
                </Label>
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">
                  Sosyal Medya / WhatsApp Paylaşım Metni
                </Label>
                <textarea
                  rows={3}
                  value={draft.socialShareCaption}
                  onChange={(e) => patchDraft('socialShareCaption', e.target.value)}
                  placeholder="Bayilerin Instagram / WhatsApp paylaşımında kullanacağı hazır açıklama..."
                  className={FIELD_TEXTAREA_CLASS}
                />
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB: SEO
           =================================================================== */}
        {activeTab === 'seo' && (
          <div className="space-y-5">
            <div className="p-4 border border-border rounded-lg bg-muted/50 space-y-1">
              <div className="text-[11px] font-medium text-muted-foreground">
                Arama Motoru (Google) Canlı Önizleme
              </div>
              <div className="text-xs text-emerald-800 font-mono truncate">
                https://taragold.com.tr/urun/{draft.seoSlug || slugifyTurkish(draft.title || draft.parentSku)}
              </div>
              <div className="text-base font-medium text-blue-800 leading-snug">
                {draft.metaTitle || draft.title || 'Ürün Meta Başlığı'}
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                {draft.description ||
                  'Ürün açıklaması burada arama sonucu özeti (meta description) olarak görüntülenir.'}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="font-medium">SEO URL Slug</Label>
                  <button
                    type="button"
                    onClick={() =>
                      patchDraft(
                        'seoSlug',
                        slugifyTurkish(`${draft.title || draft.parentSku}-${draft.purityCode}-${draft.metalColor}`)
                      )
                    }
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-600 hover:text-foreground cursor-pointer"
                  >
                    <Sparkles className="w-3 h-3" />
                    Başlıktan Üret
                  </button>
                </div>
                <Input
                  type="text"
                  value={draft.seoSlug}
                  onChange={(e) => patchDraft('seoSlug', e.target.value)}
                  placeholder="0-60-karat-pirlanta-tektas-yuzuk-14k-beyaz"
                  className={cn(FIELD_SELECT_CLASS, 'w-full font-mono')}
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="font-medium">Meta Başlık (Title Tag)</Label>
                  <span
                    className={`font-mono text-[11px] ${
                      draft.metaTitle.length > 65 ? 'text-warning' : 'text-muted-foreground'
                    }`}
                  >
                    {draft.metaTitle.length} / 60 karakter
                  </span>
                </div>
                <Input
                  type="text"
                  value={draft.metaTitle}
                  onChange={(e) => patchDraft('metaTitle', e.target.value)}
                  placeholder="0.60 Karat GIA Sertifikalı Pırlanta Tektaş Yüzük | Tara Gold"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">
                  Pazaryeri / Google Shopping Kategorisi
                </Label>
                <Input
                  type="text"
                  value={draft.marketplaceCategory}
                  onChange={(e) => patchDraft('marketplaceCategory', e.target.value)}
                  placeholder="Takı & Mücevher > Pırlanta > Pırlanta Yüzük"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Ölçü Rehberi URL</Label>
                <Input
                  type="text"
                  value={draft.sizeGuideUrl}
                  onChange={(e) => patchDraft('sizeGuideUrl', e.target.value)}
                  placeholder="https://taragold.com.tr/olcu-rehberi"
                  className={cn(FIELD_SELECT_CLASS, 'w-full font-mono')}
                />
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================
            TAB: SATIŞ & GARANTİ
           =================================================================== */}
        {activeTab === 'satis' && (
          <div className="space-y-5">
            <p className="text-xs text-muted-foreground">
              Satış sonrası politikalar. İleride kategori/marka varsayılanlarından override edilebilir;
              şimdilik ürün kartı seviyesinde tutulur.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label className="font-medium block">Garanti Süresi (Ay)</Label>
                <Input
                  type="number"
                  min={0}
                  max={120}
                  value={draft.warrantyMonths}
                  onChange={(e) =>
                    patchDraft('warrantyMonths', Math.max(0, Math.round(Number(e.target.value) || 0)))
                  }
                  className="text-right font-mono tabular-nums"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Ömür Boyu Bakım</Label>
                <Input
                  type="text"
                  value={draft.lifetimeMaintenance}
                  onChange={(e) => patchDraft('lifetimeMaintenance', e.target.value)}
                  placeholder="Evet (Ücretsiz)"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="font-medium block">Sigortalı Kargo Bilgisi</Label>
                <Input
                  type="text"
                  value={draft.insuredShippingInfo}
                  onChange={(e) => patchDraft('insuredShippingInfo', e.target.value)}
                  placeholder="Tam sigortalı özel kurye"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="font-medium block">İade &amp; Değişim Politikası</Label>
              <textarea
                rows={3}
                value={draft.returnPolicyText}
                onChange={(e) => patchDraft('returnPolicyText', e.target.value)}
                placeholder="14 gün içinde koşulsuz iade; kişiye özel yazı/ölçü yapılan ürünlerde cayma istisnası uygulanır."
                className={FIELD_TEXTAREA_CLASS}
              />
            </div>

            <div className="space-y-1.5">
              <Label className="font-medium block">Tedarikçi (katalog etiketi)</Label>
              <Input
                type="text"
                value={draft.supplierName}
                onChange={(e) => patchDraft('supplierName', e.target.value)}
                placeholder="Tara Gold Atölye"
              />
              <p className="text-[10px] text-muted-foreground">
                Fiziksel depo/tedarikçi stok satırında yaşar; bu alan ürün kartı etiketidir.
              </p>
            </div>
          </div>
        )}
      </div>
    </EntityModal>
  );
}

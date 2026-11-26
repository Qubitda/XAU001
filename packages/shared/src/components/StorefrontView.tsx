import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  ClipboardList,
  Heart,
  RefreshCw,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  X,
} from 'lucide-react';
import {
  AudienceRole,
  ComputedJewelryMetrics,
  LiveRates,
  MetalColor,
  ProductState,
} from '../types/jewelry';
import {
  computeJewelryMetrics,
  formatCurrencyValue,
  formatTrNumber,
} from '../utils/pricingEngine';
import { resolveProductMedia } from '../data/productMedia';
import { JewelryIllustration } from './JewelryIllustration';
import { LuxuryMerchRibbon } from './LuxuryMerchRibbon';
import {
  StorefrontEmptyState,
  StorefrontPageHeader,
  StorefrontProductCard,
  TARA_PRIMARY_BTN_CLASS,
  TARA_SEARCH_INPUT_CLASS,
  TARA_SELECT_CLASS,
} from '../features/storefront/components/StorefrontUI';
import { BrandTrustStrip } from '../features/storefront/components/BrandTrustStrip';
import {
  matchesDefinitionValue,
  resolveDefinitionLabel,
  usePublicDefinitionOptions,
} from '../features/definitions/hooks/useDefinitionsQuery';
import {
  LEGACY_STOREFRONT_CATEGORY_CODES,
  pickStorefrontCategories,
} from '../features/definitions/storefrontCategories';

import heroEditorialImg from '../assets/images/hero-tara-gold.jpg';

const HERO_IMAGE_URL = heroEditorialImg;

const FALLBACK_COLORS = [
  { value: 'BEYAZ', label: 'Beyaz' },
  { value: 'SARI', label: 'Sarı' },
  { value: 'ROSE', label: 'Rose' },
] as const;

const STOREFRONT_COLOR_FILTER_CODES = ['BEYAZ', 'SARI', 'ROSE'] as const;

interface StorefrontViewProps {
  products: ProductState[];
  selectedParentSku: string;
  rates: LiveRates;
  role: AudienceRole;
  favoriteSkus?: string[];
  initialCategory?: string;
  initialMerchFilter?: MerchFilter;
  initialQuery?: string;
  onRoleChange: (role: AudienceRole) => void;
  onSelectProduct: (parentSku: string, previewColor?: MetalColor) => void;
  onToggleFavorite?: (parentSku: string) => void;
  onOpenB2bOrder?: () => void;
  onQuickAddB2c?: (product: ProductState, metrics: ComputedJewelryMetrics) => void;
  onQuickAddB2b?: (product: ProductState, metrics: ComputedJewelryMetrics) => void;
}

type SortOption = 'featured' | 'price_asc' | 'price_desc' | 'carat_desc';
type MerchFilter = 'all' | 'discounted' | 'new_collection';

export function StorefrontView({
  products,
  rates,
  role,
  favoriteSkus = [],
  initialCategory = 'Tümü',
  initialMerchFilter = 'all',
  initialQuery = '',
  onSelectProduct,
  onToggleFavorite,
  onOpenB2bOrder,
  onQuickAddB2c,
  onQuickAddB2b,
}: StorefrontViewProps) {
  const categoryDefs = usePublicDefinitionOptions('kategori');
  const colorDefs = usePublicDefinitionOptions('metal_rengi');

  const categoryOptions = useMemo(() => {
    if (categoryDefs.options.length > 0) return categoryDefs.options;
    return LEGACY_STOREFRONT_CATEGORY_CODES.map((code) => ({
      value: code,
      label:
        code === 'YUZUK'
          ? 'Yüzük'
          : code === 'KOLYE'
            ? 'Kolye'
            : code === 'KUPE'
              ? 'Küpe'
              : 'Bileklik',
      code,
      id: code,
      meta: { showOnStorefront: true },
      parentCodes: [] as string[],
      parentLabels: [] as string[],
    }));
  }, [categoryDefs.options]);

  const colorOptions = useMemo(() => {
    if (colorDefs.options.length > 0) return colorDefs.options;
    return FALLBACK_COLORS.map((c) => ({
      value: c.value,
      label: c.label,
      code: c.value,
      id: c.value,
      meta: {},
      parentCodes: [] as string[],
      parentLabels: [] as string[],
    }));
  }, [colorDefs.options]);

  /** Dropdown: core tones only — full metal_rengi stays in colorOptions for matching. */
  const colorFilterOptions = useMemo(() => {
    const primary = STOREFRONT_COLOR_FILTER_CODES.map((code) =>
      colorOptions.find((o) => o.code === code)
    ).filter((o): o is NonNullable<typeof o> => Boolean(o));
    return primary.length > 0 ? primary : colorOptions.slice(0, 3);
  }, [colorOptions]);

  /** Tab list from meta.showOnStorefront (same SSOT as CategoryStrip / footer). */
  const navCategoryOptions = useMemo(
    () => pickStorefrontCategories(categoryOptions),
    [categoryOptions]
  );

  const [category, setCategory] = useState<string>(initialCategory);
  const [colorFilter, setColorFilter] = useState<'Tümü' | MetalColor>('Tümü');
  const [merchFilter, setMerchFilter] = useState<MerchFilter>(initialMerchFilter);
  const [searchQuery, setSearchQuery] = useState<string>(initialQuery);
  const [sortBy, setSortBy] = useState<SortOption>('featured');
  const [cardPreviewColors, setCardPreviewColors] = useState<Record<string, MetalColor>>({});
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});
  const [recentAddedSku, setRecentAddedSku] = useState<string | null>(null);
  const categoryNormalized = useRef(false);

  // Normalize URL/legacy label (?category=Yüzük) → definition code (YUZUK).
  useEffect(() => {
    if (categoryNormalized.current || category === 'Tümü') return;
    if (categoryDefs.options.length === 0 && colorDefs.isLoading) return;
    const match = categoryOptions.find(
      (o) => o.value === category || o.code === category || o.label === category
    );
    categoryNormalized.current = true;
    if (match && category !== match.value) setCategory(match.value);
  }, [category, categoryOptions, categoryDefs.options.length, colorDefs.isLoading]);

  const categoryLabel =
    category === 'Tümü' ? 'Tümü' : resolveDefinitionLabel(category, categoryOptions) || category;

  const flashAdded = (key: string) => {
    setRecentAddedSku(key);
    window.setTimeout(() => {
      setRecentAddedSku((cur) => (cur === key ? null : cur));
    }, 1500);
  };

  const computedCatalog = useMemo(() => {
    return products.map((prod) => {
      const displayColor = cardPreviewColors[prod.parentSku] ?? prod.metalColor;
      const effectiveProduct: ProductState =
        displayColor === prod.metalColor ? prod : { ...prod, metalColor: displayColor };
      const metrics = computeJewelryMetrics(effectiveProduct, rates);
      const media = resolveProductMedia(
        effectiveProduct.parentSku,
        displayColor,
        effectiveProduct.galleryImages
      );
      return {
        product: effectiveProduct,
        metrics,
        media,
      };
    });
  }, [products, rates, cardPreviewColors]);

  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLocaleLowerCase('tr-TR');
    const filtered = computedCatalog.filter(({ product, metrics }) => {
      if (
        category !== 'Tümü' &&
        !matchesDefinitionValue(product.category, category, categoryOptions)
      ) {
        return false;
      }
      if (colorFilter !== 'Tümü') {
        const colorHit =
          matchesDefinitionValue(product.metalColor, colorFilter, colorOptions) ||
          product.availableColors.some((c) =>
            matchesDefinitionValue(c, colorFilter, colorOptions)
          );
        if (!colorHit) return false;
      }
      if (merchFilter === 'discounted') {
        const hasRoleDiscount =
          role === 'b2b'
            ? metrics.ledger.hasB2bChannel && metrics.ledger.b2bDiscountLc > 0
            : metrics.ledger.hasB2cChannel && metrics.discountAmountTry > 0;
        if (!hasRoleDiscount) return false;
      }
      if (merchFilter === 'new_collection' && product.collection !== 'Yeni Koleksiyon') {
        return false;
      }
      if (!q) return true;
      return (
        product.title.toLocaleLowerCase('tr-TR').includes(q) ||
        product.parentSku.toLowerCase().includes(q) ||
        metrics.sku.toLowerCase().includes(q) ||
        product.subCategory.toLocaleLowerCase('tr-TR').includes(q) ||
        product.stoneType.toLocaleLowerCase('tr-TR').includes(q) ||
        product.certificateAgency.toLowerCase().includes(q)
      );
    });

    if (sortBy === 'price_asc') {
      return [...filtered].sort((a, b) =>
        role === 'b2b'
          ? a.metrics.finalB2bPriceTry - b.metrics.finalB2bPriceTry
          : a.metrics.discountedB2cPriceTry - b.metrics.discountedB2cPriceTry
      );
    }
    if (sortBy === 'price_desc') {
      return [...filtered].sort((a, b) =>
        role === 'b2b'
          ? b.metrics.finalB2bPriceTry - a.metrics.finalB2bPriceTry
          : b.metrics.discountedB2cPriceTry - a.metrics.discountedB2cPriceTry
      );
    }
    if (sortBy === 'carat_desc') {
      return [...filtered].sort((a, b) => b.metrics.totalStoneCarat - a.metrics.totalStoneCarat);
    }
    return filtered;
  }, [
    computedCatalog,
    category,
    categoryOptions,
    colorFilter,
    colorOptions,
    merchFilter,
    role,
    searchQuery,
    sortBy,
  ]);

  const featuredSignature = computedCatalog[0];
  const hasActiveFilters =
    category !== 'Tümü' ||
    colorFilter !== 'Tümü' ||
    merchFilter !== 'all' ||
    searchQuery.trim().length > 0;

  const resetAllFilters = () => {
    setCategory('Tümü');
    setColorFilter('Tümü');
    setMerchFilter('all');
    setSearchQuery('');
    setSortBy('featured');
  };

  const handleSwatchClick = (
    e: React.MouseEvent,
    parentSku: string,
    color: MetalColor
  ) => {
    e.stopPropagation();
    setCardPreviewColors((prev) => ({ ...prev, [parentSku]: color }));
  };

  const scrollToCollection = () => {
    document.getElementById('koleksiyon-grid')?.scrollIntoView({ behavior: 'smooth' });
  };

  const navCategories = useMemo(() => {
    const base = [{ value: 'Tümü', label: 'Tümü' }, ...navCategoryOptions];
    // Deep-link to a non-primary category (e.g. ?category=ALYANS) — keep it visible while active.
    if (category !== 'Tümü' && !base.some((c) => c.value === category)) {
      const extra = categoryOptions.find(
        (o) => o.value === category || o.code === category || o.label === category
      );
      if (extra) return [...base, extra];
    }
    return base;
  }, [navCategoryOptions, category, categoryOptions]);

  // =========================================================================
  // B2C STOREFRONT — TARA DIAMOND LUXURY COLLECTION / SEARCH / FILTER VIEW
  // =========================================================================
  if (role === 'b2c') {
    const pageEyebrow = 'TARA DIAMOND · ATELYE';

    const pageTitle =
      searchQuery.trim().length > 0
        ? `“${searchQuery.trim()}” İçin Arama Sonuçları`
        : merchFilter === 'discounted'
          ? 'Kampanyalı Tasarımlar'
          : merchFilter === 'new_collection'
            ? 'Yeni Gelenler'
            : category === 'Tümü'
              ? 'Tüm Koleksiyon'
              : `${categoryLabel} Koleksiyonu`;

    const pageSubtitle =
      'GIA ve HRD sertifikalı pırlantalar, 14 ve 18 ayar altın işçiliğiyle atölyemizde hazırlanır. Altın rengini kart üzerinden anında önizleyebilirsiniz.';

    return (
      <div className="space-y-8 sm:space-y-10 text-foreground">
        {/* Editorial Collection Page Header & Breadcrumb */}
        <StorefrontPageHeader
          eyebrow={pageEyebrow}
          title={pageTitle}
          subtitle={pageSubtitle}
          breadcrumb={[
            { label: 'Ana Sayfa', to: '/' },
            ...(category !== 'Tümü'
              ? [
                  { label: 'Koleksiyon', onClick: () => setCategory('Tümü') },
                  { label: categoryLabel },
                ]
              : [{ label: 'Koleksiyon' }]),
          ]}
          actions={
            <p className="font-mono text-xs text-muted-foreground tabular-nums whitespace-nowrap">
              {filteredItems.length} tasarım
            </p>
          }
        />

        {/* Category Underline Tabs + Search / Filter / Sort Bar */}
        <section id="koleksiyon-grid" className="space-y-5 scroll-mt-24">
          <div className="space-y-3 border-b border-border pb-4">
            {/* Horizontal Category Navigation — own row so filters never crush tabs */}
            <div
              role="tablist"
              aria-label="Mücevher kategorileri"
              className="flex items-center gap-5 sm:gap-7 overflow-x-auto no-scrollbar"
            >
              {navCategories.map((cat) => {
                const active = category === cat.value;
                const count =
                  cat.value === 'Tümü'
                    ? products.length
                    : products.filter((p) =>
                        matchesDefinitionValue(p.category, cat.value, categoryOptions)
                      ).length;
                return (
                  <button
                    key={cat.value}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setCategory(cat.value)}
                    className={`relative pb-2 text-[13px] font-medium whitespace-nowrap shrink-0 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm ${
                      active
                        ? 'text-foreground after:absolute after:inset-x-0 after:bottom-0 after:h-[1.5px] after:bg-primary'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <span>{cat.label}</span>
                    {count > 0 && (
                      <span className="ml-1.5 font-mono text-[11px] text-muted-foreground tabular-nums">
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Search & Refinement Controls */}
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="relative w-full sm:w-auto sm:flex-1 sm:min-w-[200px] sm:max-w-[280px]">
                <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Tasarım, taş veya sertifika ara..."
                  aria-label="Koleksiyonda ara"
                  className={TARA_SEARCH_INPUT_CLASS}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    aria-label="Aramayı temizle"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              <select
                value={colorFilter}
                onChange={(e) => setColorFilter(e.target.value as 'Tümü' | MetalColor)}
                aria-label="Altın rengi filtresi"
                className={TARA_SELECT_CLASS}
              >
                <option value="Tümü">Tüm Altın Renkleri</option>
                {colorFilterOptions.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label === 'Rose (Kırmızı)' ? 'Rose' : c.label} Altın
                  </option>
                ))}
              </select>

              <select
                value={merchFilter}
                onChange={(e) => setMerchFilter(e.target.value as MerchFilter)}
                aria-label="Seçki filtresi"
                className={TARA_SELECT_CLASS}
              >
                <option value="all">Tüm Parçalar</option>
                <option value="new_collection">Yeni Gelenler</option>
                <option value="discounted">Kampanyalı Seçki</option>
              </select>

              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                aria-label="Sıralama"
                className={TARA_SELECT_CLASS}
              >
                <option value="featured">Sıralama: Önerilen</option>
                <option value="price_asc">Fiyat: Artan</option>
                <option value="price_desc">Fiyat: Azalan</option>
                <option value="carat_desc">Karat: Yüksekten Düşüğe</option>
              </select>

              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={resetAllFilters}
                  className="h-10 px-3 rounded-[4px] text-xs font-medium text-foreground hover:bg-primary transition-colors cursor-pointer whitespace-nowrap"
                >
                  Temizle
                </button>
              )}
            </div>
          </div>

          {/* Product Grid or Empty State */}
          {filteredItems.length === 0 ? (
            <StorefrontEmptyState
              icon={<Sparkles className="w-8 h-8" />}
              title="Seçili filtrelere uygun tasarım bulunamadı"
              description="Farklı bir kategori, altın rengi veya arama terimi deneyebilir ya da tüm koleksiyonu yeniden görüntüleyebilirsiniz."
              action={
                <button
                  type="button"
                  onClick={resetAllFilters}
                  className={TARA_PRIMARY_BTN_CLASS}
                >
                  Filtreleri Temizle
                </button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {filteredItems.map(({ product, metrics, media }) => {
                const activeColor = cardPreviewColors[product.parentSku] ?? product.metalColor;
                return (
                  <StorefrontProductCard
                    key={product.parentSku}
                    product={product}
                    metrics={metrics}
                    media={media}
                    activeColor={activeColor}
                    isFavorite={favoriteSkus.includes(product.parentSku)}
                    isAdded={recentAddedSku === `b2c:${product.parentSku}`}
                    showColorSwatches={true}
                    onOpen={() => onSelectProduct(product.parentSku, activeColor)}
                    onSelectColor={(color) =>
                      setCardPreviewColors((prev) => ({ ...prev, [product.parentSku]: color }))
                    }
                    onToggleFavorite={
                      onToggleFavorite ? () => onToggleFavorite(product.parentSku) : undefined
                    }
                    onQuickAdd={
                      onQuickAddB2c
                        ? () => {
                            onQuickAddB2c(product, metrics);
                            flashAdded(`b2c:${product.parentSku}`);
                          }
                        : undefined
                    }
                  />
                );
              })}
            </div>
          )}
        </section>

        <div className="pt-8">
          <BrandTrustStrip />
        </div>
      </div>
    );
  }

  // =========================================================================
  // B2B / ERP OPERATIONAL CATALOG VIEW (PRESERVED INTACT)
  // =========================================================================
  return (
    <div className={role === 'b2b' ? 'space-y-6' : 'space-y-12'}>
      {role === 'b2b' ? (
        <section className="rounded-lg border border-border bg-card p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <p className="text-caption text-xs tabular-nums">
              Has Altın: {formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr · USD:{' '}
              {formatTrNumber(rates.liveUsdSell, 2)} TL
            </p>
            <h2 className="text-page-title text-lg sm:text-xl text-foreground">
              Fire dahil has + işçilik bazlı toptan fiyatlar
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={scrollToCollection}
              className="px-4 py-2 bg-primary text-primary-foreground text-xs font-medium rounded-md hover:opacity-90 transition-opacity inline-flex items-center gap-2 cursor-pointer"
            >
              Kataloğa Git
              <ArrowDown className="w-3.5 h-3.5" />
            </button>
            {onOpenB2bOrder ? (
              <button
                type="button"
                onClick={onOpenB2bOrder}
                className="px-4 py-2 bg-background text-foreground border border-border text-xs font-medium rounded-md hover:bg-muted transition-colors inline-flex items-center gap-2 cursor-pointer"
              >
                <ClipboardList className="w-3.5 h-3.5 text-muted-foreground" />
                Sipariş Fişi
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      {/* Section 1: Editorial Luxury Jewelry Storefront Hero (2-column balanced split) */}
      {role !== 'b2b' ? (
      <section className="grid grid-cols-1 lg:grid-cols-12 bg-white border border-border rounded-xl overflow-hidden items-stretch">
        <div className="lg:col-span-6 p-8 md:p-12 flex flex-col justify-between gap-8">
          <div className="space-y-4">
            <div className="text-xs text-muted-foreground">
              {role === 'erp'
                ? `Mağaza & Katalog Vitrini · ${products.length} Aktif Tasarım · Has Altın: ${formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr`
                : `Vitrin · ${products.length} Aktif Tasarım · Has Altın: ${formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr`}
            </div>

            <h1 className="text-page-title text-3xl sm:text-4xl md:text-5xl tracking-tight leading-[1.08] text-balance">
              Zamansız Işıltı, Sertifikalı Mücevher Ustalığı
            </h1>

            <p className="text-sm text-muted-foreground leading-relaxed max-w-lg">
              Seçkin kesim pırlantalar, 14 ve 18 ayar altın işçiliği ile İstanbul atölyemizde hazırlanır. Sigortalı değerli kurye ve orijinal sertifika ile teslim edilir.
            </p>
          </div>

          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={scrollToCollection}
                className="px-5 py-2.5 bg-primary text-primary-foreground text-xs font-medium rounded-md hover:bg-primary/90 transition-colors inline-flex items-center gap-2 cursor-pointer whitespace-nowrap"
              >
                Koleksiyonu Keşfet
                <ArrowDown className="w-3.5 h-3.5" />
              </button>

              {featuredSignature && (
                <button
                  type="button"
                  onClick={() => onSelectProduct(featuredSignature.product.parentSku)}
                  className="px-5 py-2.5 bg-white text-foreground border border-zinc-300 text-xs font-medium rounded-md hover:border-foreground transition-colors inline-flex items-center gap-2 cursor-pointer whitespace-nowrap"
                >
                  Öne Çıkan Tektaş
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div className="pt-4 border-t border-border flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[11px] text-muted-foreground">
              <span>GIA / HRD / IGI Orijinal Sertifika</span>
              <span aria-hidden="true">·</span>
              <span>Brinks / Loomis Sigortalı Teslimat</span>
              <span aria-hidden="true">·</span>
              <span>Ömür Boyu Ücretsiz Bakım</span>
            </div>
          </div>
        </div>

        <div className="lg:col-span-6 relative min-h-[260px] lg:min-h-[380px] bg-muted">
          <img
            src={HERO_IMAGE_URL}
            alt="Pırlanta tektaş yüzük ve pırlanta bileklik koleksiyonu"
            referrerPolicy="no-referrer"
            className="w-full h-full object-cover"
          />
          {featuredSignature && (
            <button
              type="button"
              onClick={() => onSelectProduct(featuredSignature.product.parentSku)}
              className="absolute bottom-4 left-4 right-4 sm:right-auto bg-white/95 backdrop-blur-xs border border-border rounded-lg px-4 py-3 text-left hover:bg-white transition-colors cursor-pointer"
            >
              <div className="text-[11px] text-muted-foreground">
                İmza Tasarım · {featuredSignature.product.certificateAgency}
              </div>
              <div className="text-sm font-semibold text-foreground mt-0.5">
                {featuredSignature.product.title}
              </div>
              <div className="font-mono text-xs font-semibold text-foreground tabular-nums mt-0.5">
                {`${formatTrNumber(featuredSignature.metrics.discountedB2cPriceTry, 0)} TL`}
              </div>
            </button>
          )}
        </div>
      </section>
      ) : null}

      {/* Section 2: Filter Toolbar & Featured Collection Grid */}
      <section id="koleksiyon-grid" className="space-y-6 scroll-mt-24">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-border pb-4">
          <div>
            <h2 className="text-page-title text-2xl md:text-3xl">
              {category === 'Tümü' ? 'Seçkin Koleksiyon' : `${categoryLabel} Koleksiyonu`}
            </h2>
            <p className="text-xs text-muted-foreground mt-1 tabular-nums">
              {filteredItems.length} tasarım listeleniyor · Altın rengini kart üzerinden anında
              önizleyebilirsiniz
            </p>
          </div>

          <div className="text-xs text-muted-foreground font-mono tabular-nums self-start md:self-auto">
            {role === 'b2b' ? 'B2B Toptan Fiyatlandırma' : 'Canlı Has Altın Fiyatlı Vitrin'}
          </div>
        </div>

        {/* Category Tabs & Search / Sort Controls */}
        <div
          className={
            role === 'b2b'
              ? 'sticky top-16 z-10 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-3 bg-background/95 backdrop-blur border-y border-border space-y-3'
              : 'flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4'
          }
        >
          <div
            className={
              role === 'b2b'
                ? 'flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4'
                : 'contents'
            }
          >
          <div
            className={`flex items-center gap-1 p-1 rounded-lg overflow-x-auto no-scrollbar ${
              role === 'b2b' ? 'bg-muted border border-border' : 'bg-muted border border-border'
            }`}
          >
            {navCategories.map((cat) => (
              <button
                key={cat.value}
                type="button"
                onClick={() => setCategory(cat.value)}
                className={`px-3.5 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                  category === cat.value
                    ? 'bg-white text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tasarım, taş veya sertifika ara..."
                className="w-full pl-8 pr-3 py-2 text-xs bg-white border border-border rounded-md focus:outline-none focus:border-ring"
              />
            </div>

            <select
              value={colorFilter}
              onChange={(e) => setColorFilter(e.target.value as 'Tümü' | MetalColor)}
              aria-label="Metal rengi filtresi"
              className="px-3 py-2 text-xs bg-white border border-border rounded-md text-foreground focus:outline-none focus:border-ring"
            >
              <option value="Tümü">Tüm Altın Renkleri</option>
              {colorOptions.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label} Altın
                </option>
              ))}
            </select>

            <select
              value={merchFilter}
              onChange={(e) => setMerchFilter(e.target.value as MerchFilter)}
              aria-label="Koleksiyon filtresi"
              className="px-3 py-2 text-xs bg-white border border-border rounded-md text-foreground focus:outline-none focus:border-ring"
            >
              <option value="all">Tüm Parçalar</option>
              <option value="discounted">İndirimli Seçki</option>
              <option value="new_collection">Yeni Koleksiyon</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              aria-label="Sıralama"
              className="px-3 py-2 text-xs bg-white border border-border rounded-md text-foreground focus:outline-none focus:border-ring"
            >
              <option value="featured">Sıralama: Önerilen</option>
              <option value="price_asc">Fiyat: Artan</option>
              <option value="price_desc">Fiyat: Azalan</option>
              <option value="carat_desc">Karat: Yüksekten Düşüğe</option>
            </select>
          </div>
          </div>
        </div>

        {/* 3-Column Product Grid */}
        {filteredItems.length === 0 ? (
          <div className="bg-white border border-border rounded-lg p-12 text-center space-y-2">
            <div className="text-sm font-semibold text-foreground">
              Seçili filtrelere uygun tasarım bulunamadı
            </div>
            <p className="text-xs text-muted-foreground">
              Farklı bir kategori, altın rengi veya arama terimi deneyebilirsiniz.
            </p>
            <button
              type="button"
              onClick={resetAllFilters}
              className="mt-2 px-4 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors cursor-pointer"
            >
              Filtreleri Temizle
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredItems.map(({ product, metrics, media }) => {
              const activeColor = cardPreviewColors[product.parentSku] ?? product.metalColor;
              const isFav = favoriteSkus.includes(product.parentSku);
              const imgFailed = failedImages[`${product.parentSku}-${activeColor}`];
              const hoverFailed = failedImages[`${product.parentSku}-hover`];
              const activeDiscountPct =
                role === 'b2b'
                  ? metrics.ledger.hasB2bChannel && metrics.ledger.b2bSubtotalBeforeDiscountLc > 0
                    ? (metrics.ledger.b2bDiscountLc /
                        metrics.ledger.b2bSubtotalBeforeDiscountLc) *
                      100
                    : 0
                  : metrics.ledger.hasB2cChannel && metrics.discountAmountTry > 0
                    ? metrics.ledger.effectiveB2cDiscountPct
                    : 0;

              return (
                <article
                  key={product.parentSku}
                  onClick={() => onSelectProduct(product.parentSku, activeColor)}
                  className="group bg-white border border-border hover:border-border rounded-lg overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md cursor-pointer flex flex-col justify-between"
                >
                  {/* Studio Media Stage */}
                  <div className="relative bg-muted aspect-[4/3] overflow-hidden border-b border-border">
                    <LuxuryMerchRibbon
                      discountPct={activeDiscountPct}
                      isNewCollection={false}
                      size="card"
                    />

                    {/* Wishlist Heart Button */}
                    {onToggleFavorite && (
                      <button
                        type="button"
                        aria-label={isFav ? 'Favorilerden çıkar' : 'Favorilere ekle'}
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleFavorite(product.parentSku);
                        }}
                        className={`absolute top-3 right-3 z-20 w-8 h-8 rounded-full bg-white/95 border border-border/80 flex items-center justify-center transition-colors cursor-pointer ${
                          isFav ? 'text-destructive' : 'text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        <Heart className={`w-4 h-4 ${isFav ? 'fill-destructive' : ''}`} />
                      </button>
                    )}

                    {!imgFailed ? (
                      <>
                        <img
                          src={media.mainUrl}
                          alt={`${product.title} — ${activeColor} Altın`}
                          referrerPolicy="no-referrer"
                          onError={() =>
                            setFailedImages((prev) => ({
                              ...prev,
                              [`${product.parentSku}-${activeColor}`]: true,
                            }))
                          }
                          style={media.toneFilter ? { filter: media.toneFilter } : undefined}
                          className={`w-full h-full object-cover transition-all duration-500 ease-out ${
                            !hoverFailed
                              ? 'group-hover:opacity-0 group-hover:scale-105'
                              : 'group-hover:scale-105'
                          }`}
                        />
                        {!hoverFailed && (
                          <img
                            src={media.hoverUrl}
                            alt={`${product.title} — ${media.hoverLabel}`}
                            referrerPolicy="no-referrer"
                            onError={() =>
                              setFailedImages((prev) => ({
                                ...prev,
                                [`${product.parentSku}-hover`]: true,
                              }))
                            }
                            style={media.toneFilter ? { filter: media.toneFilter } : undefined}
                            className="absolute inset-0 w-full h-full object-cover opacity-0 scale-105 group-hover:opacity-100 group-hover:scale-100 transition-all duration-500 ease-out"
                          />
                        )}
                      </>
                    ) : (
                      <div className="w-full h-full flex items-center justify-center p-6">
                        <JewelryIllustration
                          visualType={product.visualType}
                          metalColor={activeColor}
                          stoneType={product.stoneType}
                          centerStoneCarat={product.centerStoneCarat}
                          sideStoneCarat={product.sideStoneCarat}
                          className="w-full max-w-[200px] h-auto"
                        />
                      </div>
                    )}
                  </div>

                  {/* Card Body */}
                  <div className="p-5 flex-1 flex flex-col justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                        <span>
                          {product.subCategory} · {product.certificateAgency} · {product.parentSku}
                        </span>
                        <span
                          className={
                            product.stockStatus === 'Stokta'
                              ? 'text-success font-medium'
                              : product.stockStatus === 'Siparişe Özel'
                                ? 'text-warning font-medium'
                                : 'text-red-700 font-medium'
                          }
                        >
                          {product.stockStatus}
                        </span>
                      </div>

                      <h3 className="text-lg font-semibold text-foreground group-hover:text-foreground transition-colors leading-snug">
                        {product.title}
                      </h3>

                      <p className="text-xs text-muted-foreground tabular-nums">
                        {product.purityCode} {activeColor} Altın ·{' '}
                        {formatTrNumber(metrics.totalStoneCarat, 2)} ct · {product.stoneColorGrade}/
                        {product.stoneClarity} · {formatTrNumber(product.grossWeightGram, 2)} gr
                      </p>
                    </div>

                    {/* Interactive Color Swatches */}
                    <div className="flex items-center justify-between pt-3 border-t border-border">
                      <div className="flex items-center gap-2">
                        {product.availableColors.map((color) => {
                          const dotBg =
                            color === 'Beyaz'
                              ? 'bg-gradient-to-br from-zinc-100 to-zinc-300'
                              : color === 'Sarı'
                                ? 'bg-gradient-to-br from-[#F4DF9B] to-[#C89D3C]'
                                : 'bg-gradient-to-br from-[#F3C9BA] to-[#C67F67]';
                          const isCurrent = activeColor === color;
                          return (
                            <button
                              key={color}
                              type="button"
                              aria-label={`${product.title} — ${color} Altın`}
                              onClick={(e) => handleSwatchClick(e, product.parentSku, color)}
                              className={`w-5 h-5 rounded-full border transition-transform cursor-pointer ${dotBg} ${
                                isCurrent
                                  ? 'border-foreground scale-110 ring-2 ring-zinc-900/15'
                                  : 'border-zinc-300 hover:scale-105'
                              }`}
                            />
                          );
                        })}
                        <span className="text-[11px] text-muted-foreground ml-1">{activeColor} Altın</span>
                      </div>

                      <span className="text-[11px] text-muted-foreground">İncele</span>
                    </div>

                    {/* Role-Scoped Price & Action */}
                    <div className="pt-3 border-t border-border">
                      {role === 'b2b' &&
                        (metrics.ledger.hasB2bChannel ? (
                          <div className="space-y-1.5 rounded-md border border-border bg-muted/40 px-3 py-2">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[10px] font-semibold uppercase tracking-wider text-foreground">
                                Toptan
                              </span>
                              <span className="font-mono text-lg font-bold text-foreground tabular-nums">
                                {formatCurrencyValue(
                                  metrics.finalB2bPriceCurrency,
                                  product.pricingCurrency
                                )}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground tabular-nums">
                              <span>
                                Has: {formatTrNumber(metrics.fireIncludedFineMetalGram, 3)} gr
                              </span>
                              <span className="font-medium text-foreground">
                                {formatTrNumber(metrics.finalB2bPriceTry, 0)} TL
                              </span>
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-muted-foreground">Yalnızca perakende kanalında</div>
                        ))}

                      {role === 'erp' && (
                        <div className="space-y-1 text-[11px] font-mono tabular-nums">
                          <div className="flex items-center justify-between text-foreground">
                            <span>
                              B2B{' '}
                              {formatCurrencyValue(
                                metrics.finalB2bPriceCurrency,
                                product.pricingCurrency
                              )}
                            </span>
                            <span className="text-foreground font-semibold">
                              B2C {formatTrNumber(metrics.discountedB2cPriceTry, 0)} TL
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-muted-foreground">
                            <span>
                              Maliyet:{' '}
                              {formatTrNumber(
                                product.pricingMode === '1'
                                  ? metrics.p1TotalCostTry
                                  : metrics.p2SupplierPriceTry,
                                0
                              )}{' '}
                              TL
                            </span>
                            <span>
                              Has: {formatTrNumber(metrics.fireIncludedFineMetalGram, 3)} gr
                            </span>
                          </div>
                        </div>
                      )}

                      {(role === 'b2b' || role === 'erp') &&
                        metrics.ledger.hasB2bChannel &&
                        onQuickAddB2b && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onQuickAddB2b(product, metrics);
                              flashAdded(`b2b:${product.parentSku}`);
                            }}
                            className="mt-3 w-full py-2 px-3 rounded-md border border-border bg-muted hover:bg-primary hover:text-primary-foreground hover:border-foreground text-xs font-medium text-foreground transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                          >
                            {recentAddedSku === `b2b:${product.parentSku}` ? (
                              <>
                                <Check className="w-3.5 h-3.5 text-success" />
                                Sipariş Fişine Eklendi
                              </>
                            ) : (
                              <>
                                <ClipboardList className="w-3.5 h-3.5" />
                                Sipariş Fişine Ekle
                              </>
                            )}
                          </button>
                        )}

                      {!onQuickAddB2b && onQuickAddB2c && metrics.ledger.hasB2cChannel && (
                        <button
                          type="button"
                          disabled={product.stockStatus === 'Tükendi'}
                          onClick={(e) => {
                            e.stopPropagation();
                            onQuickAddB2c(product, metrics);
                            flashAdded(`b2c:${product.parentSku}`);
                          }}
                          className="mt-3 w-full py-2 px-3 rounded-md border border-border bg-muted hover:bg-primary hover:text-primary-foreground hover:border-foreground text-xs font-medium text-foreground transition-colors flex items-center justify-center gap-1.5 disabled:opacity-40 cursor-pointer"
                        >
                          <ShoppingBag className="w-3.5 h-3.5" />
                          Sepete Ekle
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* Section 3: Craftsmanship & Jewelry Trust Band */}
      {role !== 'b2b' ? (
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 border-t border-border">
        <div className="bg-white border border-border rounded-lg p-6 space-y-2">
          <Sparkles className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold text-foreground">
            Uluslararası Sertifika
          </h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Tüm tektaş ve pırlanta tasarımlarımız bağımsız GIA, HRD veya IGI laboratuvar sertifikası
            ve lazer seri numarası ile teslim edilir.
          </p>
        </div>

        <div className="bg-white border border-border rounded-lg p-6 space-y-2">
          <ShieldCheck className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold text-foreground">
            Tam Sigortalı Değerli Kargo
          </h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Siparişleriniz atölyeden çıkışından imza karşılığı teslimat anına kadar Brinks ve Loomis
            sigorta poliçesi kapsamındadır.
          </p>
        </div>

        <div className="bg-white border border-border rounded-lg p-6 space-y-2">
          <RefreshCw className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold text-foreground">
            Ömür Boyu Atölye Bakımı
          </h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            İlk yıl ücretsiz yüzük ölçü tadilatı, yılda iki kez ücretsiz ultrasonik temizlik, cila,
            rodaj ve tırnak kontrolü sunulur.
          </p>
        </div>
      </section>
      ) : null}
    </div>
  );
}

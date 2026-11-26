import { useState } from 'react';
import {
  Check,
  ChevronRight,
  ClipboardList,
  Gift,
  Heart,
  Layers,
  RefreshCw,
  Ruler,
  Share2,
  Shield,
  ShoppingBag,
  Sparkles,
  Truck,
} from 'lucide-react';
import {
  AudienceRole,
  ComputedJewelryMetrics,
  LiveRates,
  MetalColor,
  ProductState,
  PurityCode,
} from '../types/jewelry';
import type { B2bSupplyType } from '../features/commerce/types';
import {
  computeJewelryMetrics,
  formatCurrencyValue,
  formatTrNumber,
  PURITY_MAP,
} from '../utils/pricingEngine';
import { resolveProductMedia } from '../data/productMedia';
import { SizeGuideDialog } from '../features/commerce/components/SizeGuideDialog';
import { RingShowcase } from './RingShowcase';
import {
  StorefrontBreadcrumb,
  StorefrontProductCard,
} from '../features/storefront/components/StorefrontUI';

export interface ProductCardB2cAddPayload {
  qty: number;
  engravingText: string;
  giftWrap: boolean;
}

export interface ProductCardB2bAddPayload {
  lines: Array<{ size: number; qty: number }>;
  supplyType: B2bSupplyType;
  dealerStampNote: string;
}

interface ProductCardViewProps {
  product: ProductState;
  relatedProducts?: ProductState[];
  rates: LiveRates;
  computed: ComputedJewelryMetrics;
  role: AudienceRole;
  isFavorite?: boolean;
  onToggleFavorite?: () => void;
  onRoleChange: (role: AudienceRole) => void;
  onUpdateProduct: (patch: Partial<ProductState>) => void;
  onOpenPricing: () => void;
  onBackToVitrin: () => void;
  onSelectRelatedProduct?: (parentSku: string) => void;
  onAddToB2cCart?: (payload: ProductCardB2cAddPayload) => void;
  onAddToB2bOrder?: (payload: ProductCardB2bAddPayload) => void;
  onOpenB2cCart?: () => void;
  onOpenB2bOrder?: () => void;
}

const SIZE_STOCK_MAP: Record<number, { status: 'Stokta' | 'Tükendi' | 'Siparişe Özel'; qty: number; barcode: string }> = {
  10: { status: 'Siparişe Özel', qty: 0, barcode: 'SİPARİŞ-10' },
  11: { status: 'Siparişe Özel', qty: 0, barcode: 'SİPARİŞ-11' },
  12: { status: 'Tükendi', qty: 0, barcode: 'P692102' },
  13: { status: 'Stokta', qty: 1, barcode: 'P692104' },
  14: { status: 'Stokta', qty: 1, barcode: 'P692105' },
  15: { status: 'Stokta', qty: 1, barcode: 'P692106' },
  16: { status: 'Siparişe Özel', qty: 0, barcode: 'SİPARİŞ-16' },
  17: { status: 'Siparişe Özel', qty: 0, barcode: 'SİPARİŞ-17' },
  18: { status: 'Stokta', qty: 1, barcode: 'P692118' },
};

export function ProductCardView({
  product,
  relatedProducts = [],
  rates,
  computed,
  role,
  isFavorite = false,
  onToggleFavorite,
  onRoleChange,
  onUpdateProduct,
  onOpenPricing,
  onBackToVitrin,
  onSelectRelatedProduct,
  onAddToB2cCart,
  onAddToB2bOrder,
  onOpenB2cCart,
  onOpenB2bOrder,
}: ProductCardViewProps) {
  const [dealerName, setDealerName] = useState('Aydın Kuyumculuk · Nişantaşı');
  const [dealerMarkupPct, setDealerMarkupPct] = useState(25);
  const [hideDealerPrice, setHideDealerPrice] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);
  const [cartNotice, setCartNotice] = useState<string | null>(null);
  const [sizeGuideOpen, setSizeGuideOpen] = useState(false);

  // B2C retail personalization state
  const [b2cEngraving, setB2cEngraving] = useState('');
  const [b2cGiftWrap, setB2cGiftWrap] = useState(false);

  // B2B wholesale dealer ordering & assortment state
  const [b2bQty, setB2bQty] = useState(3);
  const [b2bSupplyType, setB2bSupplyType] = useState<B2bSupplyType>(
    product.stockStatus === 'Stokta' ? 'STOCK' : 'PRODUCTION'
  );
  const [b2bStampNote, setB2bStampNote] = useState('');
  const [assortmentOpen, setAssortmentOpen] = useState(false);
  const [assortmentQtyMap, setAssortmentQtyMap] = useState<Record<number, number>>({
    13: 1,
    14: 2,
    15: 1,
  });

  const dealerCustomerPriceTry = computed.finalB2bPriceTry * (1 + dealerMarkupPct / 100);
  const isRing = product.category === 'Yüzük';
  const sizeUnitLabel =
    product.category === 'Kolye'
      ? 'Zincir Boyu'
      : product.category === 'Bileklik'
        ? 'Bileklik Boyu'
        : product.category === 'Küpe'
          ? 'Çap / Boy'
          : 'Yüzük Ölçüsü';

  const handleSizeSelect = (size: number) => {
    const info = isRing
      ? SIZE_STOCK_MAP[size] ?? { status: 'Siparişe Özel' as const, qty: 0, barcode: `SİPARİŞ-${size}` }
      : { status: 'Stokta' as const, qty: Math.max(1, product.stockQty), barcode: `${product.barcode.slice(0, 5)}${size}` };
    const weightDelta = isRing ? (size - product.variantSize) * 0.07 : (size - product.variantSize) * 0.04;
    const nextWeight = Math.max(1.2, Number((product.grossWeightGram + weightDelta).toFixed(2)));
    onUpdateProduct({
      variantSize: size,
      stockStatus: info.status,
      stockQty: info.qty,
      barcode: info.barcode,
      grossWeightGram: nextWeight,
    });
  };

  const handlePuritySelect = (purityCode: PurityCode) => {
    const currentFactor =
      product.purityCode === '18K'
        ? 1.11
        : product.purityCode === '22K'
          ? 1.24
          : product.purityCode === '8K'
            ? 0.91
            : 1;
    const nextFactor =
      purityCode === '18K' ? 1.11 : purityCode === '22K' ? 1.24 : purityCode === '8K' ? 0.91 : 1;
    const nextWeight = Number(((product.grossWeightGram / currentFactor) * nextFactor).toFixed(2));
    onUpdateProduct({
      purityCode,
      grossWeightGram: nextWeight,
      description: `${formatTrNumber(computed.totalStoneCarat, 2)} Karat ${product.stoneColorGrade} Renk ${product.stoneClarity} Berraklık ${PURITY_MAP[purityCode].label.split(' ')[0]} Ayar ${product.metalColor} Altın ${product.subCategory}`,
    });
  };

  const handleColorSelect = (metalColor: MetalColor) => {
    const code = metalColor === 'Beyaz' ? 'BYZ' : metalColor === 'Sarı' ? 'SRY' : 'RSE';
    onUpdateProduct({
      metalColor,
      galleryImages: [
        `${product.parentSku}-${code}_main.jpg`,
        `${product.parentSku}-${code}_model.jpg`,
        `${product.parentSku}-${code}_side.jpg`,
      ],
      reelsVideoUrl: `${product.parentSku}-${code}_reels_9x16.mp4`,
      spin360Url: `${product.parentSku}-${code}_360.mp4`,
      catalogCleanImageUrl: `${product.parentSku}-${code}_clean_png.png`,
      description: `${formatTrNumber(computed.totalStoneCarat, 2)} Karat ${product.stoneColorGrade} Renk ${product.stoneClarity} Berraklık ${product.purityCode.replace('K', '')} Ayar ${metalColor} Altın ${product.subCategory}`,
    });
  };

  const handleCaratSelect = (centerCarat: number) => {
    const total = Number((centerCarat + product.sideStoneCarat).toFixed(2));
    const estStoneCost = Math.round(centerCarat * 800 + product.sideStoneCarat * 450);
    onUpdateProduct({
      centerStoneCarat: centerCarat,
      p1StoneCostCurrency: estStoneCost,
      ledger: {
        ...product.ledger,
        stoneFcPrice: estStoneCost,
      },
      title: `${total.toFixed(2)} Karat ${product.stoneType} ${product.subCategory.split('-')[1] ?? product.category} ${product.category}`,
      description: `${total.toFixed(2)} Karat ${product.stoneColorGrade} Renk ${product.stoneClarity} Berraklık ${product.purityCode.replace('K', '')} Ayar ${product.metalColor} Altın ${product.subCategory}`,
    });
  };

  const handleCopyShare = async () => {
    const shareText = `${product.socialShareCaption}\nSKU: ${computed.sku}\n${
      hideDealerPrice
        ? 'Fiyat bilgisi için mağazamızla iletişime geçiniz.'
        : `Satış Fiyatı: ${formatTrNumber(dealerCustomerPriceTry, 0)} TL`
    }\nKatalog: ${product.b2bCatalogShareEndpoint}?dealer=${encodeURIComponent(dealerName)}&markup=${dealerMarkupPct}`;
    try {
      await navigator.clipboard.writeText(shareText);
      setCopiedShare(true);
      setTimeout(() => setCopiedShare(false), 1800);
    } catch {
      setCopiedShare(false);
    }
  };

  const showFeedback = (message: string) => {
    setCartNotice(message);
    window.setTimeout(() => setCartNotice(null), 3500);
  };

  const assortmentTotalPieces = product.availableSizes.reduce(
    (sum, s) => sum + Math.max(0, assortmentQtyMap[s] ?? 0),
    0
  );

  const effectiveB2bPieces = assortmentOpen
    ? Math.max(0, assortmentTotalPieces)
    : Math.max(1, b2bQty);

  const handlePrimaryOrderAction = () => {
    if (role === 'b2c') {
      onAddToB2cCart?.({
        qty: 1,
        engravingText: b2cEngraving.trim(),
        giftWrap: b2cGiftWrap,
      });
      showFeedback(
        `${computed.sku} (${sizeUnitLabel} ${product.variantSize}) B2C sepete eklendi — Kur 15 dk sabitlendi.`
      );
      return;
    }

    if (role === 'b2b') {
      const targetLines = assortmentOpen
        ? product.availableSizes
            .map((size) => ({ size, qty: Math.max(0, assortmentQtyMap[size] ?? 0) }))
            .filter((entry) => entry.qty > 0)
        : [{ size: product.variantSize, qty: Math.max(1, b2bQty) }];

      if (targetLines.length === 0) return;

      onAddToB2bOrder?.({
        lines: targetLines,
        supplyType: b2bSupplyType,
        dealerStampNote: b2bStampNote.trim(),
      });
      const totalAdded = targetLines.reduce((sum, l) => sum + l.qty, 0);
      showFeedback(
        `${product.parentSku} · ${totalAdded} adet (${targetLines.length} ölçü) B2B sipariş fişine eklendi.`
      );
      return;
    }

    showFeedback(`${computed.sku} varyant değişiklikleri kaydedildi.`);
  };

  const isB2c = role === 'b2c';

  return (
    <div className={isB2c ? 'space-y-10 pb-20 md:pb-0' : 'space-y-10'}>
      {/* Clean Luxury Breadcrumb & Product Header */}
      <div
        className={`flex flex-col md:flex-row md:items-end justify-between gap-4 border-b pb-6 ${
          isB2c ? 'border-border' : 'border-border'
        }`}
      >
        <div className="space-y-2.5 min-w-0">
          {isB2c ? (
            <StorefrontBreadcrumb
              items={[
                { label: 'Ana Sayfa', to: '/' },
                { label: 'Koleksiyon', onClick: onBackToVitrin },
                { label: product.category },
                { label: product.title },
              ]}
            />
          ) : (
            <nav
              aria-label="Sayfa yolu"
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <button
                type="button"
                onClick={onBackToVitrin}
                className="hover:text-foreground transition-colors cursor-pointer"
              >
                Koleksiyon
              </button>
              <ChevronRight className="w-3 h-3 text-muted-foreground" />
              <span>{product.category}</span>
              <ChevronRight className="w-3 h-3 text-muted-foreground" />
              <span className="text-foreground font-medium truncate max-w-[260px]">
                {product.title}
              </span>
            </nav>
          )}

          <h1
            className={
              isB2c
                ? 'font-serif text-3xl sm:text-4xl font-normal text-foreground leading-tight'
                : 'text-page-title text-3xl md:text-4xl font-semibold text-foreground leading-tight'
            }
          >
            {product.title}
          </h1>
          <p className={`text-sm max-w-2xl leading-relaxed ${isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}`}>
            {product.description}
          </p>
        </div>

        <div
          className={`text-xs font-mono self-start md:self-auto shrink-0 ${
            isB2c ? 'text-muted-foreground' : 'text-muted-foreground'
          }`}
        >
          SKU:{' '}
          <span className={`font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
            {computed.sku}
          </span>
        </div>
      </div>

      {/* Main 2-Column Product Hero Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left: Interactive Jewelry Media Studio */}
        <div className="lg:col-span-6 space-y-6">
          <RingShowcase
            product={product}
            computed={computed}
            dealerWatermarkName={dealerName}
            showDealerWatermark={role === 'b2b' && product.dynamicDealerWatermark}
            b2cLuxuryMode={isB2c}
          />

          {/* B2B Digital Catalog & Dynamic Watermark Tool (Section 12 — B2B & ERP only) */}
          {role !== 'b2c' && (
            <div className="bg-card border border-border rounded-lg p-6 space-y-4">
              <div className="flex items-start justify-between gap-4 border-b border-border pb-3.5">
                <div>
                  <h2 className="text-sm font-semibold text-foreground">
                    Bayi Müşteri Sunum & Filigran Aracı
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Mağaza adınızı ve satış marjınızı belirleyip müşterinize tek tıkla paylaşım metni oluşturun.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    onUpdateProduct({ dynamicDealerWatermark: !product.dynamicDealerWatermark })
                  }
                  className="text-xs font-medium text-foreground hover:text-foreground underline underline-offset-4 whitespace-nowrap shrink-0"
                >
                  Filigran: {product.dynamicDealerWatermark ? 'Aktif' : 'Pasif'}
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">
                    Bayi Mağaza Adı (Filigran)
                  </label>
                  <input
                    type="text"
                    value={dealerName}
                    onChange={(e) => setDealerName(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-border rounded-md focus:outline-none focus:border-ring"
                  />
                </div>
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">
                    Bayi Müşteri Kâr Marjı (%)
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      max={150}
                      value={dealerMarkupPct}
                      onChange={(e) => setDealerMarkupPct(Number(e.target.value) || 0)}
                      className="w-24 px-3 py-2 text-xs font-mono tabular-nums border border-border rounded-md focus:outline-none focus:border-ring"
                    />
                    <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={hideDealerPrice}
                        onChange={(e) => setHideDealerPrice(e.target.checked)}
                        className="accent-foreground"
                      />
                      Fiyatı Gizle
                    </label>
                  </div>
                </div>
              </div>

              <div className="bg-muted border border-border rounded-md p-3.5 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Müşteriye Gidecek Katalog Fiyatı</span>
                  <span className="font-mono font-semibold text-foreground tabular-nums">
                    {hideDealerPrice
                      ? 'Fiyat Gizli (Teklif İste)'
                      : `${formatTrNumber(dealerCustomerPriceTry, 2)} TL`}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Tek Tıkla Katalog Linki</span>
                  <span className="font-mono text-[11px] text-muted-foreground truncate max-w-[260px]">
                    {product.b2bCatalogShareEndpoint}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 pt-1">
                <p className="text-xs text-muted-foreground line-clamp-2">{product.socialShareCaption}</p>
                <button
                  type="button"
                  onClick={handleCopyShare}
                  className="px-3.5 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors flex items-center gap-1.5 whitespace-nowrap shrink-0"
                >
                  {copiedShare ? (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      Metin Kopyalandı
                    </>
                  ) : (
                    <>
                      <Share2 className="w-3.5 h-3.5" />
                      WhatsApp / IG Kopyala
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: Contiguous Purchase / Variant Configuration Module */}
        <div
          className={`lg:col-span-6 border rounded-[6px] p-5 sm:p-7 md:p-8 space-y-6 ${
            isB2c
              ? 'bg-card border-border'
              : 'bg-card border-border rounded-lg'
          }`}
        >
          {/* Identity & Stock Summary */}
          <div
            className={`flex flex-wrap items-center justify-between gap-2 text-xs border-b pb-4 ${
              isB2c ? 'text-muted-foreground border-border/80' : 'text-muted-foreground border-border'
            }`}
          >
            <div className="font-mono">
              SKU:{' '}
              <span className={`font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                {computed.sku}
              </span>{' '}
              · Barkod:{' '}
              <span className={isB2c ? 'text-foreground' : 'text-foreground'}>{product.barcode}</span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`font-medium ${
                  product.stockStatus === 'Tükendi'
                    ? 'text-destructive'
                    : product.stockStatus === 'Siparişe Özel'
                      ? 'text-muted-foreground'
                      : 'text-foreground'
                }`}
              >
                {product.stockStatus}
              </span>
              {role !== 'b2c' && (
                <>
                  <span>·</span>
                  <span className="font-mono tabular-nums">{product.stockQty} Adet</span>
                  <span>·</span>
                  <span>{product.ownershipType}</span>
                </>
              )}
            </div>
          </div>

          {/* Pricing Block — Scoped by Audience Role */}
          <div className="space-y-3">
            {role === 'b2c' &&
              (computed.ledger.hasB2cChannel ? (
                <div>
                  <div className="flex flex-wrap items-baseline gap-3">
                    <span className="text-3xl font-semibold text-foreground font-mono tabular-nums">
                      {formatTrNumber(computed.discountedB2cPriceTry, 2)} TL
                    </span>
                    {computed.discountAmountTry > 0 && (
                      <span className="text-sm text-muted-foreground line-through font-mono tabular-nums">
                        {formatTrNumber(computed.finalB2cPriceTry, 2)} TL
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                    KDV Dahil
                    {computed.discountAmountTry > 0 ? (
                      <span className="text-foreground font-medium">
                        {' '}
                        · %{Math.round(computed.ledger.effectiveB2cDiscountPct)} kampanya
                        indirimi ({formatTrNumber(computed.discountAmountTry, 2)} TL avantaj)
                      </span>
                    ) : null}{' '}
                    · Tahmini teslim: {product.leadTimeDays} İş Günü
                  </p>
                </div>
              ) : (
                <div className="bg-muted border border-border rounded-[4px] p-4 text-xs text-muted-foreground">
                  Bu ürün için <strong>B2C satış kanalı</strong> tanımlanmadı.
                </div>
              ))}

            {role === 'b2b' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-muted border border-border rounded-md p-4">
                <div>
                  <div className="text-xs text-muted-foreground">Nihai B2B Bayi Toptan Fiyatı</div>
                  {computed.ledger.hasB2bChannel ? (
                    <>
                      <div className="text-2xl font-semibold text-foreground font-mono tabular-nums mt-1">
                        {formatCurrencyValue(computed.finalB2bPriceCurrency, product.pricingCurrency)}
                      </div>
                      <div className="text-xs font-mono text-muted-foreground tabular-nums mt-0.5">
                        {formatTrNumber(computed.finalB2bPriceTry, 2)} TL (Anlık Kur)
                      </div>
                    </>
                  ) : (
                    <div className="text-xs text-muted-foreground mt-1.5">
                      B2B satış kanalı tanımlı değil
                    </div>
                  )}
                </div>
                <div className="sm:border-l sm:border-border sm:pl-4">
                  <div className="text-xs text-muted-foreground">Tavsiye Edilen B2C Vitrin Fiyatı</div>
                  {computed.ledger.hasB2cChannel ? (
                    <>
                      <div className="text-xl font-semibold text-foreground font-mono tabular-nums mt-1">
                        {formatTrNumber(computed.discountedB2cPriceTry, 2)} TL
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        Liste: {formatTrNumber(computed.finalB2cPriceTry, 2)} TL · Has Altın:{' '}
                        <span className="font-mono tabular-nums">
                          {formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="text-xs text-muted-foreground mt-1.5">
                      B2C satış kanalı tanımlı değil
                    </div>
                  )}
                </div>
              </div>
            )}

            {role === 'erp' && (
              <div className="bg-muted border border-border rounded-md p-4 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground">
                    Aktif Model: {product.pricingMode === '1' ? '1 - Detaylı (Maden + İşçilik + Taş)' : '2 - Sade (Tedarikçi Hazır Fiyatı)'}
                  </span>
                  <button
                    type="button"
                    onClick={onOpenPricing}
                    className="text-muted-foreground hover:text-foreground font-medium underline underline-offset-4 cursor-pointer"
                  >
                    Fiyat Motorunda Düzenle
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-3 pt-1 border-t border-border/80">
                  <div>
                    <div className="text-[11px] text-muted-foreground">Geliş Maliyeti (TL)</div>
                    <div className="text-sm font-mono font-semibold text-foreground tabular-nums mt-0.5">
                      {formatTrNumber(
                        product.pricingMode === '1'
                          ? computed.p1TotalCostTry
                          : computed.p2SupplierPriceTry,
                        2
                      )}{' '}
                      TL
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-muted-foreground">B2B Toptan</div>
                    <div className="text-sm font-mono font-semibold text-foreground tabular-nums mt-0.5">
                      {computed.ledger.hasB2bChannel
                        ? formatCurrencyValue(computed.finalB2bPriceCurrency, product.pricingCurrency)
                        : 'Tanımsız'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-muted-foreground">B2C İndirimli</div>
                    <div className="text-sm font-mono font-semibold text-foreground tabular-nums mt-0.5">
                      {computed.ledger.hasB2cChannel
                        ? `${formatTrNumber(computed.discountedB2cPriceTry, 2)} TL`
                        : 'Tanımsız'}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Interactive Variant Axes (Rule M3, M4, M8) */}
          <div className={`space-y-5 pt-2 border-t ${isB2c ? 'border-border/80' : 'border-border'}`}>
            {/* Metal Rengi */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className={`font-medium ${isB2c ? 'text-muted-foreground' : 'text-foreground'}`}>
                  Metal Rengi:{' '}
                  <span className={isB2c ? 'text-foreground' : 'text-foreground'}>
                    {product.metalColor} Altın
                  </span>
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {(['Beyaz', 'Sarı', 'Rose'] as MetalColor[]).map((color) => {
                  const swatch =
                    color === 'Beyaz'
                      ? 'bg-gradient-to-br from-[#F4F3F1] to-[#CFCBC4]'
                      : color === 'Sarı'
                        ? 'bg-gradient-to-br from-[#F4DF9B] to-[#C89D3C]'
                        : 'bg-gradient-to-br from-[#F1C7B8] to-[#BF7E68]';
                  const active = product.metalColor === color;
                  return (
                    <button
                      key={color}
                      type="button"
                      onClick={() => handleColorSelect(color)}
                      className={`min-h-[40px] px-3.5 py-2 text-xs font-medium rounded-md border transition-colors flex items-center gap-2 whitespace-nowrap shrink-0 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        active
                          ? 'border-foreground bg-card text-foreground ring-1 ring-ring/40'
                          : 'border-input bg-background text-muted-foreground hover:border-ring hover:text-foreground'
                      }`}
                    >
                      <span className={`w-3.5 h-3.5 rounded-full border border-black/15 ${swatch}`} />
                      {color}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Ayar (Purity) */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className={`font-medium ${isB2c ? 'text-muted-foreground' : 'text-foreground'}`}>
                  Ayar:{' '}
                  <span className={isB2c ? 'text-foreground' : 'text-foreground'}>
                    {PURITY_MAP[product.purityCode]?.label ?? product.purityCode}
                  </span>
                </span>
                {!isB2c && (
                  <span className="text-muted-foreground font-mono">
                    milyem: {formatTrNumber(computed.millesimalFineness, 3)}
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {(['8K', '14K', '18K', '22K'] as PurityCode[]).map((code) => {
                  const active = product.purityCode === code;
                  return (
                    <button
                      key={code}
                      type="button"
                      onClick={() => handlePuritySelect(code)}
                      className={`min-h-[40px] px-3.5 py-2 text-xs font-mono font-medium rounded-[4px] border transition-colors whitespace-nowrap shrink-0 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        active
                          ? 'border-foreground bg-primary text-primary-foreground'
                          : 'border-input bg-background text-foreground hover:border-ring'
                      }`}
                    >
                      {code}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Merkez Taş Karatı */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className={`font-medium ${isB2c ? 'text-muted-foreground' : 'text-foreground'}`}>
                  Toplam Karat:{' '}
                  <span className={`font-mono tabular-nums ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                    {formatTrNumber(computed.totalStoneCarat, 2)} ct
                  </span>{' '}
                  <span className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>
                    ({formatTrNumber(product.centerStoneCarat, 2)} merkez +{' '}
                    {formatTrNumber(product.sideStoneCarat, 2)} yan)
                  </span>
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {[0.3, 0.5, 0.9].map((centerCt) => {
                  const totalCt = (centerCt + product.sideStoneCarat).toFixed(2);
                  const active = product.centerStoneCarat === centerCt;
                  return (
                    <button
                      key={centerCt}
                      type="button"
                      onClick={() => handleCaratSelect(centerCt)}
                      className={`min-h-[40px] px-3.5 py-2 text-xs font-mono font-medium rounded-[4px] border transition-colors whitespace-nowrap shrink-0 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        active
                          ? 'border-foreground bg-primary text-primary-foreground'
                          : 'border-input bg-background text-foreground hover:border-ring'
                      }`}
                    >
                      {totalCt} ct
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Ölçü / Boy (Rule M8: Bağımsız stok) */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className={`font-medium ${isB2c ? 'text-muted-foreground' : 'text-foreground'}`}>
                  {sizeUnitLabel}:{' '}
                  <span className={`font-mono ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                    {isRing
                      ? `No ${product.variantSize}`
                      : `${product.variantSize} ${product.category === 'Küpe' ? 'mm' : 'cm'}`}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => setSizeGuideOpen(true)}
                  className={`inline-flex items-center gap-1 underline underline-offset-4 cursor-pointer ${
                    isB2c
                      ? 'text-muted-foreground hover:text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Ruler className="w-3 h-3" />
                  Ölçü Rehberi
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {product.availableSizes.map((size) => {
                  const info = isRing ? SIZE_STOCK_MAP[size] : undefined;
                  const isOut = isRing && info?.status === 'Tükendi';
                  const isSelected = product.variantSize === size;
                  return (
                    <button
                      key={size}
                      type="button"
                      onClick={() => handleSizeSelect(size)}
                      title={`${sizeUnitLabel} ${size}${info ? ` — ${info.status}` : ''}`}
                      className={`min-w-[44px] min-h-[40px] px-2.5 py-2 text-xs font-mono rounded-[4px] border transition-colors tabular-nums cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        isSelected
                          ? 'border-foreground bg-primary text-primary-foreground'
                          : isOut
                            ? 'border-border bg-muted text-muted-foreground line-through'
                            : 'border-input bg-background text-foreground hover:border-ring'
                      }`}
                    >
                      {size}
                    </button>
                  );
                })}
              </div>
              <p className={`text-[11px] mt-2 leading-relaxed ${isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}`}>
                {product.stockStatus === 'Stokta'
                  ? 'Seçili ölçü stokta hazırdır — 1–2 iş günü içinde sigortalı kurye ile sevk edilir.'
                  : product.stockStatus === 'Siparişe Özel'
                    ? 'Seçili ölçü atölyemizde sizin için özel olarak hazırlanır (5–7 iş günü).'
                    : 'Seçili ölçü şu an tükendi. Farklı bir ölçü seçebilirsiniz.'}
              </p>
            </div>
          </div>

          {/* Role-Specific Commerce Controls (B2C Personalization vs B2B Assortment/Supply) */}
          {role === 'b2c' && product.stockStatus !== 'Tükendi' && (
            <div className="rounded-[6px] border border-border bg-background p-4 space-y-2.5 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="space-y-1.5">
                  <span className="text-[11px] font-medium text-muted-foreground flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-muted-foreground" />
                    Yüzük İçi Lazer Yazı (Opsiyonel)
                  </span>
                  <input
                    type="text"
                    maxLength={20}
                    value={b2cEngraving}
                    onChange={(e) => setB2cEngraving(e.target.value)}
                    placeholder="Örn: E & A · 24.11"
                    className="w-full h-9 px-3 text-xs rounded-[4px] border border-input bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25"
                  />
                </label>
                <div className="space-y-1.5">
                  <span className="text-[11px] font-medium text-muted-foreground flex items-center gap-1.5">
                    <Gift className="w-3.5 h-3.5 text-muted-foreground" />
                    Sunum & Hediye Kutusu
                  </span>
                  <label className="flex items-center gap-2 h-9 px-3 rounded-[4px] border border-input bg-card text-foreground cursor-pointer">
                    <input
                      type="checkbox"
                      checked={b2cGiftWrap}
                      onChange={(e) => setB2cGiftWrap(e.target.checked)}
                      className="accent-foreground"
                    />
                    <span>Kadife Kutu + Hediye Kartı</span>
                  </label>
                </div>
              </div>
              {b2cEngraving.trim().length > 0 && (
                <p className="text-[11px] text-muted-foreground">
                  Lazer yazı uygulanan ürünler kişiye özel kapsamda değerlendirilir (iade kapsamı
                  dışındadır).
                </p>
              )}
            </div>
          )}

          {role === 'b2b' && (
            <div className="rounded-lg border border-border bg-muted/70 p-3.5 space-y-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-muted-foreground" />
                  B2B Toptan Sipariş Parametreleri
                </span>
                <button
                  type="button"
                  onClick={() => setAssortmentOpen((v) => !v)}
                  className="text-[11px] font-medium text-foreground hover:text-foreground hover:underline cursor-pointer"
                >
                  {assortmentOpen
                    ? 'Tekli ölçü girişine dön'
                    : 'Çoklu ölçü asorti matrisi aç'}
                </button>
              </div>

              {!assortmentOpen ? (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  <label className="space-y-1">
                    <span className="text-[11px] text-muted-foreground">Sipariş Adedi</span>
                    <input
                      type="number"
                      min={1}
                      max={500}
                      value={b2bQty}
                      onChange={(e) => setB2bQty(Math.max(1, Number(e.target.value) || 1))}
                      className="w-full h-8 px-2.5 font-mono rounded-md border border-border bg-card text-foreground"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] text-muted-foreground">Tedarik Kaynağı</span>
                    <select
                      value={b2bSupplyType}
                      onChange={(e) => setB2bSupplyType(e.target.value as B2bSupplyType)}
                      className="w-full h-8 px-2 rounded-md border border-border bg-card text-foreground text-xs"
                    >
                      <option value="STOCK">Hazır Stoktan Ayır</option>
                      <option value="PRODUCTION">Atölye Üretim Siparişi</option>
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] text-muted-foreground">Bayi Damga / Not</span>
                    <input
                      type="text"
                      maxLength={60}
                      value={b2bStampNote}
                      onChange={(e) => setB2bStampNote(e.target.value)}
                      placeholder="Örn: 585 + Bayi Logo"
                      className="w-full h-8 px-2.5 rounded-md border border-border bg-card text-foreground"
                    />
                  </label>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-[11px] text-muted-foreground">
                    Her {sizeUnitLabel.toLocaleLowerCase('tr-TR')} için sipariş adedi girin (0 olanlar eklenmez):
                  </div>
                  <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                    {product.availableSizes.map((size) => (
                      <label
                        key={size}
                        className="flex flex-col items-center p-1.5 rounded border border-border bg-card"
                      >
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {isRing ? `No ${size}` : `${size}`}
                        </span>
                        <input
                          type="number"
                          min={0}
                          max={200}
                          value={assortmentQtyMap[size] ?? 0}
                          onChange={(e) =>
                            setAssortmentQtyMap((prev) => ({
                              ...prev,
                              [size]: Math.max(0, Number(e.target.value) || 0),
                            }))
                          }
                          className="w-12 text-center font-mono text-xs font-semibold text-foreground mt-1 border-t border-border pt-1 focus:outline-none"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border text-[11px] font-mono tabular-nums text-muted-foreground">
                <span>
                  Tahmini Fire Dahil Has:{' '}
                  <strong className="text-foreground">
                    {formatTrNumber(
                      computed.fireIncludedFineMetalGram * effectiveB2bPieces,
                      4
                    )}{' '}
                    gr
                  </strong>
                </span>
                <span>
                  Toplam ({effectiveB2bPieces} adet):{' '}
                  <strong className="text-foreground">
                    {formatCurrencyValue(
                      computed.finalB2bPriceCurrency * effectiveB2bPieces,
                      product.pricingCurrency
                    )}
                  </strong>
                </span>
              </div>
            </div>
          )}

          {/* Primary Action CTA + Favorite Toggle */}
          <div className="pt-2 space-y-2.5">
            <div className="flex items-stretch gap-2.5">
              <button
                type="button"
                onClick={handlePrimaryOrderAction}
                disabled={
                  (role === 'b2c' && product.stockStatus === 'Tükendi') ||
                  (role === 'b2b' && effectiveB2bPieces === 0)
                }
                className={`flex-1 min-h-[46px] py-3 px-5 rounded-[4px] text-sm font-medium transition-colors flex items-center justify-center gap-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  (role === 'b2c' && product.stockStatus === 'Tükendi') ||
                  (role === 'b2b' && effectiveB2bPieces === 0)
                    ? isB2c
                      ? 'bg-border text-muted-foreground cursor-not-allowed'
                      : 'bg-muted text-muted-foreground cursor-not-allowed'
                    : 'bg-primary text-primary-foreground hover:bg-primary/90'
                }`}
              >
                {role === 'b2c' ? (
                  product.stockStatus === 'Tükendi' ? (
                    'Seçili Ölçü Tükendi — Farklı Ölçü Seçiniz'
                  ) : (
                    <>
                      <ShoppingBag className="w-4 h-4" />
                      <span>
                        Sepete Ekle · {formatTrNumber(computed.discountedB2cPriceTry, 2)} TL
                      </span>
                    </>
                  )
                ) : role === 'b2b' ? (
                  <>
                    <ClipboardList className="w-4 h-4" />
                    Sipariş Fişine Ekle ({effectiveB2bPieces} Adet) ·{' '}
                    {formatCurrencyValue(
                      computed.finalB2bPriceCurrency * effectiveB2bPieces,
                      product.pricingCurrency
                    )}
                  </>
                ) : (
                  `Varyant Değişikliklerini Kaydet · ${computed.sku}`
                )}
              </button>

              {onToggleFavorite && (
                <button
                  type="button"
                  onClick={onToggleFavorite}
                  aria-label={isFavorite ? 'Favorilerden çıkar' : 'Favorilere ekle'}
                  className={`min-w-[46px] px-3.5 rounded-[4px] border transition-colors flex items-center justify-center cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    isFavorite
                      ? isB2c
                        ? 'border-foreground bg-primary/[0.06] text-foreground'
                        : 'border-destructive bg-destructive/10 text-destructive'
                      : isB2c
                        ? 'border-input bg-background text-foreground hover:border-ring hover:text-foreground'
                        : 'border-border bg-card text-muted-foreground hover:border-foreground hover:text-foreground'
                  }`}
                >
                  <Heart
                    className={`w-4 h-4 ${
                      isFavorite ? (isB2c ? 'fill-foreground' : 'fill-destructive') : ''
                    }`}
                  />
                </button>
              )}
            </div>

            {cartNotice && (
              <div
                className={`flex flex-wrap items-center justify-center gap-2 text-xs font-medium ${
                  isB2c ? 'text-success' : 'text-success'
                }`}
              >
                <span>{cartNotice}</span>
                {role === 'b2c' && onOpenB2cCart && (
                  <button
                    type="button"
                    onClick={onOpenB2cCart}
                    className="underline text-foreground font-semibold cursor-pointer"
                  >
                    Sepeti Aç
                  </button>
                )}
                {role === 'b2b' && onOpenB2bOrder && (
                  <button
                    type="button"
                    onClick={onOpenB2bOrder}
                    className="underline text-foreground font-semibold cursor-pointer"
                  >
                    Sipariş Fişini Aç
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Key Physical & Trust Metadata Strip */}
          <div
            className={`grid grid-cols-2 sm:grid-cols-4 gap-4 pt-5 border-t text-xs ${
              isB2c ? 'border-border' : 'border-border'
            }`}
          >
            <div>
              <div className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Vitrin Ağırlığı</div>
              <div
                className={`font-mono font-medium mt-0.5 tabular-nums ${
                  isB2c ? 'text-foreground' : 'text-foreground'
                }`}
              >
                {computed.displayWeightText}
              </div>
            </div>
            <div>
              <div className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Sertifika</div>
              <div
                className={`font-mono font-medium mt-0.5 ${
                  isB2c ? 'text-foreground' : 'text-foreground'
                }`}
              >
                {product.certificateAgency} · {product.certificateNumber}
              </div>
            </div>
            <div>
              <div className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Taş 4C</div>
              <div
                className={`font-medium mt-0.5 ${isB2c ? 'text-foreground' : 'text-foreground'}`}
              >
                {product.stoneColorGrade} / {product.stoneClarity} / {product.stoneCutGrade}
              </div>
            </div>
            <div>
              <div className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Mıhlama / Adet</div>
              <div
                className={`font-medium mt-0.5 ${isB2c ? 'text-foreground' : 'text-foreground'}`}
              >
                {product.settingType} · {product.stoneCount} Taş
              </div>
            </div>
          </div>

          {/* Role-Specific Internal ERP Metadata (Hidden from B2C) */}
          {role !== 'b2c' && (
            <div className="border-t border-border pt-5 space-y-2.5">
              <div className="text-xs font-semibold text-foreground">
                {role === 'erp'
                  ? 'Atölye & Has Maden Özeti'
                  : 'Bayi Has Maden & Gramaj Özeti'}
              </div>
              <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <dt className="text-muted-foreground">Net Metal Ağırlığı</dt>
                  <dd className="font-mono font-medium text-foreground tabular-nums mt-0.5">
                    {formatTrNumber(computed.netMetalGram, 3)} gr
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Has Altın Ağırlığı</dt>
                  <dd className="font-mono font-medium text-foreground tabular-nums mt-0.5">
                    {formatTrNumber(computed.fineMetalGram, 4)} gr
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Milyem (Saflık)</dt>
                  <dd className="font-mono font-medium text-foreground tabular-nums mt-0.5">
                    {formatTrNumber(computed.millesimalFineness, 3)}
                  </dd>
                </div>
                {role === 'erp' && (
                  <>
                    <div>
                      <dt className="text-muted-foreground">Tedarikçi / Atölye</dt>
                      <dd className="font-medium text-foreground mt-0.5">{product.supplierName}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Lokasyon / Kasa</dt>
                      <dd className="font-mono font-medium text-foreground mt-0.5">
                        {product.warehouseLocation}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Oluşturan</dt>
                      <dd className="font-mono text-[11px] text-foreground mt-0.5 truncate">
                        {product.createdBy}
                      </dd>
                    </div>
                  </>
                )}
              </dl>
            </div>
          )}
        </div>
      </div>

      {/* Bottom 3-Column Specification & Policy Strip (Sections 10, 11, 13) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 sm:gap-6">
        <div
          className={`border p-6 space-y-3 ${
            isB2c
              ? 'bg-card border-border rounded-[6px]'
              : 'bg-card border-border rounded-lg'
          }`}
        >
          <div
            className={`flex items-center gap-2 font-semibold text-sm ${
              isB2c ? 'text-foreground' : 'text-foreground'
            }`}
          >
            <Sparkles className={`w-4 h-4 ${isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}`} />
            Taş & {product.certificateAgency} Sertifika Detayı
          </div>
          <dl className="space-y-2 text-xs">
            <div
              className={`flex justify-between py-1.5 border-b ${
                isB2c ? 'border-border/75' : 'border-border'
              }`}
            >
              <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Taş Tipi / Menşei</dt>
              <dd className={`font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                {product.stoneType} · {product.stoneOrigin}
              </dd>
            </div>
            <div
              className={`flex justify-between py-1.5 border-b ${
                isB2c ? 'border-border/75' : 'border-border'
              }`}
            >
              <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Kesim / Şekil</dt>
              <dd className={`font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                {product.stoneCutShape} ({product.stoneCutGrade})
              </dd>
            </div>
            <div
              className={`flex justify-between py-1.5 border-b ${
                isB2c ? 'border-border/75' : 'border-border'
              }`}
            >
              <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Renk / Berraklık</dt>
              <dd className={`font-mono font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                {product.stoneColorGrade} Renk · {product.stoneClarity}
              </dd>
            </div>
            <div className="flex justify-between py-1.5">
              <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Taş Adedi / Mıhlama</dt>
              <dd className={`font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                {product.stoneCount} Adet · {product.settingType}
              </dd>
            </div>
          </dl>

          {computed.resolvedStoneLines.length > 0 && (
            <div
              className={`pt-2 border-t space-y-1.5 ${
                isB2c ? 'border-border/75' : 'border-border'
              }`}
            >
              <div className={`text-[11px] font-medium ${isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}`}>
                Taş Satırları
              </div>
              <div className="space-y-1 text-[11px]">
                {computed.resolvedStoneLines.map((st) => (
                  <div
                    key={st.id}
                    className={`flex items-center justify-between gap-2 rounded-[4px] px-2.5 py-1.5 ${
                      isB2c ? 'bg-muted' : 'bg-muted'
                    }`}
                  >
                    <span className={`font-medium ${isB2c ? 'text-muted-foreground' : 'text-foreground'}`}>
                      {st.role === 'MERKEZ'
                        ? 'Merkez'
                        : st.role === 'PAVE'
                          ? 'Pavé'
                          : st.role === 'AKSAN'
                            ? 'Aksan'
                            : 'Yan'}{' '}
                      · {st.stoneType} ({st.count} adet)
                    </span>
                    <span
                      className={`font-mono tabular-nums ${
                        isB2c ? 'text-foreground' : 'text-foreground'
                      }`}
                    >
                      {formatTrNumber(st.carat, 2)} {st.measureUnit}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div
          className={`border p-6 space-y-3 ${
            isB2c
              ? 'bg-card border-border rounded-[6px]'
              : 'bg-card border-border rounded-lg'
          }`}
        >
          <div
            className={`flex items-center gap-2 font-semibold text-sm ${
              isB2c ? 'text-foreground' : 'text-foreground'
            }`}
          >
            <Shield className={`w-4 h-4 ${isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}`} />
            Montür, Ölçü & Fiziksel Özellikler
          </div>
          <dl className="space-y-2 text-xs">
            {product.mountSpec && (
              <>
                <div
                  className={`flex justify-between py-1.5 border-b ${
                    isB2c ? 'border-border/75' : 'border-border'
                  }`}
                >
                  <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Montür Yapısı</dt>
                  <dd className={`font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                    {product.mountSpec.structure === 'HEAD_BAND'
                      ? 'İki Parça (Taç + Kol)'
                      : 'Tek Parça (Full Montür)'}
                  </dd>
                </div>
                <div
                  className={`flex justify-between py-1.5 border-b ${
                    isB2c ? 'border-border/75' : 'border-border'
                  }`}
                >
                  <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Montür Karat Aralığı</dt>
                  <dd
                    className={`font-mono font-medium tabular-nums ${
                      computed.isCaratWithinMountRange
                        ? isB2c
                          ? 'text-foreground'
                          : 'text-foreground'
                        : isB2c
                          ? 'text-muted-foreground'
                          : 'text-warning'
                    }`}
                  >
                    {formatTrNumber(product.mountSpec.allowedCaratMin, 2)}–
                    {formatTrNumber(product.mountSpec.allowedCaratMax, 2)} ct
                    {!computed.isCaratWithinMountRange ? ' (Özel Taç)' : ''}
                  </dd>
                </div>
                {role !== 'b2c' &&
                  product.mountSpec.structure === 'HEAD_BAND' &&
                  product.mountSpec.headCode && (
                    <div className="flex justify-between py-1.5 border-b border-border">
                      <dt className="text-muted-foreground">Taç / Kol Kodları</dt>
                      <dd className="font-mono text-[11px] text-foreground">
                        {product.mountSpec.headCode} · {product.mountSpec.bandCode}
                      </dd>
                    </div>
                  )}
              </>
            )}
            <div
              className={`flex justify-between py-1.5 border-b ${
                isB2c ? 'border-border/75' : 'border-border'
              }`}
            >
              <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Genişlik / Kalınlık</dt>
              <dd
                className={`font-mono font-medium tabular-nums ${
                  isB2c ? 'text-foreground' : 'text-foreground'
                }`}
              >
                {formatTrNumber(product.widthMm, 1)} mm · {formatTrNumber(product.thicknessMm, 1)}{' '}
                mm
              </dd>
            </div>
            <div
              className={`flex justify-between py-1.5 border-b ${
                isB2c ? 'border-border/75' : 'border-border'
              }`}
            >
              <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Taç Yüksekliği</dt>
              <dd
                className={`font-mono font-medium tabular-nums ${
                  isB2c ? 'text-foreground' : 'text-foreground'
                }`}
              >
                {formatTrNumber(product.heightMm, 1)} mm
              </dd>
            </div>
            <div className="flex justify-between py-1.5">
              <dt className={isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}>Stil / Özel Gün</dt>
              <dd className={`font-medium ${isB2c ? 'text-foreground' : 'text-foreground'}`}>
                {product.styleTechnique} · {product.occasion}
              </dd>
            </div>
          </dl>
        </div>

        <div
          className={`border p-6 space-y-3 ${
            isB2c
              ? 'bg-card border-border rounded-[6px]'
              : 'bg-card border-border rounded-lg'
          }`}
        >
          <div
            className={`flex items-center gap-2 font-semibold text-sm ${
              isB2c ? 'text-foreground' : 'text-foreground'
            }`}
          >
            <Truck className={`w-4 h-4 ${isB2c ? 'text-muted-foreground' : 'text-muted-foreground'}`} />
            Garanti, Sigortalı Kargo & İade
          </div>
          <div
            className={`space-y-2.5 text-xs leading-relaxed ${
              isB2c ? 'text-muted-foreground' : 'text-muted-foreground'
            }`}
          >
            <div className="flex items-start gap-2">
              <RefreshCw
                className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                  isB2c ? 'text-muted-foreground' : 'text-muted-foreground'
                }`}
              />
              <span>
                <strong className={isB2c ? 'text-foreground' : 'text-foreground'}>
                  {product.warrantyMonths} Ay Garanti
                </strong>{' '}
                ve ömür boyu ücretsiz bakım, cila ve rodaj hizmeti.
              </span>
            </div>
            <p>
              <strong className={isB2c ? 'text-foreground' : 'text-foreground'}>
                Sigortalı Kargo:
              </strong>{' '}
              {product.insuredShippingInfo}.
            </p>
            <p>{product.returnPolicyText}</p>
          </div>
        </div>
      </div>

      {/* Related Designs Section */}
      {relatedProducts.length > 0 && onSelectRelatedProduct && (
        <section
          className={`space-y-5 pt-6 border-t ${isB2c ? 'border-border' : 'border-border'}`}
        >
          <div className="flex items-baseline justify-between gap-4">
            <h2
              className={
                isB2c
                  ? 'font-serif text-2xl sm:text-3xl font-normal text-foreground'
                  : 'text-page-title text-2xl font-semibold text-foreground'
              }
            >
              Benzer Tasarımlar
            </h2>
            <button
              type="button"
              onClick={onBackToVitrin}
              className={`text-xs font-medium underline underline-offset-4 cursor-pointer ${
                isB2c
                  ? 'text-muted-foreground hover:text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Tüm Koleksiyonu Gör
            </button>
          </div>

          {isB2c ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {relatedProducts.map((rel) => {
                const relMetrics = computeJewelryMetrics(rel, rates);
                const relMedia = resolveProductMedia(
                  rel.parentSku,
                  rel.metalColor,
                  rel.galleryImages
                );
                return (
                  <StorefrontProductCard
                    key={rel.parentSku}
                    product={rel}
                    metrics={relMetrics}
                    media={relMedia}
                    showQuickAdd={false}
                    onOpen={() => onSelectRelatedProduct(rel.parentSku)}
                  />
                );
              })}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {relatedProducts.map((rel) => {
                const relMetrics = computeJewelryMetrics(rel, rates);
                const relMedia = resolveProductMedia(
                  rel.parentSku,
                  rel.metalColor,
                  rel.galleryImages
                );
                return (
                  <article
                    key={rel.parentSku}
                    onClick={() => onSelectRelatedProduct(rel.parentSku)}
                    className="bg-card border border-border hover:border-border rounded-lg overflow-hidden transition-all cursor-pointer group"
                  >
                    <div className="aspect-[4/3] bg-muted overflow-hidden">
                      <img
                        src={relMedia.mainUrl}
                        alt={rel.title}
                        referrerPolicy="no-referrer"
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                      />
                    </div>
                    <div className="p-4 space-y-1">
                      <div className="text-[11px] text-muted-foreground">
                        {rel.subCategory} · {rel.certificateAgency}
                      </div>
                      <div className="text-base font-semibold text-foreground group-hover:text-foreground transition-colors leading-snug">
                        {rel.title}
                      </div>
                      <div className="font-mono text-sm font-semibold text-foreground tabular-nums pt-1">
                        {role === 'b2b'
                          ? formatCurrencyValue(
                              relMetrics.finalB2bPriceCurrency,
                              rel.pricingCurrency
                            )
                          : `${formatTrNumber(relMetrics.discountedB2cPriceTry, 0)} TL`}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Mobile Sticky Bottom Purchase Bar (B2C Only) */}
      {isB2c && computed.ledger.hasB2cChannel && (
        <div className="md:hidden fixed inset-x-0 bottom-0 z-30 bg-background/95 backdrop-blur-md border-t border-border px-4 pt-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom))] flex items-center justify-between gap-3">
          <div className="min-w-0 tabular-nums">
            <div className="text-[11px] text-muted-foreground truncate">
              {product.purityCode} {product.metalColor} · {sizeUnitLabel} {product.variantSize}
            </div>
            <div className="font-mono text-base font-semibold text-foreground whitespace-nowrap">
              {formatTrNumber(computed.discountedB2cPriceTry, 0)} TL
            </div>
          </div>

          <button
            type="button"
            disabled={product.stockStatus === 'Tükendi'}
            onClick={handlePrimaryOrderAction}
            className="min-h-[44px] px-4 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-40 inline-flex items-center gap-1.5 whitespace-nowrap shrink-0 cursor-pointer"
          >
            <ShoppingBag className="w-4 h-4" />
            <span>{product.stockStatus === 'Tükendi' ? 'Tükendi' : 'Sepete Ekle'}</span>
          </button>
        </div>
      )}

      <SizeGuideDialog
        open={sizeGuideOpen}
        onOpenChange={setSizeGuideOpen}
        category={product.category}
      />
    </div>
  );
}

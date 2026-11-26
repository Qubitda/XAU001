import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronRight } from 'lucide-react';
import featuredRingImg from '../../../assets/images/se009_white_main_1795533192415.jpg';
import type { ComputedJewelryMetrics, MetalColor } from '../../../types/jewelry';
import type { ProductState } from '../../catalog/types';
import type { ResolvedProductMedia } from '../../../data/productMedia';
import { JewelryIllustration } from '../../../components/JewelryIllustration';
import { formatTrNumber } from '../../../utils/pricingEngine';
import { StorefrontProductCard } from './StorefrontUI';

export interface ComputedStorefrontProduct {
  product: ProductState;
  metrics: ComputedJewelryMetrics;
  media: ResolvedProductMedia;
}

type ShowcaseFilter = 'featured' | 'new_collection' | 'discounted';

interface FeaturedAndNewSectionProps {
  items: ComputedStorefrontProduct[];
  isLoading: boolean;
  favoriteSkus: string[];
  addedSku: string | null;
  onOpenProduct: (parentSku: string) => void;
  onToggleFavorite: (parentSku: string) => void;
  onQuickAdd: (entry: ComputedStorefrontProduct) => void;
}

export function FeaturedAndNewSection({
  items,
  isLoading,
  favoriteSkus,
  addedSku,
  onOpenProduct,
  onToggleFavorite,
  onQuickAdd,
}: FeaturedAndNewSectionProps) {
  const [activeTab, setActiveTab] = useState<ShowcaseFilter>('featured');
  const [carouselOffset, setCarouselOffset] = useState(0);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});
  const [previewColors, setPreviewColors] = useState<Record<string, MetalColor>>({});

  const newArrivals = useMemo(() => {
    const onlyNew = items.filter((entry) => entry.product.collection === 'Yeni Koleksiyon');
    return onlyNew.length > 0 ? onlyNew : items;
  }, [items]);

  const discountedItems = useMemo(
    () => items.filter((entry) => entry.metrics.discountAmountTry > 0),
    [items]
  );

  const visibleNewPreview = useMemo(() => {
    if (newArrivals.length === 0) return [];
    const count = Math.min(3, newArrivals.length);
    return Array.from({ length: count }, (_, idx) => {
      return newArrivals[(carouselOffset + idx) % newArrivals.length];
    });
  }, [newArrivals, carouselOffset]);

  const showcaseItems = useMemo(() => {
    if (activeTab === 'new_collection') return newArrivals.slice(0, 8);
    if (activeTab === 'discounted') return discountedItems.slice(0, 8);
    return items.slice(0, 8);
  }, [activeTab, items, newArrivals, discountedItems]);

  const featuredBannerImage = useMemo(() => {
    const firstRing = items.find((entry) => {
      const c = entry.product.category;
      return c === 'YUZUK' || c.toLocaleLowerCase('tr-TR') === 'yüzük';
    });
    return firstRing?.media.mainUrl || featuredRingImg;
  }, [items]);

  const handleNextNewPreview = () => {
    if (newArrivals.length <= 1) return;
    setCarouselOffset((prev) => (prev + 1) % newArrivals.length);
  };

  return (
    <div className="space-y-12 sm:space-y-16">
      {/* Dual Editorial Row: Featured Collection Left | New Arrivals Preview Right */}
      <section
        aria-label="Öne çıkan koleksiyon ve yeni gelenler"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-5 items-stretch">
          {/* Left Card: Öne Çıkan Koleksiyon (Timeless Collection) */}
          <div className="lg:col-span-6 relative rounded-[6px] overflow-hidden bg-muted border border-border min-h-[210px] sm:min-h-[230px] flex items-center">
            <img
              src={featuredBannerImage}
              alt="TARA DIAMOND Timeless Collection öne çıkan pırlanta yüzük"
              loading="lazy"
              decoding="async"
              referrerPolicy="no-referrer"
              className="absolute inset-0 w-full h-full object-cover object-right opacity-95"
            />
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-gradient-to-r from-background via-background/90 to-background/15"
            />

            <div className="relative z-10 p-6 sm:p-8 max-w-[68%] sm:max-w-[60%] space-y-2.5">
              <p className="text-xs font-medium text-muted-foreground">Öne Çıkan Koleksiyon</p>
              <h2 className="font-serif text-[28px] sm:text-[34px] font-normal text-foreground leading-[1.08]">
                Timeless Collection
              </h2>
              <p className="text-xs sm:text-[13px] text-muted-foreground leading-relaxed">
                Zamansız tasarımlarla, daima şık.
              </p>
              <div className="pt-2">
                <Link
                  to="/koleksiyon"
                  className="inline-flex items-center gap-1.5 text-xs sm:text-[13px] font-medium text-foreground border-b border-foreground/70 pb-0.5 hover:text-foreground hover:border-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm transition-colors"
                >
                  <span>Koleksiyonu İncele</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          </div>

          {/* Right Card: Yeni Gelenler Preview Strip */}
          <div className="lg:col-span-6 rounded-[6px] bg-muted border border-border p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-5">
            <div className="space-y-2 sm:max-w-[190px] shrink-0">
              <h2 className="font-serif text-[26px] sm:text-[28px] font-normal text-foreground leading-tight">
                Yeni Gelenler
              </h2>
              <p className="text-xs sm:text-[13px] text-muted-foreground leading-relaxed">
                En yeni tasarımlarımızı keşfedin.
              </p>
              <div className="pt-2">
                <Link
                  to="/koleksiyon?filter=new_collection"
                  className="inline-flex items-center gap-1.5 text-xs sm:text-[13px] font-medium text-foreground border-b border-foreground/70 pb-0.5 hover:text-foreground hover:border-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm transition-colors"
                >
                  <span>Tümünü Gör</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>

            {/* Interactive Live Product Thumbnails */}
            <div className="relative flex-1 min-w-0 flex items-center gap-2.5 sm:gap-3">
              {visibleNewPreview.length === 0 ? (
                <div className="w-full py-6 text-center text-xs text-muted-foreground border border-dashed border-border rounded-[4px]">
                  Yeni sezon ürünleri hazırlanıyor.
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-2.5 sm:gap-3 flex-1 min-w-0">
                    {visibleNewPreview.map(({ product, metrics, media }) => {
                      const imgFailed = failedImages[`preview-${media.mainUrl}`];
                      return (
                        <button
                          key={product.parentSku}
                          type="button"
                          onClick={() => onOpenProduct(product.parentSku)}
                          title={`${product.title} — ${formatTrNumber(metrics.discountedB2cPriceTry, 0)} TL`}
                          className="group relative aspect-square rounded-[4px] overflow-hidden bg-card border border-border hover:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
                        >
                          {imgFailed ? (
                            <div className="w-full h-full flex items-center justify-center p-2">
                              <JewelryIllustration
                                visualType={product.visualType}
                                metalColor={product.metalColor}
                                stoneType={product.stoneType}
                                centerStoneCarat={product.centerStoneCarat}
                                sideStoneCarat={product.sideStoneCarat}
                                className="w-full h-full"
                              />
                            </div>
                          ) : (
                            <img
                              src={media.mainUrl}
                              alt={product.title}
                              loading="lazy"
                              decoding="async"
                              referrerPolicy="no-referrer"
                              onError={() =>
                                setFailedImages((prev) => ({
                                  ...prev,
                                  [`preview-${media.mainUrl}`]: true,
                                }))
                              }
                              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>

                  {newArrivals.length > 3 && (
                    <button
                      type="button"
                      onClick={handleNextNewPreview}
                      aria-label="Sonraki yeni tasarımları göster"
                      className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-white border border-border text-foreground hover:border-ring hover:text-foreground flex items-center justify-center shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Live API Product Showcase Section */}
      <section
        aria-label="Seçkin ürünler"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6 sm:space-y-8"
      >
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-border pb-4">
          <div className="space-y-1">
            <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground font-medium">
              Sertifikalı Koleksiyon
            </p>
            <h2 className="font-serif text-2xl sm:text-3xl font-normal text-foreground">
              Seçkin Tasarımlar
            </h2>
          </div>

          <div
            role="tablist"
            aria-label="Ürün filtreleri"
            className="flex items-center gap-5 sm:gap-7 overflow-x-auto no-scrollbar"
          >
            {(
              [
                { id: 'featured', label: 'Öne Çıkanlar', count: items.length },
                { id: 'new_collection', label: 'Yeni Gelenler', count: newArrivals.length },
                { id: 'discounted', label: 'Kampanyalar', count: discountedItems.length },
              ] as const
            ).map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative pb-2 text-xs sm:text-[13px] font-medium whitespace-nowrap shrink-0 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm ${
                    active
                      ? 'text-foreground after:absolute after:inset-x-0 after:bottom-0 after:h-[1.5px] after:bg-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab.label}
                  {tab.count > 0 && (
                    <span className="ml-1.5 font-mono text-[11px] text-muted-foreground tabular-nums">
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Loading State */}
        {isLoading && items.length === 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="rounded-[6px] border border-border bg-card overflow-hidden animate-pulse"
              >
                <div className="aspect-[4/3] bg-muted" />
                <div className="p-4 space-y-2.5">
                  <div className="h-3 w-24 bg-border rounded" />
                  <div className="h-5 w-4/5 bg-border rounded" />
                  <div className="h-4 w-1/2 bg-border rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : showcaseItems.length === 0 ? (
          /* Authentic Empty State (No fabricated products) */
          <div className="rounded-[6px] border border-border bg-card py-12 px-6 text-center space-y-3">
            <p className="font-serif text-xl text-foreground">
              {activeTab === 'discounted'
                ? 'Şu anda aktif kampanyalı ürün bulunmuyor.'
                : 'Bu kategoride henüz listelenmiş ürün bulunmuyor.'}
            </p>
            <p className="text-xs text-muted-foreground max-w-md mx-auto">
              Tüm sertifikalı koleksiyonu incelemek veya diğer kategorilere göz atmak için
              koleksiyon sayfasına geçebilirsiniz.
            </p>
            <div className="pt-1">
              <Link
                to="/koleksiyon"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[4px] bg-primary text-primary-foreground text-xs font-medium hover:bg-primary transition-colors"
              >
                <span>Koleksiyonu Görüntüle</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        ) : (
          /* Real Catalog Product Cards */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {showcaseItems.map((entry) => {
              const activeColor =
                previewColors[entry.product.parentSku] ?? entry.product.metalColor;
              return (
                <StorefrontProductCard
                  key={entry.product.parentSku}
                  product={entry.product}
                  metrics={entry.metrics}
                  media={entry.media}
                  activeColor={activeColor}
                  showColorSwatches={true}
                  isFavorite={favoriteSkus.includes(entry.product.parentSku)}
                  isAdded={addedSku === entry.product.parentSku}
                  onOpen={() => onOpenProduct(entry.product.parentSku)}
                  onSelectColor={(color) =>
                    setPreviewColors((prev) => ({
                      ...prev,
                      [entry.product.parentSku]: color,
                    }))
                  }
                  onToggleFavorite={() => onToggleFavorite(entry.product.parentSku)}
                  onQuickAdd={() => onQuickAdd(entry)}
                />
              );
            })}
          </div>
        )}

        {/* Footer CTA link to Full Collection */}
        {items.length > 0 && (
          <div className="flex justify-center pt-1">
            <Link
              to="/koleksiyon"
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-[4px] border border-border bg-card text-xs font-medium text-foreground hover:border-ring hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
            >
              <span>Tüm Koleksiyonu Keşfet ({items.length} tasarım)</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}

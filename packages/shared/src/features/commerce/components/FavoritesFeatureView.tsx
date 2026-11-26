import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  ClipboardList,
  Copy,
  Heart,
  Trash2,
} from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '../../../components/portal';
import { Badge, Button } from '../../../components/ui';
import { useAuth } from '../../../providers/AuthProvider';
import {
  useActiveProductMetrics,
  usePortalSelection,
} from '../../catalog/hooks/useCatalogQueries';
import {
  computeJewelryMetrics,
  formatCurrencyValue,
  formatTrNumber,
} from '../../../utils/pricingEngine';
import { resolveProductMedia } from '../../../data/productMedia';
import {
  useAddToB2bDraftMutation,
  useAddToB2cCartMutation,
  useFavoritesQuery,
  useToggleFavoriteMutation,
} from '../hooks/useCommerceQueries';
import {
  buildB2bOrderLineFromProduct,
  buildB2cCartItemFromProduct,
} from '../services/commerceService';
import {
  StorefrontEmptyState,
  StorefrontPageHeader,
  StorefrontProductCard,
  TARA_PRIMARY_BTN_CLASS,
  TARA_SECONDARY_BTN_CLASS,
} from '../../storefront/components/StorefrontUI';

interface FavoritesFeatureViewProps {
  portalMode?: 'b2c' | 'b2b';
}

export function FavoritesFeatureView({ portalMode }: FavoritesFeatureViewProps = {}) {
  const navigate = useNavigate();
  const { role } = useAuth();
  const effectiveRole = portalMode === 'b2b' ? 'b2b' : portalMode === 'b2c' ? 'b2c' : role;
  const catalogRoute = portalMode === 'b2b' ? '/b2b/katalog' : '/koleksiyon';
  const productRoutePrefix = portalMode === 'b2b' ? '/b2b/urun' : '/urun';
  const { products, rates } = useActiveProductMetrics();
  const { setSelectedParentSku } = usePortalSelection();
  const favoritesQuery = useFavoritesQuery();
  const toggleFavorite = useToggleFavoriteMutation();
  const addB2c = useAddToB2cCartMutation();
  const addB2b = useAddToB2bDraftMutation();

  const [addedKey, setAddedKey] = useState<string | null>(null);
  const [copiedPresentation, setCopiedPresentation] = useState(false);

  const favoriteSkus = favoritesQuery.data ?? [];

  const favoriteItems = useMemo(() => {
    return favoriteSkus
      .map((sku) => products.find((p) => p.parentSku === sku))
      .filter((p): p is NonNullable<typeof p> => Boolean(p))
      .map((product) => ({
        product,
        metrics: computeJewelryMetrics(product, rates),
        media: resolveProductMedia(
          product.parentSku,
          product.metalColor,
          product.galleryImages
        ),
      }));
  }, [favoriteSkus, products, rates]);

  const flashAdded = (key: string) => {
    setAddedKey(key);
    window.setTimeout(() => setAddedKey((cur) => (cur === key ? null : cur)), 1500);
  };

  const handleCopyB2bSelection = async () => {
    const text = [
      'Özel Seçki — Sertifikalı Mücevher Sunumu',
      '----------------------------------------',
      ...favoriteItems.map(
        ({ product, metrics }, idx) =>
          `${idx + 1}. ${product.title} (${product.purityCode} ${product.metalColor} Altın · ${formatTrNumber(metrics.totalStoneCarat, 2)} ct ${product.stoneColorGrade}/${product.stoneClarity}) — ${formatTrNumber(metrics.discountedB2cPriceTry, 0)} TL`
      ),
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopiedPresentation(true);
      window.setTimeout(() => setCopiedPresentation(false), 2000);
    } catch {
      setCopiedPresentation(false);
    }
  };

  // B2C Storefront — TARA DIAMOND Design System
  if (effectiveRole === 'b2c') {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
        <StorefrontPageHeader
          eyebrow="Kişisel Seçki"
          title={`Favorilerim (${favoriteItems.length})`}
          subtitle="Kaydettiğiniz tasarımları güncel altın fiyatlarıyla takip edin, dilediğiniz an sepetinize ekleyin."
          breadcrumb={[
            { label: 'Ana Sayfa', to: '/' },
            { label: 'Favorilerim' },
          ]}
          actions={
            <button
              type="button"
              onClick={() => navigate(catalogRoute)}
              className={TARA_SECONDARY_BTN_CLASS}
            >
              <span>Koleksiyona Dön</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          }
        />

        {favoriteItems.length === 0 ? (
          <StorefrontEmptyState
            icon={<Heart className="w-8 h-8" />}
            title="Henüz favori parçanız bulunmuyor"
            description="Koleksiyondaki tasarımların üzerindeki kalp ikonuna tıklayarak kendi özel seçkinizi oluşturabilirsiniz."
            action={
              <button
                type="button"
                onClick={() => navigate(catalogRoute)}
                className={TARA_PRIMARY_BTN_CLASS}
              >
                <span>Koleksiyonu Keşfet</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            }
          />
        ) : (
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {favoriteItems.map(({ product, metrics, media }) => (
              <StorefrontProductCard
                key={product.parentSku}
                product={product}
                metrics={metrics}
                media={media}
                isFavorite={true}
                isAdded={addedKey === product.parentSku}
                onOpen={() => {
                  setSelectedParentSku(product.parentSku);
                  navigate(`${productRoutePrefix}/${encodeURIComponent(product.parentSku)}`);
                }}
                onToggleFavorite={() => toggleFavorite.mutate(product.parentSku)}
                onQuickAdd={() => {
                  addB2c.mutate(
                    buildB2cCartItemFromProduct({
                      product,
                      computed: metrics,
                      rates,
                      qty: 1,
                    })
                  );
                  flashAdded(product.parentSku);
                }}
              />
            ))}
          </section>
        )}
      </div>
    );
  }

  const isB2bPortal = portalMode === 'b2b';
  const headerActions = (
    <>
      {favoriteItems.length > 0 && (
        <Button variant="outline" size="sm" onClick={handleCopyB2bSelection}>
          {copiedPresentation ? (
            <>
              <Check className="w-3.5 h-3.5 text-success" />
              Sunum Metni Kopyalandı
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              Müşteri Sunumu Kopyala
            </>
          )}
        </Button>
      )}
      <Button variant="outline" size="sm" onClick={() => navigate(catalogRoute)}>
        {isB2bPortal ? 'Toptan Kataloğa Dön' : 'Koleksiyona Dön'}
        <ArrowRight className="w-3.5 h-3.5" />
      </Button>
    </>
  );

  return (
    <div
      className={
        isB2bPortal
          ? 'space-y-6'
          : 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8'
      }
    >
      {isB2bPortal ? (
        <PortalPageHeader
          eyebrow="Bayi Seçkisi · Müşteri Sunum Listesi"
          title={`Favorilerim (${favoriteItems.length})`}
          description="Beğendiğiniz tasarımları güncel kur ve altın fiyatlarıyla takip edin, tek tıkla sipariş fişine aktarın."
          actions={headerActions}
        />
      ) : (
        <section className="border-b border-zinc-200 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div className="space-y-1.5">
            <p className="text-xs text-zinc-500">Bayi Seçkisi · Müşteri Sunum Listesi</p>
            <h1 className="text-page-title">Favorilerim ({favoriteItems.length})</h1>
            <p className="text-sm text-zinc-600">
              Beğendiğiniz tasarımları güncel kur ve altın fiyatlarıyla takip edin, tek tıkla
              sipariş fişine aktarın.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">{headerActions}</div>
        </section>
      )}

      {favoriteItems.length === 0 ? (
        isB2bPortal ? (
          <PortalDataCard contentClassName="py-16 px-6 text-center space-y-3">
            <Heart className="w-9 h-9 text-muted-foreground/40 mx-auto" />
            <div className="text-base font-semibold text-foreground">
              Henüz favori parçanız bulunmuyor
            </div>
            <p className="text-xs text-muted-foreground max-w-md mx-auto">
              Katalogdaki tasarımların üzerindeki kalp ikonuna tıklayarak kendi seçkinizi
              oluşturabilirsiniz.
            </p>
            <div className="pt-2">
              <Button size="sm" onClick={() => navigate(catalogRoute)}>
                Kataloğu Keşfet
              </Button>
            </div>
          </PortalDataCard>
        ) : (
          <div className="bg-white border border-zinc-200 rounded-lg py-16 px-6 text-center space-y-3">
            <Heart className="w-9 h-9 text-zinc-300 mx-auto" />
            <div className="text-section text-foreground">Henüz favori parçanız bulunmuyor</div>
            <p className="text-xs text-zinc-500 max-w-md mx-auto">
              Koleksiyondaki tasarımların üzerindeki kalp ikonuna tıklayarak kendi seçkinizi
              oluşturabilirsiniz.
            </p>
            <div className="pt-2">
              <Button onClick={() => navigate(catalogRoute)}>Koleksiyonu Keşfet</Button>
            </div>
          </div>
        )
      ) : (
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {favoriteItems.map(({ product, metrics, media }) => {
            const cardInner = (
              <>
                <div>
                  <div
                    onClick={() => {
                      setSelectedParentSku(product.parentSku);
                      navigate(`${productRoutePrefix}/${encodeURIComponent(product.parentSku)}`);
                    }}
                    className={`relative aspect-[4/3] overflow-hidden cursor-pointer group ${
                      isB2bPortal ? 'bg-muted' : 'bg-muted'
                    }`}
                  >
                    <img
                      src={media.mainUrl}
                      alt={product.title}
                      referrerPolicy="no-referrer"
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                    />
                    <button
                      type="button"
                      aria-label="Favorilerden çıkar"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleFavorite.mutate(product.parentSku);
                      }}
                      className="absolute top-3 right-3 w-8 h-8 rounded-full border border-border bg-background/95 text-destructive hover:bg-background flex items-center justify-center transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="p-5 space-y-2">
                    <div
                      className="flex items-center justify-between text-[11px] text-muted-foreground"
                    >
                      <span>
                        {product.subCategory} · {product.certificateAgency}
                      </span>
                      {isB2bPortal ? (
                        <Badge
                          variant="outline"
                          className={
                            product.stockStatus === 'Stokta'
                              ? 'text-success border-success/30'
                              : 'text-warning border-warning/30'
                          }
                        >
                          {product.stockStatus}
                        </Badge>
                      ) : (
                        <span
                          className={
                            product.stockStatus === 'Stokta'
                              ? 'text-success font-medium'
                              : 'text-warning font-medium'
                          }
                        >
                          {product.stockStatus}
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedParentSku(product.parentSku);
                        navigate(`${productRoutePrefix}/${encodeURIComponent(product.parentSku)}`);
                      }}
                      className={`text-lg font-semibold text-left leading-snug cursor-pointer transition-colors ${
                        isB2bPortal
                          ? 'text-foreground hover:text-muted-foreground'
                          : 'text-foreground hover:text-zinc-700'
                      }`}
                    >
                      {product.title}
                    </button>

                    <p
                      className={`text-xs tabular-nums ${
                        isB2bPortal ? 'text-muted-foreground' : 'text-zinc-500'
                      }`}
                    >
                      {product.purityCode} {product.metalColor} Altın ·{' '}
                      {formatTrNumber(metrics.totalStoneCarat, 2)} ct · {product.stoneColorGrade}/
                      {product.stoneClarity}
                    </p>
                  </div>
                </div>

                <div
                  className={`px-5 pb-5 pt-3 border-t space-y-3 ${
                    isB2bPortal ? 'border-border' : 'border-zinc-100'
                  }`}
                >
                  <div className="flex items-baseline justify-between">
                    <span
                      className={`text-xs ${isB2bPortal ? 'text-muted-foreground' : 'text-zinc-500'}`}
                    >
                      B2B Toptan
                    </span>
                    <span
                      className={`font-mono text-base font-semibold tabular-nums ${
                        isB2bPortal ? 'text-foreground' : 'text-foreground'
                      }`}
                    >
                      {formatCurrencyValue(metrics.finalB2bPriceCurrency, product.pricingCurrency)}
                    </span>
                  </div>

                  <Button
                    className="w-full"
                    size="sm"
                    onClick={() => {
                      addB2b.mutate(
                        buildB2bOrderLineFromProduct({
                          product,
                          computed: metrics,
                          rates,
                          qty: 1,
                        })
                      );
                      flashAdded(product.parentSku);
                    }}
                  >
                    {addedKey === product.parentSku ? (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        Sipariş Fişine Eklendi
                      </>
                    ) : (
                      <>
                        <ClipboardList className="w-3.5 h-3.5" />
                        Sipariş Fişine Ekle
                      </>
                    )}
                  </Button>
                </div>
              </>
            );

            return isB2bPortal ? (
              <PortalDataCard
                key={product.parentSku}
                contentClassName="p-0 overflow-hidden flex flex-col justify-between"
              >
                {cardInner}
              </PortalDataCard>
            ) : (
              <article
                key={product.parentSku}
                className="bg-white border border-zinc-200 rounded-lg overflow-hidden flex flex-col justify-between hover:border-ring transition-colors"
              >
                {cardInner}
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}

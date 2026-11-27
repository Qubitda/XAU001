import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Diamond,
  Loader2,
  Lock,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../../../providers/AuthProvider';
import { resolveProductMedia } from '../../../data/productMedia';
import { JewelryIllustration } from '../../../components/JewelryIllustration';
import {
  useCatalogQuery,
  useLiveRatesQuery,
} from '../../catalog/hooks/useCatalogQueries';
import { useCommerceUI } from '../../commerce/hooks/useCommerceQueries';
import {
  StorefrontBreadcrumb,
  StorefrontEmptyState,
  TARA_PRIMARY_BTN_CLASS,
  TARA_SECONDARY_BTN_CLASS,
} from '../../storefront/components/StorefrontUI';
import { formatCurrencyValue, formatTrNumber, resolveProductKind } from '../../../utils/pricingEngine';
import type { ProductState } from '../../../types/jewelry';
import { ApiClientError } from '../../../lib/api/client';
import {
  useCompatibleStonesQuery,
  useCreateDyoBundleMutation,
  useDyoValidateMutation,
} from '../hooks/useDyoQueries';
import type { DyoCompatibleStoneItem, DyoPricingDto } from '../types';
import { cn } from '../../../lib/utils';

type WizardStep = 1 | 2 | 3;
export type DyoPortalMode = 'b2c' | 'b2b';

const STEPS: { id: WizardStep; label: string }[] = [
  { id: 1, label: 'Montür seç' },
  { id: 2, label: 'Taş seç' },
  { id: 3, label: 'Özet & sepet' },
];

interface DyoWizardFeatureViewProps {
  portalMode?: DyoPortalMode;
}

function mountingLabel(product: ProductState): string {
  const detail = product.mountingDetail;
  const shapes = detail?.compatibleShapes?.length
    ? detail.compatibleShapes.join(', ')
    : 'Şekil tanımsız';
  const min = detail?.minCarat ?? product.mountSpec?.allowedCaratMin;
  const max = detail?.maxCarat ?? product.mountSpec?.allowedCaratMax;
  const range =
    min != null && max != null ? `${formatTrNumber(min, 2)}–${formatTrNumber(max, 2)} ct` : 'Karat aralığı yok';
  return `${shapes} · ${range}`;
}

function stoneLabel(stone: DyoCompatibleStoneItem): string {
  const d = stone.looseStoneDetail;
  if (!d) return stone.title;
  const parts = [
    d.shape,
    `${formatTrNumber(d.carat, 3)} ct`,
    [d.color, d.clarity].filter(Boolean).join('/'),
  ].filter(Boolean);
  return parts.join(' · ');
}

function ProductThumb({ product }: { product: ProductState }) {
  const media = resolveProductMedia(product.parentSku, product.metalColor, product.galleryImages);
  const [failed, setFailed] = useState(false);
  return (
    <div className="w-full aspect-square rounded-[4px] border border-border bg-muted overflow-hidden flex items-center justify-center">
      {media.mainUrl && !failed ? (
        <img
          src={media.mainUrl}
          alt={product.title}
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="w-full h-full object-cover"
          style={media.toneFilter ? { filter: media.toneFilter } : undefined}
        />
      ) : (
        <JewelryIllustration
          visualType={product.visualType || 'solitaire_ring'}
          metalColor={product.metalColor}
          stoneType={product.stoneType || 'Pırlanta'}
          centerStoneCarat={product.centerStoneCarat || 0.5}
          sideStoneCarat={product.sideStoneCarat || 0}
          className="w-20 h-20"
        />
      )}
    </div>
  );
}

export function DyoWizardFeatureView({ portalMode = 'b2c' }: DyoWizardFeatureViewProps = {}) {
  const navigate = useNavigate();
  const { mountingSku: routeMountSku } = useParams<{ mountingSku?: string }>();
  const [searchParams] = useSearchParams();
  const initialMount = routeMountSku || searchParams.get('mountingSku') || '';

  const { authenticated, setAuthModalOpen } = useAuth();
  const { setB2cCartOpen, setB2bOrderOpen } = useCommerceUI();
  const catalogQuery = useCatalogQuery();
  const ratesQuery = useLiveRatesQuery();
  const isB2b = portalMode === 'b2b';
  const audience = isB2b ? 'b2b' : 'b2c';
  const designBase = isB2b ? '/b2b/tasarla' : '/tasarla';
  const catalogPath = isB2b ? '/b2b/katalog' : '/koleksiyon';
  const homePath = isB2b ? '/b2b/panel' : '/';
  const homeLabel = isB2b ? 'Bayi Paneli' : 'Ana Sayfa';
  const catalogLabel = isB2b ? 'Toptan Katalog' : 'Koleksiyon';

  const [step, setStep] = useState<WizardStep>(initialMount ? 2 : 1);
  const [selectedMountSku, setSelectedMountSku] = useState(initialMount);
  const [selectedStoneSku, setSelectedStoneSku] = useState('');
  const [colorFilter, setColorFilter] = useState('');
  const [clarityFilter, setClarityFilter] = useState('');
  const [pricing, setPricing] = useState<DyoPricingDto | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const mountings = useMemo(
    () => (catalogQuery.data ?? []).filter((p) => resolveProductKind(p) === 'MOUNTING'),
    [catalogQuery.data]
  );

  const selectedMount = useMemo(
    () => mountings.find((m) => m.parentSku === selectedMountSku) ?? null,
    [mountings, selectedMountSku]
  );

  const stonesQuery = useCompatibleStonesQuery(
    selectedMountSku && authenticated
      ? {
          mountingSku: selectedMountSku,
          color: colorFilter || undefined,
          clarity: clarityFilter || undefined,
          limit: 100,
        }
      : null,
    audience
  );

  const validateMutation = useDyoValidateMutation(audience);
  const createBundleMutation = useCreateDyoBundleMutation(audience);

  useEffect(() => {
    if (initialMount && mountings.some((m) => m.parentSku === initialMount)) {
      setSelectedMountSku(initialMount);
      setStep(2);
    }
  }, [initialMount, mountings]);

  useEffect(() => {
    setSelectedStoneSku('');
    setPricing(null);
    setLocalError(null);
  }, [selectedMountSku]);

  const requireAuth = () => {
    if (authenticated) return true;
    setAuthModalOpen(true);
    setLocalError('DYO için giriş yapmanız gerekir.');
    return false;
  };

  const goToStones = (sku: string) => {
    setSelectedMountSku(sku);
    setStep(2);
    navigate(`${designBase}/${encodeURIComponent(sku)}`, { replace: true });
  };

  const handleSelectStone = async (stoneSku: string) => {
    if (!requireAuth() || !selectedMountSku) return;
    setSelectedStoneSku(stoneSku);
    setLocalError(null);
    try {
      const result = await validateMutation.mutateAsync({
        mountingSku: selectedMountSku,
        stoneSku,
      });
      setPricing(result.pricing);
      setStep(3);
    } catch (err) {
      setPricing(null);
      setLocalError(err instanceof ApiClientError ? err.message : 'Uyumluluk doğrulanamadı');
    }
  };

  const handleAddToCart = async () => {
    if (!requireAuth() || !selectedMountSku || !selectedStoneSku) return;
    setLocalError(null);
    try {
      await createBundleMutation.mutateAsync({
        mountingSku: selectedMountSku,
        stoneSku: selectedStoneSku,
        addToCart: true,
        audience,
      });
      if (isB2b) {
        setB2bOrderOpen(true);
        navigate('/b2b/siparis-fisi');
      } else {
        setB2cCartOpen(true);
        navigate(catalogPath);
      }
    } catch (err) {
      setLocalError(err instanceof ApiClientError ? err.message : 'Sepete eklenemedi');
    }
  };

  const selectedStone = (stonesQuery.data?.items ?? []).find((s) => s.parentSku === selectedStoneSku);
  const b2cFinal = pricing?.channels?.B2C_API?.finalPriceTry ?? pricing?.baseCostTry ?? null;
  const b2bFinal = pricing?.channels?.B2B?.finalPriceTry ?? pricing?.baseCostTry ?? null;
  const displayFinal = isB2b ? b2bFinal : b2cFinal;
  const usdTry = ratesQuery.data?.liveUsdSell ?? ratesQuery.data?.entryUsdRate ?? 34;

  return (
    <div className="bg-background text-foreground min-h-[70vh]">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-12 py-6 sm:py-10 space-y-6">
        <StorefrontBreadcrumb
          items={[
            { label: homeLabel, to: homePath },
            { label: catalogLabel, to: catalogPath },
            { label: 'Kendin Tasarla' },
          ]}
        />

        <header className="space-y-3">
          <div className="inline-flex items-center gap-2 text-[11px] tracking-[0.14em] uppercase text-muted-foreground">
            <Sparkles className="w-3.5 h-3.5" />
            Design Your Own
          </div>
          <h1 className="font-serif text-2xl sm:text-3xl text-foreground">Montür + Sertifikalı Taş</h1>
          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            Uyumlu montürü seçin, karat/şekil aralığına uyan serbest taşı rezerve edin. Sepete ekleme 15 dakikalık
            soft-lock başlatır; checkout’ta stok kesinleşir.
          </p>
        </header>

        <ol className="flex flex-wrap gap-2 sm:gap-3">
          {STEPS.map((s) => {
            const active = step === s.id;
            const done = step > s.id;
            return (
              <li key={s.id}>
                <button
                  type="button"
                  disabled={s.id === 2 && !selectedMountSku}
                  onClick={() => {
                    if (s.id === 1) setStep(1);
                    if (s.id === 2 && selectedMountSku) setStep(2);
                    if (s.id === 3 && selectedStoneSku && pricing) setStep(3);
                  }}
                  className={cn(
                    'inline-flex items-center gap-2 px-3 py-2 rounded-[4px] text-xs font-medium border transition-colors',
                    active && 'bg-primary text-primary-foreground border-foreground',
                    done && !active && 'bg-card border-ring text-foreground',
                    !active && !done && 'bg-white border-border text-muted-foreground'
                  )}
                >
                  <span className="font-mono tabular-nums">{done ? <Check className="w-3.5 h-3.5" /> : s.id}</span>
                  {s.label}
                </button>
              </li>
            );
          })}
        </ol>

        {localError && (
          <div className="px-4 py-3 rounded-[4px] border border-red-200 bg-red-50 text-sm text-red-800">
            {localError}
          </div>
        )}

        {!authenticated && (
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 rounded-[4px] border border-border bg-card">
            <p className="text-sm text-muted-foreground">Taş listesi ve sepete ekleme için oturum açın.</p>
            <button type="button" className={TARA_PRIMARY_BTN_CLASS} onClick={() => setAuthModalOpen(true)}>
              Giriş yap
            </button>
          </div>
        )}

        {step === 1 && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold tracking-wide uppercase text-muted-foreground">DYO’ya hazır montürler</h2>
            {catalogQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> Katalog yükleniyor…
              </div>
            ) : mountings.length === 0 ? (
              <StorefrontEmptyState
                title="Uygun montür yok"
                description="OPS’ta MOUNTING ürünlerine uyumlu şekil ve karat aralığı tanımlandıktan sonra burada listelenir."
                action={
                  <Link to={catalogPath} className={TARA_SECONDARY_BTN_CLASS}>
                    {isB2b ? 'Kataloğa dön' : 'Koleksiyona dön'}
                  </Link>
                }
              />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {mountings.map((mount) => {
                  const selected = mount.parentSku === selectedMountSku;
                  return (
                    <button
                      key={mount.parentSku}
                      type="button"
                      onClick={() => goToStones(mount.parentSku)}
                      className={cn(
                        'text-left rounded-[4px] border bg-white p-3 space-y-3 transition-colors cursor-pointer',
                        selected ? 'border-foreground ring-1 ring-foreground' : 'border-border hover:border-ring'
                      )}
                    >
                      <ProductThumb product={mount} />
                      <div className="space-y-1">
                        <div className="font-serif text-base text-foreground line-clamp-2">{mount.title}</div>
                        <div className="font-mono text-[11px] text-muted-foreground">{mount.parentSku}</div>
                        <div className="text-xs text-muted-foreground">{mountingLabel(mount)}</div>
                        {mount.mountingDetail?.settingLaborUsd ? (
                          <div className="text-xs text-muted-foreground">
                            Mıhlama {formatCurrencyValue(mount.mountingDetail.settingLaborUsd, 'USD')}
                          </div>
                        ) : null}
                      </div>
                      <span className={cn(TARA_PRIMARY_BTN_CLASS, 'w-full')}>
                        Taş seç <ArrowRight className="w-3.5 h-3.5" />
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {step === 2 && selectedMount && (
          <section className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <button
                  type="button"
                  className={cn(TARA_SECONDARY_BTN_CLASS, 'mb-3')}
                  onClick={() => {
                    setStep(1);
                    navigate(designBase, { replace: true });
                  }}
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Montür değiştir
                </button>
                <h2 className="font-serif text-xl text-foreground">{selectedMount.title}</h2>
                <p className="text-xs text-muted-foreground mt-1">{mountingLabel(selectedMount)}</p>
              </div>
              <div className="w-28 shrink-0">
                <ProductThumb product={selectedMount} />
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <input
                value={colorFilter}
                onChange={(e) => setColorFilter(e.target.value.toUpperCase())}
                placeholder="Renk (F, G…)"
                className="h-10 px-3 rounded-[4px] border border-input bg-white text-xs font-mono w-28"
              />
              <input
                value={clarityFilter}
                onChange={(e) => setClarityFilter(e.target.value.toUpperCase())}
                placeholder="Berraklık (VS1…)"
                className="h-10 px-3 rounded-[4px] border border-input bg-white text-xs font-mono w-36"
              />
            </div>

            {!authenticated ? (
              <p className="text-sm text-muted-foreground">Uyumlu taşları görmek için giriş yapın.</p>
            ) : stonesQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> Uyumlu taşlar yükleniyor…
              </div>
            ) : stonesQuery.isError ? (
              <div className="text-sm text-red-700">
                {stonesQuery.error instanceof ApiClientError
                  ? stonesQuery.error.message
                  : 'Taş listesi alınamadı'}
              </div>
            ) : (stonesQuery.data?.items.length ?? 0) === 0 ? (
              <StorefrontEmptyState
                title="Uyumlu taş bulunamadı"
                description="Şekil, karat veya mm toleransına uyan stokta taş yok; soft-lock’taki taşlar da listeden düşer."
              />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {stonesQuery.data!.items.map((stone) => {
                  const d = stone.looseStoneDetail;
                  const busy = validateMutation.isPending && selectedStoneSku === stone.parentSku;
                  return (
                    <button
                      key={stone.parentSku}
                      type="button"
                      disabled={validateMutation.isPending}
                      onClick={() => void handleSelectStone(stone.parentSku)}
                      className="text-left rounded-[4px] border border-border bg-white p-3 space-y-2 hover:border-ring transition-colors cursor-pointer disabled:opacity-60"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="font-serif text-sm text-foreground line-clamp-2">{stone.title}</div>
                          <div className="font-mono text-[11px] text-muted-foreground mt-0.5">{stone.parentSku}</div>
                        </div>
                        <Diamond className="w-4 h-4 text-muted-foreground shrink-0" />
                      </div>
                      <div className="text-xs text-muted-foreground">{stoneLabel(stone)}</div>
                      {d?.netCostUsd != null && (
                        <div className="text-xs font-mono text-foreground">
                          Taş {formatCurrencyValue(d.netCostUsd, 'USD')}
                          <span className="text-muted-foreground"> · ≈ {formatCurrencyValue(d.netCostUsd * usdTry, 'TRY')}</span>
                        </div>
                      )}
                      <span className={cn(TARA_SECONDARY_BTN_CLASS, 'w-full')}>
                        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Seç ve fiyatla'}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {step === 3 && selectedMount && selectedStone && pricing && (
          <section className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-6">
            <div className="space-y-4 rounded-[4px] border border-border bg-white p-4 sm:p-5">
              <h2 className="font-serif text-xl">Paket özeti</h2>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Montür</div>
                  <ProductThumb product={selectedMount} />
                  <div className="text-sm font-medium">{selectedMount.title}</div>
                  <div className="font-mono text-[11px] text-muted-foreground">{selectedMount.parentSku}</div>
                </div>
                <div className="space-y-2">
                  <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Taş</div>
                  <ProductThumb product={selectedStone} />
                  <div className="text-sm font-medium">{selectedStone.title}</div>
                  <div className="text-xs text-muted-foreground">{stoneLabel(selectedStone)}</div>
                </div>
              </div>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs border-t border-border pt-4">
                <dt className="text-muted-foreground">B2C satış</dt>
                <dd className="text-right font-mono">
                  {formatCurrencyValue(pricing.channels?.B2C_API?.finalPriceTry ?? 0, 'TRY')}
                </dd>
                <dt className="text-muted-foreground">B2B satış</dt>
                <dd className="text-right font-mono">
                  {formatCurrencyValue(pricing.channels?.B2B?.finalPriceTry ?? 0, 'TRY')}
                </dd>
              </dl>
            </div>

            <aside className="space-y-4 rounded-[4px] border border-foreground bg-primary text-primary-foreground p-4 sm:p-5 h-fit">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                <Lock className="w-3.5 h-3.5" /> 15 dk soft-lock
              </div>
              <div>
                <div className="text-xs text-muted-foreground">
                  {isB2b ? 'B2B bayi fiyatı' : 'B2C nihai'}
                </div>
                <div className="font-serif text-3xl mt-1">
                  {displayFinal != null ? formatCurrencyValue(displayFinal, 'TRY') : '—'}
                </div>
              </div>
              {!isB2b && pricing.channels.B2B && (
                <div className="text-xs text-muted-foreground">
                  B2B referans: {formatCurrencyValue(pricing.channels.B2B.finalPriceTry, 'TRY')}
                </div>
              )}
              {isB2b && pricing.channels.B2C_API && (
                <div className="text-xs text-muted-foreground">
                  B2C referans: {formatCurrencyValue(pricing.channels.B2C_API.finalPriceTry, 'TRY')}
                </div>
              )}
              <p className="text-xs text-muted-foreground leading-relaxed">
                {isB2b
                  ? 'Sipariş fişine eklediğinizde taş soft-lock edilir. Bundle satırları tek başına silinemez.'
                  : 'Sepete eklediğinizde taş soft-lock edilir. Bundle satırları tek başına silinemez; paket olarak kaldırılır.'}
              </p>
              <button
                type="button"
                className="w-full inline-flex items-center justify-center gap-2 min-h-[44px] px-5 rounded-[4px] bg-background text-foreground text-sm font-medium hover:bg-white disabled:opacity-50 cursor-pointer"
                disabled={createBundleMutation.isPending}
                onClick={() => void handleAddToCart()}
              >
                {createBundleMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    {isB2b ? 'Sipariş fişine ekle' : 'Sepete ekle'} <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
              <button
                type="button"
                className="w-full text-xs text-muted-foreground hover:text-primary-foreground underline-offset-2 hover:underline cursor-pointer"
                onClick={() => setStep(2)}
              >
                Taş seçimine dön
              </button>
            </aside>
          </section>
        )}
      </div>
    </div>
  );
}

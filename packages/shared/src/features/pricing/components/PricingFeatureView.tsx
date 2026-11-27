import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, RefreshCw } from 'lucide-react';
import { PricingEngineView } from '../../../components/PricingEngineView';
import { PortalDataCard, PortalPageHeader } from '../../../components/portal';
import { CapabilityGate, useAuth } from '../../../providers/AuthProvider';
import {
  Button,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../../components/ui';
import {
  useActiveProductMetrics,
  usePortalSelection,
  useUpdateProductMutation,
} from '../../catalog/hooks/useCatalogQueries';
import { apiFetch } from '../../../lib/api/client';
import { computeJewelryMetrics, TROY_OZ_TO_GRAM } from '../../../utils/pricingEngine';
import type { LiveRates, ProductState } from '../../../types/jewelry';

type RecipeSnapshotInfo = {
  id: string;
  status: string;
  sourceMatrixVersion: number | null;
  appliedRatesSnapshot?: {
    sourceMatrixId?: string;
    sourceMatrixVersion?: number;
    fxBaseRates?: Record<string, string | number>;
    liveHasGoldTrySell?: string | number;
  };
};

export function PricingFeatureView() {
  const { setRole } = useAuth();
  const {
    products,
    product,
    activeProduct,
    rates,
    computed,
    isLoading,
    isError,
    isEmpty,
    hasLiveRates,
    refetch,
  } = useActiveProductMetrics();
  const { setSelectedParentSku } = usePortalSelection();
  const updateProductMutation = useUpdateProductMutation();
  const [recipeInfo, setRecipeInfo] = useState<RecipeSnapshotInfo | null>(null);
  const [localRates, setLocalRates] = useState<LiveRates | null>(null);
  const [hasManualOverride, setHasManualOverride] = useState(false);

  useEffect(() => {
    setLocalRates(null);
    setHasManualOverride(false);
    setRecipeInfo(null);
    if (!activeProduct?.parentSku) return;
    let active = true;
    apiFetch<RecipeSnapshotInfo[]>(
      `/api/v1/ops/pricing/recipes?parentSku=${encodeURIComponent(activeProduct.parentSku)}&pageSize=1`
    )
      .then((res) => {
        if (!active) return;
        const rec = (res.data ?? [])[0] ?? null;
        setRecipeInfo(rec);
        const snapFx = rec?.appliedRatesSnapshot?.fxBaseRates;
        if (snapFx && Object.keys(snapFx).length > 0) {
          const parsedFx: Record<string, number> = { ...rates.fxBaseRates };
          for (const [k, v] of Object.entries(snapFx)) {
            parsedFx[k] = Number(v) || parsedFx[k] || 0;
          }
          const hasGold = Number(rec.appliedRatesSnapshot?.liveHasGoldTrySell) || rates.liveHasGoldTrySell;
          setLocalRates({
            ...rates,
            snapshotId: rec.sourceMatrixVersion ? `Matris v${rec.sourceMatrixVersion} (Snapshot)` : rates.snapshotId,
            liveUsdSell: parsedFx.USD ?? rates.liveUsdSell,
            liveEurSell: parsedFx.EUR ?? rates.liveEurSell,
            liveHasGoldTrySell: hasGold,
            fxBaseRates: parsedFx as LiveRates['fxBaseRates'],
          });
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [activeProduct?.parentSku]);

  const effectiveRates = localRates ?? rates;
  const effectiveComputed = useMemo(
    () => (localRates ? computeJewelryMetrics(product, localRates) : computed),
    [localRates, product, computed]
  );

  const handleUpdateProduct = (patch: Partial<ProductState>) => {
    if (!activeProduct) return;
    updateProductMutation.mutate({ parentSku: activeProduct.parentSku, patch });
  };

  const persistRecipeSnapshot = (nextRates: LiveRates, manual: boolean) => {
    if (!recipeInfo?.id || recipeInfo.status === 'YAYINLANDI') return;
    void apiFetch(`/api/v1/ops/pricing/recipes/${recipeInfo.id}`, {
      method: 'PATCH',
      body: {
        appliedRatesSnapshot: {
          sourceMatrixVersion: recipeInfo.sourceMatrixVersion,
          fxBaseRates: nextRates.fxBaseRates,
          liveHasGoldTrySell: nextRates.liveHasGoldTrySell,
        },
        overrideMetadata: { manualOverride: manual, updatedAt: new Date().toISOString() },
      },
    }).catch(() => {});
  };

  const handleUpdateRates = (patch: Partial<LiveRates>) => {
    const nextRates: LiveRates = {
      ...effectiveRates,
      ...patch,
      fxBaseRates: {
        ...effectiveRates.fxBaseRates,
        ...(patch.fxBaseRates ?? {}),
      },
    };
    setLocalRates(nextRates);
    setHasManualOverride(true);
    persistRecipeSnapshot(nextRates, true);
  };

  const handleResetFromCentralMatrix = () => {
    setLocalRates(null);
    setHasManualOverride(false);
    persistRecipeSnapshot(rates, false);
  };

  if (isLoading) {
    return (
      <div className="space-y-6 w-full max-w-full min-w-0">
        <PortalPageHeader
          eyebrow="Canlı Maliyet & Fiyatlandırma"
          title="Yükleniyor..."
          description="Ürün ve kur verileri getiriliyor"
        />
        <PortalDataCard contentClassName="px-5 py-10">
          <div className="flex flex-col items-center gap-3 text-sm text-muted-foreground">
            <RefreshCw className="h-5 w-5 animate-spin" />
            Katalog ve canlı kurlar yükleniyor...
          </div>
        </PortalDataCard>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6 w-full max-w-full min-w-0">
        <PortalPageHeader
          eyebrow="Canlı Maliyet & Fiyatlandırma"
          title="Veri yüklenemedi"
          description="API bağlantısı başarısız"
        />
        <PortalDataCard contentClassName="px-5 py-8">
          <div className="flex flex-col items-center gap-3 text-sm">
            <p className="text-rose-600">Ürün veya kur verileri alınamadı.</p>
            <Button type="button" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-3.5 w-3.5" />
              Tekrar Dene
            </Button>
          </div>
        </PortalDataCard>
      </div>
    );
  }

  if (isEmpty || !activeProduct) {
    return (
      <div className="space-y-6 w-full max-w-full min-w-0">
        <PortalPageHeader
          eyebrow="Canlı Maliyet & Fiyatlandırma"
          title="Henüz kayıt bulunamadı"
          description="Fiyat motorunu kullanmak için önce bir ürün ekleyin"
        />
        <PortalDataCard contentClassName="px-5 py-8">
          <div className="flex flex-col items-center gap-3 text-sm text-muted-foreground">
            <p>Katalogda ürün yok.</p>
            <Button variant="outline" size="sm" asChild>
              <Link to="/ops/urunler">Ürün Yönetimine Git</Link>
            </Button>
          </div>
        </PortalDataCard>
      </div>
    );
  }

  if (!hasLiveRates) {
    return (
      <div className="space-y-6 w-full max-w-full min-w-0">
        <PortalPageHeader
          eyebrow="Canlı Maliyet & Fiyatlandırma"
          title="Kur verisi yok"
          description="Canlı kur kaydı bulunamadı"
        />
        <PortalDataCard contentClassName="px-5 py-8">
          <div className="flex flex-col items-center gap-3 text-sm">
            <p className="text-muted-foreground">
              Henüz kayıtlı kur bulunamadı. Tekrar deneyin veya kur kaynağını kontrol edin.
            </p>
            <Button type="button" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-3.5 w-3.5" />
              Tekrar Dene
            </Button>
          </div>
        </PortalDataCard>
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full max-w-full min-w-0 overflow-x-hidden">
      <PortalPageHeader
        eyebrow={`Canlı Maliyet & Fiyatlandırma · ${product.parentSku}`}
        title={product.title || product.parentSku}
        description="Maliyet kalemleri, çapraz kur matrisi ve satış kanalı kuralları"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="pricing-model-select" className="text-xs whitespace-nowrap">
                Ürün Modeli
              </Label>
              <Select value={product.parentSku} onValueChange={setSelectedParentSku}>
                <SelectTrigger id="pricing-model-select" className="w-[min(280px,70vw)] h-9">
                  <SelectValue placeholder="Model seçin" />
                </SelectTrigger>
                <SelectContent>
                  {products.map((item) => (
                    <SelectItem key={item.parentSku} value={item.parentSku}>
                      {item.parentSku} · {item.title || 'Adsız ürün'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link to={`/urun/${product.parentSku}`}>
                Ürünü Vitrinde Gör
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </Button>
          </div>
        }
      />

      <CapabilityGate
        capability="pricing:edit"
        fallback={
          <PortalDataCard contentClassName="px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-foreground">
              <span>
                Şu anda salt okunur görüntüleme modundasınız. Maliyet, işçilik ve canlı kur
                parametrelerini düzenlemek için Yönetim yetkisine geçebilirsiniz.
              </span>
              <Button type="button" size="sm" onClick={() => setRole('erp')}>
                Yönetim Yetkisine Geç
              </Button>
            </div>
          </PortalDataCard>
        }
      >
        {null}
      </CapabilityGate>

      <PortalDataCard
        title="Ürün Bazlı Kur / Metal Referansı (Merkezi Matristen Bağımsız)"
        contentClassName="p-4 flex flex-wrap items-end gap-4 text-xs"
        toolbar={
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground font-mono">
              {hasManualOverride
                ? 'Manuel Override (Yalnızca bu ürün)'
                : recipeInfo?.sourceMatrixVersion
                  ? `Merkezi Matris v${recipeInfo.sourceMatrixVersion}`
                  : 'Aktif Merkezi Matris'}
            </span>
            <Button type="button" size="sm" variant="outline" onClick={handleResetFromCentralMatrix}>
              <RefreshCw className="w-3 h-3 mr-1" />
              Merkezi Matristen Al
            </Button>
          </div>
        }
      >
        <div className="space-y-1">
          <Label className="text-[11px]">USD / TRY</Label>
          <Input
            type="number"
            step="any"
            className="h-8 w-28 font-mono text-right"
            value={effectiveRates.fxBaseRates.USD ?? 42}
            onChange={(e) => {
              const v = parseFloat(e.target.value) || 0;
              handleUpdateRates({
                liveUsdSell: v,
                fxBaseRates: { ...effectiveRates.fxBaseRates, USD: v },
              });
            }}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-[11px]">EUR / TRY</Label>
          <Input
            type="number"
            step="any"
            className="h-8 w-28 font-mono text-right"
            value={effectiveRates.fxBaseRates.EUR ?? 48.5}
            onChange={(e) => {
              const v = parseFloat(e.target.value) || 0;
              handleUpdateRates({
                liveEurSell: v,
                fxBaseRates: { ...effectiveRates.fxBaseRates, EUR: v },
              });
            }}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-[11px]">Has Altın (TRY/gr)</Label>
          <Input
            type="number"
            step="any"
            className="h-8 w-32 font-mono text-right"
            value={effectiveRates.liveHasGoldTrySell}
            onChange={(e) => {
              const hasTry = parseFloat(e.target.value) || 0;
              const xauOz = Number((hasTry * TROY_OZ_TO_GRAM).toFixed(2));
              handleUpdateRates({
                liveHasGoldTrySell: hasTry,
                fxBaseRates: { ...effectiveRates.fxBaseRates, XAU: xauOz },
              });
            }}
          />
        </div>
      </PortalDataCard>

      <PricingEngineView
        product={product}
        rates={effectiveRates}
        computed={effectiveComputed}
        onUpdateProduct={handleUpdateProduct}
        onUpdateRates={handleUpdateRates}
      />
    </div>
  );
}

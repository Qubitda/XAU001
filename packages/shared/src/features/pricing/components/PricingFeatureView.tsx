import { Link } from 'react-router-dom';
import { ArrowUpRight, RefreshCw } from 'lucide-react';
import { PricingEngineView } from '../../../components/PricingEngineView';
import { PortalDataCard, PortalPageHeader } from '../../../components/portal';
import { CapabilityGate, useAuth } from '../../../providers/AuthProvider';
import {
  Button,
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
  useUpdateRatesMutation,
} from '../../catalog/hooks/useCatalogQueries';
import type { LiveRates, ProductState } from '../../../types/jewelry';

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
  const updateRatesMutation = useUpdateRatesMutation();

  const handleUpdateProduct = (patch: Partial<ProductState>) => {
    if (!activeProduct) return;
    updateProductMutation.mutate({ parentSku: activeProduct.parentSku, patch });
  };

  const handleUpdateRates = (patch: Partial<LiveRates>) => {
    updateRatesMutation.mutate(patch);
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

      <PricingEngineView
        product={product}
        rates={rates}
        computed={computed}
        onUpdateProduct={handleUpdateProduct}
        onUpdateRates={handleUpdateRates}
      />
    </div>
  );
}

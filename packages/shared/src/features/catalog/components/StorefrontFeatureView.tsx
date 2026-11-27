import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ClipboardList } from 'lucide-react';
import { PortalPageHeader } from '../../../components/portal';
import { Button } from '../../../components/ui';
import { StorefrontView } from '../../../components/StorefrontView';
import { useAuth } from '../../../providers/AuthProvider';
import {
  useActiveProductMetrics,
  usePortalSelection,
} from '../hooks/useCatalogQueries';
import type { MetalColor } from '../types';
import {
  useAddToB2bDraftMutation,
  useAddToB2cCartMutation,
  useB2bDraftQuery,
  useCommerceUI,
  useFavoritesQuery,
  useToggleFavoriteMutation,
} from '../../commerce/hooks/useCommerceQueries';
import {
  buildB2bOrderLineFromProduct,
  buildB2cCartItemFromProduct,
} from '../../commerce/services/commerceService';

interface StorefrontFeatureViewProps {
  portalMode?: 'b2c' | 'b2b';
}

export function StorefrontFeatureView({ portalMode }: StorefrontFeatureViewProps = {}) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { role, setRole } = useAuth();
  const { products: rawProducts, product, rates } = useActiveProductMetrics();
  const { setSelectedParentSku } = usePortalSelection();
  const addB2cMutation = useAddToB2cCartMutation();
  const addB2bMutation = useAddToB2bDraftMutation();
  const favoritesQuery = useFavoritesQuery();
  const toggleFavoriteMutation = useToggleFavoriteMutation();
  const { setB2bOrderOpen } = useCommerceUI();
  const b2bDraftQuery = useB2bDraftQuery();
  const draftPieces = (b2bDraftQuery.data?.lines ?? []).reduce((s, l) => s + l.qty, 0);

  const effectiveRole = portalMode === 'b2b' ? 'b2b' : portalMode === 'b2c' ? 'b2c' : role;
  const products =
    effectiveRole === 'b2c'
      ? rawProducts.filter((p) => p.stockStatus !== 'Tükendi')
      : rawProducts;
  const productRoutePrefix = portalMode === 'b2b' ? '/b2b/urun' : '/urun';

  const initialCategory = searchParams.get('category') || 'Tümü';
  const rawFilter = searchParams.get('filter');
  const initialMerchFilter =
    rawFilter === 'discounted' || rawFilter === 'new_collection' ? rawFilter : 'all';
  const initialQuery = searchParams.get('q') || '';

  const handleSelectProduct = (parentSku: string, previewColor?: MetalColor) => {
    setSelectedParentSku(parentSku);
    navigate(`${productRoutePrefix}/${encodeURIComponent(parentSku)}`, {
      state: previewColor ? { previewMetalColor: previewColor } : undefined,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div
      className={
        portalMode === 'b2b'
          ? 'space-y-6'
          : 'bg-[var(--tara-pearl)] max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-12 py-8 sm:py-10 lg:py-12'
      }
    >
      {portalMode === 'b2b' ? (
        <PortalPageHeader
          eyebrow={`Canlı kur · ${rates.snapshotId} · ${products.length} aktif SKU`}
          title="Toptan Katalog"
          description="SKU, taş veya sertifika arayın; ürünleri doğrudan sipariş fişine ekleyin."
          actions={
            <>
              <Button variant="outline" size="sm" asChild>
                <Link to="/b2b/siparis-fisi">
                  <ClipboardList className="w-3.5 h-3.5" />
                  Sipariş Fişi ({draftPieces})
                </Link>
              </Button>
              <Button size="sm" onClick={() => setB2bOrderOpen(true)}>
                Hesaplaşma &amp; Onay
              </Button>
            </>
          }
        />
      ) : null}
      <StorefrontView
        key={`${portalMode ?? 'auto'}-${initialCategory}-${initialMerchFilter}-${initialQuery}`}
        products={products}
        selectedParentSku={product.parentSku}
        rates={rates}
        role={effectiveRole}
        favoriteSkus={favoritesQuery.data ?? []}
        initialCategory={initialCategory}
        initialMerchFilter={initialMerchFilter}
        initialQuery={initialQuery}
        onRoleChange={setRole}
        onSelectProduct={handleSelectProduct}
        onToggleFavorite={(parentSku) => toggleFavoriteMutation.mutate(parentSku)}
        onOpenB2bOrder={() => setB2bOrderOpen(true)}
        onQuickAddB2c={(item, metrics) => {
          addB2cMutation.mutate(
            buildB2cCartItemFromProduct({
              product: item,
              computed: metrics,
              rates,
              qty: 1,
            })
          );
          // isAdded flash is optimistic in StorefrontView; guest/auth cart updates via mutation cache
        }}
        onQuickAddB2b={(item, metrics) => {
          addB2bMutation.mutate(
            buildB2bOrderLineFromProduct({
              product: item,
              computed: metrics,
              rates,
              qty: 1,
            })
          );
        }}
      />
    </div>
  );
}

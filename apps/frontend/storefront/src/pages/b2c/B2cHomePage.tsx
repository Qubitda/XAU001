import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useActiveProductMetrics,
  useCatalogQuery,
  usePortalSelection,
} from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import {
  useAddToB2cCartMutation,
  useFavoritesQuery,
  useToggleFavoriteMutation,
} from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { buildB2cCartItemFromProduct } from '@taragold/shared/features/commerce/services/commerceService';
import { computeJewelryMetrics } from '@taragold/shared/utils/pricingEngine';
import { resolveProductMedia } from '@taragold/shared/data/productMedia';
import { HeroBannerSlider } from '@taragold/shared/features/storefront/components/HeroBannerSlider';
import { CategoryStrip } from '@taragold/shared/features/storefront/components/CategoryStrip';
import {
  FeaturedAndNewSection,
  type ComputedStorefrontProduct,
} from '@taragold/shared/features/storefront/components/FeaturedAndNewSection';
import { BrandTrustStrip } from '@taragold/shared/features/storefront/components/BrandTrustStrip';

export function B2cHomePage() {
  const navigate = useNavigate();
  const catalogQuery = useCatalogQuery();
  const { rates } = useActiveProductMetrics();
  const { setSelectedParentSku } = usePortalSelection();
  const favoritesQuery = useFavoritesQuery();
  const toggleFavorite = useToggleFavoriteMutation();
  const addB2c = useAddToB2cCartMutation();

  const [addingSku, setAddingSku] = useState<string | null>(null);
  const [addedSku, setAddedSku] = useState<string | null>(null);

  const products = useMemo(
    () => (catalogQuery.data ?? []).filter((p) => p.stockStatus !== 'Tükendi'),
    [catalogQuery.data]
  );
  const favoriteSkus = favoritesQuery.data ?? [];

  const computedProducts = useMemo<ComputedStorefrontProduct[]>(
    () =>
      products.map((product) => ({
        product,
        metrics: computeJewelryMetrics(product, rates),
        media: resolveProductMedia(product.parentSku, product.metalColor, product.galleryImages),
      })),
    [products, rates]
  );

  const handleOpenProduct = (parentSku: string) => {
    setSelectedParentSku(parentSku);
    navigate(`/urun/${encodeURIComponent(parentSku)}`);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleQuickAdd = (entry: ComputedStorefrontProduct) => {
    setAddingSku(entry.product.parentSku);
    addB2c.mutate(
      buildB2cCartItemFromProduct({
        product: entry.product,
        computed: entry.metrics,
        rates,
        qty: 1,
      }),
      {
        onSuccess: () => {
          setAddedSku(entry.product.parentSku);
          window.setTimeout(
            () => setAddedSku((cur) => (cur === entry.product.parentSku ? null : cur)),
            1500
          );
        },
        onSettled: () => {
          setAddingSku((cur) => (cur === entry.product.parentSku ? null : cur));
        },
      }
    );
  };

  const addedProductTitle = useMemo(() => {
    if (!addedSku) return null;
    return products.find((p) => p.parentSku === addedSku)?.title ?? null;
  }, [addedSku, products]);

  return (
    <div className="bg-background text-foreground">
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {addedProductTitle ? `${addedProductTitle} sepete eklendi` : ''}
      </div>

      {/* 1. Hero Campaign Slider */}
      <HeroBannerSlider />

      {/* 2. Categories + Featured Collection + New Arrivals & Live Showcase */}
      <div className="py-12 sm:py-16 lg:py-20 space-y-16 sm:space-y-20">
        <CategoryStrip products={products} />

        <FeaturedAndNewSection
          items={computedProducts}
          isLoading={catalogQuery.isLoading}
          favoriteSkus={favoriteSkus}
          addingSku={addingSku}
          addedSku={addedSku}
          onOpenProduct={handleOpenProduct}
          onToggleFavorite={(sku) => toggleFavorite.mutate(sku)}
          onQuickAdd={handleQuickAdd}
        />
      </div>

      {/* 3. Brand Trust Strip */}
      <BrandTrustStrip />
    </div>
  );
}

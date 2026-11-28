import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Calculator, Globe, ImagePlus, Layers, Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { ProductCardView } from '../../../components/ProductCardView';
import { ConfirmDialog } from '../../../components/crud/ConfirmDialog';
import { CapabilityGate, useAuth } from '../../../providers/AuthProvider';
import {
  useActiveProductMetrics,
  useDeleteProductMutation,
  usePortalSelection,
  useUpdateProductMutation,
} from '../hooks/useCatalogQueries';
import { ProductEntityModal, type ProductModalTab } from './ProductEntityModal';
import { formatDeleteError } from '../utils/publishMessages';
import type { MetalColor, ProductState } from '../types';
import {
  useAddToB2bDraftMutation,
  useAddToB2cCartMutation,
  useCommerceUI,
  useFavoritesQuery,
  useToggleFavoriteMutation,
} from '../../commerce/hooks/useCommerceQueries';
import {
  buildB2bOrderLineFromProduct,
  buildB2cCartItemFromProduct,
} from '../../commerce/services/commerceService';
import { computeJewelryMetrics } from '../../../utils/pricingEngine';

interface ProductCardFeatureViewProps {
  portalMode?: 'b2c' | 'b2b';
}

interface ProductLocationState {
  previewMetalColor?: MetalColor;
}

export function ProductCardFeatureView({ portalMode }: ProductCardFeatureViewProps = {}) {
  const { parentSku } = useParams<{ parentSku?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { role, setRole } = useAuth();
  const { setSelectedParentSku } = usePortalSelection();
  const { products, product, rates, computed } = useActiveProductMetrics(parentSku);
  const updateProductMutation = useUpdateProductMutation();
  const deleteProductMutation = useDeleteProductMutation();
  const addB2cMutation = useAddToB2cCartMutation();
  const addB2bMutation = useAddToB2bDraftMutation();
  const favoritesQuery = useFavoritesQuery();
  const toggleFavoriteMutation = useToggleFavoriteMutation();
  const { setB2cCartOpen, setB2bOrderOpen } = useCommerceUI();

  const [editOpen, setEditOpen] = useState(false);
  const [editTab, setEditTab] = useState<ProductModalTab>('genel');
  const [deleteOpen, setDeleteOpen] = useState(false);
  /** Buyer surfaces configure variants locally — OPS PATCH requires catalog:write. */
  const [variantPatch, setVariantPatch] = useState<Partial<ProductState>>({});

  const openEditor = (tab: ProductModalTab) => {
    setEditTab(tab);
    setEditOpen(true);
  };

  const effectiveRole = portalMode === 'b2b' ? 'b2b' : portalMode === 'b2c' ? 'b2c' : role;
  const catalogRoute = portalMode === 'b2b' ? '/b2b/katalog' : '/koleksiyon';
  const productRoutePrefix = portalMode === 'b2b' ? '/b2b/urun' : '/urun';
  // Storefront / B2B are sales surfaces only — OPS edit chrome stays in /ops.
  const showOpsToolbar = !portalMode && role === 'erp';
  const isBuyerSurface = portalMode === 'b2c' || portalMode === 'b2b';

  useEffect(() => {
    if (!isBuyerSurface) {
      setVariantPatch({});
      return;
    }
    const preview = (location.state as ProductLocationState | null)?.previewMetalColor;
    setVariantPatch(preview ? { metalColor: preview } : {});
  }, [parentSku, location.state, isBuyerSurface]);

  useEffect(() => {
    if (parentSku && products.some((p) => p.parentSku === parentSku)) {
      setSelectedParentSku(parentSku);
    }
  }, [parentSku, products, setSelectedParentSku]);

  const displayProduct = useMemo(
    () => (isBuyerSurface ? { ...product, ...variantPatch } : product),
    [isBuyerSurface, product, variantPatch]
  );

  const displayComputed = useMemo(
    () => (isBuyerSurface ? computeJewelryMetrics(displayProduct, rates) : computed),
    [isBuyerSurface, displayProduct, rates, computed]
  );

  const relatedProducts = useMemo(() => {
    const others = products.filter((p) => p.parentSku !== displayProduct.parentSku);
    const sameCategory = others.filter((p) => p.category === displayProduct.category);
    const diffCategory = others.filter((p) => p.category !== displayProduct.category);
    return [...sameCategory, ...diffCategory].slice(0, 3);
  }, [products, displayProduct.parentSku, displayProduct.category]);

  const isFavorite = (favoritesQuery.data ?? []).includes(displayProduct.parentSku);

  const handleUpdateProduct = (patch: Partial<ProductState>) => {
    if (isBuyerSurface) {
      setVariantPatch((prev) => ({ ...prev, ...patch }));
      return;
    }
    updateProductMutation.mutate({ parentSku: product.parentSku, patch });
  };

  const handleConfirmDelete = async () => {
    try {
      const res = await deleteProductMutation.mutateAsync(product.parentSku);
      toast.success(
        res?.archived
          ? `${product.parentSku} arşivlendi (yayında olduğu veya işlem geçmişi bulunduğu için silinemedi).`
          : `${product.parentSku} kalıcı olarak silindi.`
      );
      const next = products.find((p) => p.parentSku !== product.parentSku);
      if (next) setSelectedParentSku(next.parentSku);
      setDeleteOpen(false);
      navigate(catalogRoute);
    } catch (err) {
      toast.error(formatDeleteError(err));
      setDeleteOpen(false);
    }
  };

  return (
    <div
      className={
        portalMode === 'b2b'
          ? 'space-y-6'
          : 'max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-12 py-8 space-y-6'
      }
    >
      {showOpsToolbar && (
        <CapabilityGate capability="catalog:write">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 pb-4 text-xs">
            <div className="text-zinc-500">
              Yönetim Kaydı:{' '}
              <span className="font-mono text-foreground font-semibold">{product.parentSku}</span>
              {' · '}
              <span>{product.title}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => openEditor('fiyatlandirma')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium bg-white border border-zinc-300 text-zinc-800 rounded-md hover:bg-zinc-50 transition-colors cursor-pointer"
              >
                <Calculator className="w-3.5 h-3.5 text-warning" />
                Fiyatlandırma
              </button>
              <button
                type="button"
                onClick={() => openEditor('varyantlar')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium bg-white border border-zinc-300 text-zinc-800 rounded-md hover:bg-zinc-50 transition-colors cursor-pointer"
              >
                <Layers className="w-3.5 h-3.5 text-zinc-700" />
                Varyantlar
              </button>
              <button
                type="button"
                onClick={() => openEditor('medya')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium bg-white border border-zinc-300 text-zinc-800 rounded-md hover:bg-zinc-50 transition-colors cursor-pointer"
              >
                <ImagePlus className="w-3.5 h-3.5 text-zinc-700" />
                Görsel & Video
              </button>
              <button
                type="button"
                onClick={() => openEditor('seo')}
                title="SEO"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium bg-white border border-zinc-300 text-zinc-800 rounded-md hover:bg-zinc-50 transition-colors cursor-pointer"
              >
                <Globe className="w-3.5 h-3.5 text-zinc-700" />
                SEO
              </button>
              <button
                type="button"
                onClick={() => openEditor('genel')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium bg-white border border-zinc-300 text-zinc-800 rounded-md hover:bg-zinc-50 transition-colors cursor-pointer"
              >
                <Pencil className="w-3.5 h-3.5" />
                Ürünü Düzenle
              </button>
              <CapabilityGate capability="catalog:delete">
                <button
                  type="button"
                  disabled={products.length <= 1}
                  onClick={() => setDeleteOpen(true)}
                  data-delete="true"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium bg-white border border-destructive/40 text-destructive rounded-md hover:bg-destructive/10 transition-colors disabled:opacity-40 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Ürünü Sil
                </button>
              </CapabilityGate>
            </div>
          </div>
        </CapabilityGate>
      )}

      <ProductCardView
        product={displayProduct}
        relatedProducts={relatedProducts}
        rates={rates}
        computed={displayComputed}
        role={effectiveRole}
        isFavorite={isFavorite}
        onToggleFavorite={() => toggleFavoriteMutation.mutate(displayProduct.parentSku)}
        onRoleChange={setRole}
        onUpdateProduct={handleUpdateProduct}
        onOpenPricing={() => navigate('/ops/fiyat-motoru')}
        onBackToVitrin={() => navigate(catalogRoute)}
        onSelectRelatedProduct={(sku) => {
          setSelectedParentSku(sku);
          navigate(`${productRoutePrefix}/${encodeURIComponent(sku)}`);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onAddToB2cCart={({ qty, engravingText, giftWrap }) => {
          addB2cMutation.mutate(
            buildB2cCartItemFromProduct({
              product: displayProduct,
              computed: displayComputed,
              rates,
              qty,
              engravingText,
              giftWrap,
            })
          );
        }}
        onAddToB2bOrder={({ lines, supplyType, dealerStampNote }) => {
          const orderLines = lines.map((entry) =>
            buildB2bOrderLineFromProduct({
              product: displayProduct,
              computed: displayComputed,
              rates,
              qty: entry.qty,
              sizeOverride: entry.size,
              supplyType,
              dealerStampNote,
            })
          );
          addB2bMutation.mutate(orderLines);
        }}
        onOpenB2cCart={() => setB2cCartOpen(true)}
        onOpenB2bOrder={() => setB2bOrderOpen(true)}
      />

      {showOpsToolbar ? (
        <>
          <ProductEntityModal
            open={editOpen}
            onOpenChange={setEditOpen}
            mode="edit"
            initialProduct={product}
            initialTab={editTab}
          />

          <ConfirmDialog
            open={deleteOpen}
            onOpenChange={setDeleteOpen}
            variant="destructive"
            isLoading={deleteProductMutation.isPending}
            title={`${product.parentSku} kaydını sil`}
            description="Bu ürünü sildiğinizde koleksiyon ve fiyat motorundan kaldırılır."
            confirmLabel="Sil"
            cancelLabel="Vazgeç"
            onConfirm={handleConfirmDelete}
          />
        </>
      ) : null}
    </div>
  );
}

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Calculator,
  CheckCircle2,
  ExternalLink,
  EyeOff,
  Globe,
  Image as ImageIcon,
  Layers,
  Pencil,
  Plus,
  Search,
  Trash2,
} from 'lucide-react';
import { ConfirmDialog } from '../../../components/crud/ConfirmDialog';
import { ListPage } from '../../../components/crud/ListPage';
import { PortalDataCard } from '../../../components/portal';
import {
  Button,
  Card,
  CardContent,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsList,
  TabsTrigger,
} from '../../../components/ui';
import { CapabilityGate } from '../../../providers/AuthProvider';
import {
  computeJewelryMetrics,
  formatCurrencyValue,
  formatTrNumber,
} from '../../../utils/pricingEngine';
import { resolveProductThumbnail } from '../../../data/productMedia';
import {
  useActiveProductMetrics,
  useDeleteProductMutation,
  usePortalSelection,
  usePublishProductMutation,
  useUnpublishProductMutation,
} from '../hooks/useCatalogQueries';
import { formatPublishError } from '../utils/publishMessages';
import { ProductEntityModal, type ProductModalTab } from './ProductEntityModal';
import { QuickStockModal } from './QuickStockModal';
import type { ProductState } from '../types';
import {
  matchesDefinitionValue,
  resolveDefinitionLabel,
  useDefinitionOptions,
  type DefinitionOption,
} from '../../definitions/hooks/useDefinitionsQuery';
import { LEGACY_STOREFRONT_CATEGORY_CODES } from '../../definitions/storefrontCategories';

export function CatalogManagementView() {
  const navigate = useNavigate();
  const { products, rates } = useActiveProductMetrics();
  const { setSelectedParentSku } = usePortalSelection();
  const publishProductMutation = usePublishProductMutation();
  const unpublishProductMutation = useUnpublishProductMutation();
  const deleteProductMutation = useDeleteProductMutation();
  const [publishError, setPublishError] = useState<string | null>(null);
  const categoryDefs = useDefinitionOptions('kategori');

  const categoryOptions = useMemo<DefinitionOption[]>(() => {
    // OPS katalog: tüm aktif kategoriler (tanım SSOT). Fallback yalnızca API yokken.
    return categoryDefs.options.length > 0
      ? categoryDefs.options
      : LEGACY_STOREFRONT_CATEGORY_CODES.map((code) => ({
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
          meta: {},
          parentCodes: [] as string[],
          parentLabels: [] as string[],
        }));
  }, [categoryDefs.options]);

  const categoryTabs = useMemo(() => {
    return [{ value: 'Tümü', label: 'Tümü' }, ...categoryOptions];
  }, [categoryOptions]);

  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('Tümü');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'DRAFT'>('ALL');
  const [createOpen, setCreateOpen] = useState(false);
  const [editingState, setEditingState] = useState<{
    product: ProductState;
    tab: ProductModalTab;
  } | null>(null);
  const [deletingProduct, setDeletingProduct] = useState<ProductState | null>(null);
  const [quickStockProduct, setQuickStockProduct] = useState<ProductState | null>(null);
  const [failedThumbs, setFailedThumbs] = useState<Record<string, boolean>>({});

  const publishedCount = useMemo(
    () => products.filter((p) => (p.catalogStatus ?? 'ACTIVE') === 'ACTIVE').length,
    [products]
  );
  const draftCount = useMemo(
    () => products.filter((p) => p.catalogStatus === 'DRAFT').length,
    [products]
  );

  const rows = useMemo(() => {
    const q = query.trim().toLocaleLowerCase('tr-TR');
    const matchOpts = categoryOptions;
    return products
      .filter((p) => {
        const status = p.catalogStatus ?? 'ACTIVE';
        if (statusFilter !== 'ALL' && status !== statusFilter) {
          return false;
        }
        if (
          categoryFilter !== 'Tümü' &&
          !matchesDefinitionValue(p.category, categoryFilter, matchOpts)
        ) {
          return false;
        }
        if (!q) return true;
        return (
          p.parentSku.toLowerCase().includes(q) ||
          p.title.toLocaleLowerCase('tr-TR').includes(q) ||
          p.stoneType.toLocaleLowerCase('tr-TR').includes(q) ||
          p.certificateAgency.toLowerCase().includes(q)
        );
      })
      .map((product) => ({
        product,
        metrics: computeJewelryMetrics(product, rates),
        thumbUrl: resolveProductThumbnail(product),
        categoryLabel: resolveDefinitionLabel(product.category, matchOpts) || product.category,
      }));
  }, [products, rates, query, categoryFilter, statusFilter, categoryOptions]);

  const handleConfirmDelete = async () => {
    if (!deletingProduct) return;
    try {
      const res = await deleteProductMutation.mutateAsync(deletingProduct.parentSku);
      toast.success(
        res?.archived
          ? `${deletingProduct.parentSku} arşivlendi (sipariş/sepet bağlantısı bulunduğu için).`
          : `${deletingProduct.parentSku} silindi.`
      );
      setDeletingProduct(null);
    } catch (err) {
      const msg = formatPublishError(err);
      setPublishError(msg);
      toast.error(msg);
      setDeletingProduct(null);
    }
  };

  return (
    <CapabilityGate
      capability="catalog:write"
      fallback={
        <Card className="max-w-xl mx-auto shadow-none">
          <CardContent className="p-10 text-center space-y-2">
            <h2 className="text-section text-foreground">Operasyon Katalog Yetkisi Gerekli</h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Katalog ve stok yönetimi ekranı yalnızca merkez operasyon (OPS) hesaplarına açıktır.
            </p>
          </CardContent>
        </Card>
      }
    >
      <div className="space-y-6">
        <ListPage
          title="Katalog & Stok Yönetimi"
          subtitle={`${products.length} mücevher modeli (${publishedCount} yayında · ${draftCount} taslak) · Fiyatlandırma, görsel/video galerisi ve SEO düzenleme`}
          actions={
            <>
              <Button size="sm" variant="outline" onClick={() => navigate('/ops/fiyat-motoru')}>
                <Calculator className="w-3.5 h-3.5" />
                Fiyat Motoru
              </Button>
              <Button size="sm" variant="success" onClick={() => setCreateOpen(true)}>
                <Plus className="w-3.5 h-3.5" />
                Yeni Ürün Ekle
              </Button>
            </>
          }
          filters={
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="relative flex-1 min-w-[220px] max-w-sm">
                <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <Input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Model kodu, ürün adı veya taş ara..."
                  className="h-9 pl-8 text-xs"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Tabs
                  value={statusFilter}
                  onValueChange={(v) => setStatusFilter(v as 'ALL' | 'ACTIVE' | 'DRAFT')}
                >
                  <TabsList className="h-9">
                    <TabsTrigger value="ALL" className="text-xs px-3">
                      Tümü ({products.length})
                    </TabsTrigger>
                    <TabsTrigger value="ACTIVE" className="text-xs px-3">
                      Yayında ({publishedCount})
                    </TabsTrigger>
                    <TabsTrigger value="DRAFT" className="text-xs px-3">
                      Taslak ({draftCount})
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

                <Tabs value={categoryFilter} onValueChange={setCategoryFilter}>
                  <TabsList className="h-9">
                    {categoryTabs.map((cat) => (
                      <TabsTrigger key={cat.value} value={cat.value} className="text-xs px-3">
                        {cat.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </div>
            </div>
          }
        >
          <PortalDataCard contentClassName="overflow-x-auto">
            {publishError && (
              <div className="mx-4 mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive flex items-center justify-between gap-2">
                <span>{publishError}</span>
                <button
                  type="button"
                  onClick={() => setPublishError(null)}
                  className="text-[11px] font-medium underline cursor-pointer shrink-0"
                >
                  Kapat
                </button>
              </div>
            )}
            <Table className="text-xs">
              <TableHeader className="bg-muted/40">
                <TableRow>
                  <TableHead className="px-4 font-medium">Model</TableHead>
                  <TableHead className="px-4 font-medium">Durum</TableHead>
                  <TableHead className="px-4 font-medium">Ayar / Taş</TableHead>
                  <TableHead className="px-4 font-medium text-right">Stok Adedi</TableHead>
                  <TableHead className="px-4 font-medium text-right">Has Altın</TableHead>
                  <TableHead className="px-4 font-medium text-right">B2B Toptan</TableHead>
                  <TableHead className="px-4 font-medium text-right">B2C Vitrin</TableHead>
                  <TableHead className="px-4 font-medium text-right">İşlemler</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(({ product, metrics, thumbUrl, categoryLabel }) => {
                  const status = product.catalogStatus ?? 'ACTIVE';
                  const isPublished = status === 'ACTIVE';
                  return (
                  <TableRow key={product.parentSku}>
                    <TableCell className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {thumbUrl && !failedThumbs[product.parentSku] ? (
                          <img
                            src={thumbUrl}
                            alt={product.title}
                            referrerPolicy="no-referrer"
                            onError={() =>
                              setFailedThumbs((prev) => ({ ...prev, [product.parentSku]: true }))
                            }
                            className="w-11 h-11 rounded-md object-cover bg-muted border border-border shrink-0"
                          />
                        ) : (
                          <div className="w-11 h-11 rounded-md bg-muted border border-border shrink-0 flex items-center justify-center text-muted-foreground">
                            <ImageIcon className="w-4 h-4" />
                          </div>
                        )}
                        <div>
                          <div className="font-medium text-foreground">{product.title}</div>
                          <div className="font-mono text-[11px] text-muted-foreground">
                            {product.parentSku} · {categoryLabel} ·{' '}
                            {product.certificateAgency || 'Sertifikasız'}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3 whitespace-nowrap">
                      {isPublished ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium text-[11px]">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                          Yayında
                        </span>
                      ) : status === 'ARCHIVED' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zinc-200 text-zinc-700 font-medium text-[11px]">
                          Arşiv
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium text-[11px]">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                          Taslak
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="px-4 py-3 text-foreground whitespace-nowrap">
                      <div>
                        {product.purityCode} {product.metalColor} Altın
                      </div>
                      <div className="font-mono text-[11px] text-muted-foreground tabular-nums">
                        {formatTrNumber(metrics.totalStoneCarat, 2)} ct · {product.grossWeightGram} gr
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => setQuickStockProduct(product)}
                        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-muted font-mono tabular-nums text-foreground transition-colors cursor-pointer"
                        title="Hızlı stok gir / düzelt / sıfırla"
                        aria-label={`${product.parentSku} stok adedi`}
                      >
                        <span>
                          {product.stockStatus === 'Siparişe Özel'
                            ? 'Siparişe Özel'
                            : `${formatTrNumber(product.stockQty ?? 0, 0)} adet`}
                        </span>
                        <Pencil className="w-3 h-3 text-muted-foreground" />
                      </button>
                    </TableCell>
                    <TableCell className="px-4 py-3 text-right font-mono tabular-nums text-foreground whitespace-nowrap">
                      {formatTrNumber(metrics.fireIncludedFineMetalGram, 4)} gr
                    </TableCell>
                    <TableCell className="px-4 py-3 text-right font-mono font-medium tabular-nums text-foreground whitespace-nowrap">
                      {metrics.ledger.hasB2bChannel
                        ? formatCurrencyValue(metrics.finalB2bPriceCurrency, product.pricingCurrency)
                        : '—'}
                    </TableCell>
                    <TableCell className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-foreground whitespace-nowrap">
                      {metrics.ledger.hasB2cChannel
                        ? `${formatTrNumber(metrics.discountedB2cPriceTry, 0)} TL`
                        : '—'}
                    </TableCell>
                    <TableCell className="px-4 py-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-0.5">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className={
                            isPublished
                              ? 'h-8 w-8 text-amber-600 hover:text-amber-700'
                              : 'h-8 w-8 text-emerald-600 hover:text-emerald-700'
                          }
                          title={isPublished ? 'Yayından Kaldır (Taslağa Al)' : 'Yayınla'}
                          disabled={
                            unpublishProductMutation.isPending || publishProductMutation.isPending
                          }
                          onClick={async () => {
                            setPublishError(null);
                            try {
                              if (isPublished) {
                                await unpublishProductMutation.mutateAsync(product.parentSku);
                                toast.success(`${product.parentSku} taslağa alındı.`);
                              } else {
                                await publishProductMutation.mutateAsync(product.parentSku);
                                toast.success(`${product.parentSku} yayına alındı.`);
                              }
                            } catch (err) {
                              const msg = formatPublishError(err);
                              setPublishError(msg);
                              toast.error(msg);
                            }
                          }}
                        >
                          {isPublished ? (
                            <EyeOff className="w-3.5 h-3.5" />
                          ) : (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          title="Varyantlar"
                          onClick={() => setEditingState({ product, tab: 'varyantlar' })}
                        >
                          <Layers className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          title="Fiyatlandırma & Maliyet Düzenle"
                          onClick={() => setEditingState({ product, tab: 'fiyatlandirma' })}
                        >
                          <Calculator className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          title="Görsel, Video & Medya Yönetimi"
                          onClick={() => setEditingState({ product, tab: 'medya' })}
                        >
                          <ImageIcon className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          title="SEO Ayarları"
                          onClick={() => setEditingState({ product, tab: 'seo' })}
                        >
                          <Globe className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          title="Tüm Alanları Düzenle"
                          onClick={() => setEditingState({ product, tab: 'genel' })}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          title="Ürün sayfasını aç"
                          onClick={() => {
                            setSelectedParentSku(product.parentSku);
                            navigate(`/urun/${encodeURIComponent(product.parentSku)}`);
                          }}
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </Button>
                        <CapabilityGate capability="catalog:delete">
                          <Button
                            type="button"
                            variant="ghost-destructive"
                            size="icon"
                            className="h-8 w-8"
                            data-delete="true"
                            title="Modeli sil"
                            disabled={deleteProductMutation.isPending}
                            onClick={() => setDeletingProduct(product)}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </CapabilityGate>
                      </div>
                    </TableCell>
                  </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </PortalDataCard>
        </ListPage>

        <ProductEntityModal
          open={createOpen}
          onOpenChange={setCreateOpen}
          mode="create"
          onSaved={(saved) => setSelectedParentSku(saved.parentSku)}
        />

        {editingState && (
          <ProductEntityModal
            open={Boolean(editingState)}
            onOpenChange={(open) => {
              if (!open) setEditingState(null);
            }}
            mode="edit"
            initialProduct={editingState.product}
            initialTab={editingState.tab}
          />
        )}

        <ConfirmDialog
          open={Boolean(deletingProduct)}
          onOpenChange={(open) => {
            if (!open) setDeletingProduct(null);
          }}
          variant="destructive"
          isLoading={deleteProductMutation.isPending}
          title={deletingProduct ? `${deletingProduct.parentSku} modelini sil` : 'Modeli sil'}
          description={
            deletingProduct
              ? `"${deletingProduct.title}" kaydı katalogdan kalıcı olarak kaldırılacak.`
              : ''
          }
          confirmLabel="Kalıcı Sil"
          cancelLabel="Vazgeç"
          onConfirm={handleConfirmDelete}
        />

        <QuickStockModal
          product={quickStockProduct}
          open={Boolean(quickStockProduct)}
          onOpenChange={(open) => {
            if (!open) setQuickStockProduct(null);
          }}
        />
      </div>
    </CapabilityGate>
  );
}
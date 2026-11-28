import { useMemo, useState } from 'react';
import { Grid3X3, Layers, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Input, Label } from '../../../components/ui';
import { ApiClientError } from '../../../lib/api/client';
import {
  useBulkCreateOpsVariantsMutation,
  useCreateOpsVariantMutation,
  useDeactivateOpsVariantMutation,
  useOpsVariantsQuery,
  usePatchOpsVariantMutation,
} from '../../ops/hooks/useOpsQueries';
import type { OpsVariant } from '../../ops/types';
import type { MetalColor, ProductKind, ProductState, PurityCode } from '../../../types/jewelry';
import { formatCurrencyValue, formatTrNumber } from '../../../utils/pricingEngine';
import { cn } from '../../../lib/utils';

const FIELD_SELECT_CLASS =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50';

type VariantFormState = {
  sku: string;
  purityCode: string;
  metalColor: string;
  size: number;
  centerStoneCarat: string;
  grossWeightGram: string;
  initialStockQty: number;
  isDefault: boolean;
};

export interface PendingMatrixConfig {
  purities: string[];
  colors: string[];
  sizes: number[];
  initialStockQty: number;
}

function emptyForm(product: ProductState): VariantFormState {
  const suffix = `${product.metalColor?.slice(0, 1) ?? 'X'}${product.variantSize || 14}`;
  return {
    sku: `${product.parentSku}-${suffix}`.toUpperCase(),
    purityCode: product.purityCode || '14K',
    metalColor: product.metalColor || 'Beyaz',
    size: product.variantSize || 14,
    centerStoneCarat: String(product.centerStoneCarat ?? 0),
    grossWeightGram: String(product.grossWeightGram || 3),
    initialStockQty: 0,
    isDefault: false,
  };
}

function formFromVariant(v: OpsVariant): VariantFormState {
  return {
    sku: v.sku,
    purityCode: v.purityCode,
    metalColor: v.metalColor,
    size: v.size,
    centerStoneCarat: v.centerStoneCarat,
    grossWeightGram: v.grossWeightGram,
    initialStockQty: v.stockQty,
    isDefault: v.isDefault,
  };
}

export function ProductVariantsPanel({
  product,
  productKind,
  purityOptions,
  colorOptions,
  mode,
  pendingMatrix,
  onPendingMatrixChange,
}: {
  product: ProductState;
  productKind: ProductKind;
  purityOptions: string[];
  colorOptions: string[];
  mode: 'create' | 'edit';
  pendingMatrix?: PendingMatrixConfig;
  onPendingMatrixChange?: (next: PendingMatrixConfig) => void;
}) {
  const parentSku = product.parentSku?.trim().toUpperCase() ?? '';
  const canManage = mode === 'edit' && Boolean(parentSku);
  const [showInactive, setShowInactive] = useState(false);

  const variantsQuery = useOpsVariantsQuery(
    { parentSku, pageSize: 100, ...(showInactive ? {} : { isActive: true }) },
    canManage
  );
  const createMutation = useCreateOpsVariantMutation();
  const patchMutation = usePatchOpsVariantMutation();
  const deactivateMutation = useDeactivateOpsVariantMutation();
  const bulkMutation = useBulkCreateOpsVariantsMutation();

  const [showForm, setShowForm] = useState(false);
  const [showMatrix, setShowMatrix] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<VariantFormState>(() => emptyForm(product));
  const [error, setError] = useState<string | null>(null);

  // Matrix state (used directly in edit mode, or synced to pendingMatrix in create mode)
  const availableColorList = useMemo(
    () => (colorOptions.length ? colorOptions : ['Beyaz', 'Sarı', 'Rose']),
    [colorOptions]
  );
  const availablePurityList = useMemo(
    () => (purityOptions.length ? purityOptions : ['14K', '18K', '22K']),
    [purityOptions]
  );

  const [matrixPurities, setMatrixPurities] = useState<string[]>(() =>
    pendingMatrix?.purities.length ? pendingMatrix.purities : product.purityCode ? [product.purityCode] : ['14K']
  );
  const [matrixColors, setMatrixColors] = useState<string[]>(() =>
    pendingMatrix?.colors.length
      ? pendingMatrix.colors
      : product.availableColors?.length
        ? product.availableColors
        : product.metalColor
          ? [product.metalColor]
          : ['Beyaz']
  );
  const [matrixSizesText, setMatrixSizesText] = useState<string>(() =>
    (pendingMatrix?.sizes.length
      ? pendingMatrix.sizes
      : product.availableSizes?.length
        ? product.availableSizes
        : [product.variantSize || 14]
    ).join(', ')
  );
  const [matrixInitialStock, setMatrixInitialStock] = useState<number>(
    pendingMatrix?.initialStockQty ?? 0
  );

  const parsedMatrixSizes = useMemo(() => {
    const nums = matrixSizesText
      .split(/[,\s]+/)
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isInteger(n) && n >= 0 && n <= 70);
    return Array.from(new Set(nums)).sort((a, b) => a - b);
  }, [matrixSizesText]);

  const syncPendingMatrix = (
    nextPurities: string[],
    nextColors: string[],
    nextSizes: number[],
    nextStock: number
  ) => {
    onPendingMatrixChange?.({
      purities: nextPurities,
      colors: nextColors,
      sizes: nextSizes,
      initialStockQty: nextStock,
    });
  };

  const rows = variantsQuery.data?.items ?? [];
  const showSize = productKind !== 'LOOSE_STONE';
  const showCarat = productKind !== 'MOUNTING';

  const catalogHints = useMemo(() => {
    const colors = product.availableColors?.length
      ? product.availableColors
      : (colorOptions as MetalColor[]);
    return { colors, purities: purityOptions as PurityCode[] };
  }, [product.availableColors, colorOptions, purityOptions]);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm(product));
    setError(null);
    setShowMatrix(false);
    setShowForm(true);
  };

  const openEdit = (v: OpsVariant) => {
    setEditingId(v.id);
    setForm(formFromVariant(v));
    setError(null);
    setShowMatrix(false);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!canManage) return;
    setError(null);
    const normalizedCarat = form.centerStoneCarat.toString().replace(',', '.').trim() || '0';
    const normalizedWeight = form.grossWeightGram.toString().replace(',', '.').trim() || '0.01';
    try {
      if (editingId) {
        await patchMutation.mutateAsync({
          variantId: editingId,
          body: {
            sku: form.sku.trim().toUpperCase(),
            purityCode: form.purityCode,
            metalColor: form.metalColor,
            size: form.size,
            centerStoneCarat: normalizedCarat,
            grossWeightGram: normalizedWeight,
            isDefault: form.isDefault,
          },
        });
        toast.success('Varyant güncellendi.');
      } else {
        await createMutation.mutateAsync({
          parentSku,
          sku: form.sku.trim().toUpperCase(),
          purityCode: form.purityCode,
          metalColor: form.metalColor,
          size: form.size,
          centerStoneCarat: normalizedCarat,
          grossWeightGram: normalizedWeight,
          initialStockQty: Math.max(0, Math.round(form.initialStockQty || 0)),
          isDefault: form.isDefault,
          isActive: true,
        });
        toast.success('Yeni varyant oluşturuldu.');
      }
      setShowForm(false);
      setEditingId(null);
    } catch (err) {
      const msg =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Varyant kaydedilemedi.';
      setError(msg);
      toast.error(msg);
    }
  };

  const handleDeleteOrDeactivate = async (v: OpsVariant) => {
    setError(null);
    try {
      const res = await deactivateMutation.mutateAsync(v.id);
      if (res.deleted) {
        toast.success(`${v.sku} varyantı silindi.`);
      } else {
        toast.success(`${v.sku} stok/sipariş kaydı bulunduğu için pasifleştirildi.`);
      }
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : 'İşlem başarısız oldu.';
      setError(msg);
      toast.error(msg);
    }
  };

  const handleActivate = async (v: OpsVariant) => {
    setError(null);
    try {
      await patchMutation.mutateAsync({ variantId: v.id, body: { isActive: true } });
      toast.success(`${v.sku} aktifleştirildi.`);
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : 'Durum güncellenemedi.';
      setError(msg);
    }
  };

  const handleBulkMatrixCreate = async () => {
    if (!canManage) return;
    setError(null);
    if (matrixPurities.length === 0 || matrixColors.length === 0 || parsedMatrixSizes.length === 0) {
      setError('Matris için en az bir ayar, bir renk ve geçerli bir ölçü girin.');
      return;
    }
    try {
      const res = await bulkMutation.mutateAsync({
        parentSku,
        purities: matrixPurities,
        colors: matrixColors,
        sizes: parsedMatrixSizes,
        centerStoneCarat: String(product.centerStoneCarat ?? 0),
        grossWeightGram: String(Math.max(0.01, Number(product.grossWeightGram) || 3)),
        initialStockQty: Math.max(0, Math.round(matrixInitialStock || 0)),
      });
      toast.success(
        `${res.createdCount} varyant oluşturuldu${res.skippedCount > 0 ? ` (${res.skippedCount} mevcut atlandı)` : ''}.`
      );
      setShowMatrix(false);
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : 'Matris üretimi başarısız oldu.';
      setError(msg);
      toast.error(msg);
    }
  };

  const toggleItem = (list: string[], val: string) =>
    list.includes(val) ? list.filter((x) => x !== val) : [...list, val];

  const matrixBuilderBlock = (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-foreground">Matristen Toplu Varyant Üret</div>
          <p className="text-[11px] text-muted-foreground">
            Seçtiğiniz ayar × renk × ölçü kombinasyonları gerçek <span className="font-mono">ProductVariant</span> kayıtlarına dönüştürülür.
          </p>
        </div>
        <span className="text-[11px] font-mono text-foreground">
          {matrixPurities.length * matrixColors.length * Math.max(1, parsedMatrixSizes.length)} kombinasyon
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-[11px]">Maden Ayarları</Label>
          <div className="flex flex-wrap gap-1.5">
            {availablePurityList.map((p) => {
              const active = matrixPurities.includes(p);
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    const next = toggleItem(matrixPurities, p);
                    setMatrixPurities(next);
                    syncPendingMatrix(next, matrixColors, parsedMatrixSizes, matrixInitialStock);
                  }}
                  className={cn(
                    'px-2.5 py-1 rounded border text-[11px] font-mono cursor-pointer',
                    active
                      ? 'bg-foreground text-white border-foreground'
                      : 'bg-background text-foreground border-input hover:bg-muted'
                  )}
                >
                  {p}
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label className="text-[11px]">Maden Renkleri</Label>
          <div className="flex flex-wrap gap-1.5">
            {availableColorList.map((c) => {
              const active = matrixColors.includes(c);
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => {
                    const next = toggleItem(matrixColors, c);
                    setMatrixColors(next);
                    syncPendingMatrix(matrixPurities, next, parsedMatrixSizes, matrixInitialStock);
                  }}
                  className={cn(
                    'px-2.5 py-1 rounded border text-[11px] cursor-pointer',
                    active
                      ? 'bg-foreground text-white border-foreground'
                      : 'bg-background text-foreground border-input hover:bg-muted'
                  )}
                >
                  {c}
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-1">
          <Label className="text-[11px]">Ölçüler (virgülle ayırın, örn. 12, 14, 16)</Label>
          <Input
            type="text"
            value={matrixSizesText}
            onChange={(e) => {
              const val = e.target.value;
              setMatrixSizesText(val);
              const parsed = val
                .split(/[,\s]+/)
                .map((s) => Number(s.trim()))
                .filter((n) => Number.isInteger(n) && n >= 0 && n <= 70);
              syncPendingMatrix(
                matrixPurities,
                matrixColors,
                Array.from(new Set(parsed)).sort((a, b) => a - b),
                matrixInitialStock
              );
            }}
            placeholder="12, 14, 16"
            className="font-mono text-xs"
          />
        </div>

        <div className="space-y-1">
          <Label className="text-[11px]">Varyant Başına Başlangıç Stoğu</Label>
          <Input
            type="number"
            min={0}
            step={1}
            value={matrixInitialStock}
            onChange={(e) => {
              const qty = Math.max(0, Math.round(Number(e.target.value) || 0));
              setMatrixInitialStock(qty);
              syncPendingMatrix(matrixPurities, matrixColors, parsedMatrixSizes, qty);
            }}
            className="font-mono text-right"
          />
        </div>
      </div>

      {canManage && (
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="outline" size="sm" onClick={() => setShowMatrix(false)}>
            Kapat
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={bulkMutation.isPending}
            onClick={() => void handleBulkMatrixCreate()}
          >
            <Grid3X3 className="w-3.5 h-3.5" />
            {bulkMutation.isPending ? 'Üretiliyor...' : 'Kombinasyonları Üret'}
          </Button>
        </div>
      )}
    </div>
  );

  if (!canManage) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-4 flex items-start gap-3">
          <Layers className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-foreground">
              Oluşturma Aşamasında Varyant Matrisi
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Aşağıda seçtiğiniz renk, ayar ve ölçüler ürün kaydedildiğinde otomatik olarak gerçek{' '}
              <span className="font-mono">ProductVariant</span> kayıtlarına dönüştürülür.
            </p>
          </div>
        </div>
        {matrixBuilderBlock}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Ürün Varyantları
            <span className="ml-2 font-mono text-xs text-muted-foreground">({rows.length})</span>
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Satılabilir seçenekler (renk, ayar, ölçü, karat). Stok miktarı Stok &amp; Depo sekmesinden veya yeni varyantta başlangıç stoğu olarak yönetilir.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer mr-1">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="rounded border-input"
            />
            Pasifleri göster
          </label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              setShowForm(false);
              setShowMatrix((v) => !v);
            }}
          >
            <Grid3X3 className="w-3.5 h-3.5" />
            Matristen Üret
          </Button>
          <Button type="button" size="sm" variant="success" onClick={openCreate}>
            <Plus className="w-3.5 h-3.5" />
            Yeni varyant ekle
          </Button>
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs font-medium">
          {error}
        </div>
      )}

      {showMatrix && matrixBuilderBlock}

      <div className="border border-border rounded-lg overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead className="bg-muted/60 text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">SKU</th>
              <th className="px-3 py-2 font-medium">Renk</th>
              <th className="px-3 py-2 font-medium">Ayar</th>
              {showSize && <th className="px-3 py-2 font-medium">Ölçü</th>}
              {showCarat && <th className="px-3 py-2 font-medium">Taş</th>}
              <th className="px-3 py-2 font-medium text-right">Gram</th>
              <th className="px-3 py-2 font-medium text-right">Stok*</th>
              <th className="px-3 py-2 font-medium">Durum</th>
              <th className="px-3 py-2 font-medium text-right">İşlem</th>
            </tr>
          </thead>
          <tbody>
            {variantsQuery.isLoading && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-muted-foreground">
                  Yükleniyor…
                </td>
              </tr>
            )}
            {!variantsQuery.isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-muted-foreground">
                  Aktif varyant yok. Katalog ipuçları: {(catalogHints.colors as string[]).join(', ') || '—'}
                </td>
              </tr>
            )}
            {rows.map((v) => {
              const summary = product.variants?.find((s) => s.id === v.id || s.sku === v.sku);
              const b2c = summary?.b2cPricing?.finalPriceTry;
              return (
                <tr key={v.id} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-foreground">
                    {v.sku}
                    {v.isDefault && (
                      <span className="ml-1 text-[10px] text-muted-foreground">varsayılan</span>
                    )}
                    {b2c != null && (
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        B2C ~{formatCurrencyValue(b2c, 'TRY')}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">{v.metalColor}</td>
                  <td className="px-3 py-2 font-mono">{v.purityCode}</td>
                  {showSize && <td className="px-3 py-2 font-mono">{v.size}</td>}
                  {showCarat && (
                    <td className="px-3 py-2 font-mono">
                      {formatTrNumber(Number(v.centerStoneCarat), 2)} ct
                    </td>
                  )}
                  <td className="px-3 py-2 text-right font-mono tabular-nums">
                    {formatTrNumber(Number(v.grossWeightGram), 2)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">{v.stockQty}</td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        'inline-flex px-2 py-0.5 rounded border text-[11px] font-medium',
                        v.isActive
                          ? 'bg-success/10 text-success border-success/30'
                          : 'bg-muted text-muted-foreground border-border'
                      )}
                    >
                      {v.isActive ? 'Aktif' : 'Pasif'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button
                      type="button"
                      className="text-[11px] font-medium text-zinc-700 hover:text-foreground mr-2 cursor-pointer"
                      onClick={() => openEdit(v)}
                    >
                      Düzenle
                    </button>
                    {v.isActive ? (
                      <button
                        type="button"
                        disabled={v.isDefault || deactivateMutation.isPending}
                        title={
                          v.isDefault
                            ? 'Varsayılan varyant silinemez/pasifleştirilemez'
                            : 'Stok/sipariş yoksa silinir, varsa pasifleştirilir'
                        }
                        className="inline-flex items-center gap-0.5 text-[11px] font-medium text-destructive hover:underline disabled:opacity-40 cursor-pointer"
                        onClick={() => void handleDeleteOrDeactivate(v)}
                      >
                        <Trash2 className="w-3 h-3" />
                        Sil / Pasifleştir
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="text-[11px] font-medium text-emerald-700 hover:underline cursor-pointer"
                        onClick={() => void handleActivate(v)}
                      >
                        Aktifleştir
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-muted-foreground">
        * Stok sütunu WarehouseStock aggregate özetidir; stok giriş/çıkışı Stok &amp; Depo sekmesinden yapılır.
      </p>

      {showForm && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <div className="text-xs font-semibold text-foreground">
            {editingId ? 'Varyantı Düzenle' : 'Yeni Varyant'}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px]">Varyant SKU</Label>
              <Input
                className="font-mono"
                value={form.sku}
                onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value.toUpperCase() }))}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px]">Metal rengi</Label>
              <select
                className={FIELD_SELECT_CLASS}
                value={form.metalColor}
                onChange={(e) => setForm((f) => ({ ...f, metalColor: e.target.value }))}
              >
                {availableColorList.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-[11px]">Metal ayarı</Label>
              <select
                className={cn(FIELD_SELECT_CLASS, 'font-mono')}
                value={form.purityCode}
                onChange={(e) => setForm((f) => ({ ...f, purityCode: e.target.value }))}
              >
                {availablePurityList.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            {showSize && (
              <div className="space-y-1">
                <Label className="text-[11px]">Yüzük ölçüsü</Label>
                <Input
                  type="number"
                  min={0}
                  max={70}
                  className="font-mono text-right"
                  value={form.size}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, size: Math.max(0, Math.round(Number(e.target.value) || 0)) }))
                  }
                />
              </div>
            )}
            {showCarat && (
              <div className="space-y-1">
                <Label className="text-[11px]">Taş karatı (ct)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min={0}
                  className="font-mono text-right"
                  value={form.centerStoneCarat}
                  onChange={(e) => setForm((f) => ({ ...f, centerStoneCarat: e.target.value }))}
                />
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-[11px]">Katalog gramaj (gr)</Label>
              <Input
                type="number"
                step="0.01"
                min={0.01}
                className="font-mono text-right"
                value={form.grossWeightGram}
                onChange={(e) => setForm((f) => ({ ...f, grossWeightGram: e.target.value }))}
              />
            </div>
            {!editingId && (
              <div className="space-y-1">
                <Label className="text-[11px]">Başlangıç Stoğu (Adet)</Label>
                <Input
                  type="number"
                  min={0}
                  step={1}
                  className="font-mono text-right"
                  value={form.initialStockQty}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      initialStockQty: Math.max(0, Math.round(Number(e.target.value) || 0)),
                    }))
                  }
                />
              </div>
            )}
          </div>
          <Label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.isDefault}
              onChange={(e) => setForm((f) => ({ ...f, isDefault: e.target.checked }))}
              className="rounded border-input"
            />
            <span className="text-xs font-medium">Varsayılan varyant</span>
          </Label>
          {error && (
            <div className="px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs font-medium">
              {error}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setShowForm(false);
                setEditingId(null);
              }}
            >
              Vazgeç
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={createMutation.isPending || patchMutation.isPending}
              onClick={() => void handleSave()}
            >
              {editingId ? 'Kaydet' : 'Varyantı Oluştur'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

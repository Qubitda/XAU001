import { useMemo, useState } from 'react';
import { Layers, Plus } from 'lucide-react';
import { Button, Input, Label } from '../../../components/ui';
import { ApiClientError } from '../../../lib/api/client';
import {
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
  isDefault: boolean;
};

function emptyForm(product: ProductState): VariantFormState {
  const suffix = `${product.metalColor?.slice(0, 1) ?? 'X'}${product.variantSize || 14}`;
  return {
    sku: `${product.parentSku}-${suffix}`.toUpperCase(),
    purityCode: product.purityCode || '14K',
    metalColor: product.metalColor || 'Beyaz',
    size: product.variantSize || 14,
    centerStoneCarat: String(product.centerStoneCarat ?? 0.3),
    grossWeightGram: String(product.grossWeightGram || 4),
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
    isDefault: v.isDefault,
  };
}

export function ProductVariantsPanel({
  product,
  productKind,
  purityOptions,
  colorOptions,
  mode,
}: {
  product: ProductState;
  productKind: ProductKind;
  purityOptions: string[];
  colorOptions: string[];
  mode: 'create' | 'edit';
}) {
  const parentSku = product.parentSku?.trim().toUpperCase() ?? '';
  const canManage = mode === 'edit' && Boolean(parentSku);
  const variantsQuery = useOpsVariantsQuery(
    { parentSku, pageSize: 100 },
    canManage
  );
  const createMutation = useCreateOpsVariantMutation();
  const patchMutation = usePatchOpsVariantMutation();
  const deactivateMutation = useDeactivateOpsVariantMutation();

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<VariantFormState>(() => emptyForm(product));
  const [error, setError] = useState<string | null>(null);

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
    setShowForm(true);
  };

  const openEdit = (v: OpsVariant) => {
    setEditingId(v.id);
    setForm(formFromVariant(v));
    setError(null);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!canManage) return;
    setError(null);
    try {
      if (editingId) {
        await patchMutation.mutateAsync({
          variantId: editingId,
          body: {
            sku: form.sku.trim().toUpperCase(),
            purityCode: form.purityCode,
            metalColor: form.metalColor,
            size: form.size,
            centerStoneCarat: form.centerStoneCarat,
            grossWeightGram: form.grossWeightGram,
            isDefault: form.isDefault,
          },
        });
      } else {
        await createMutation.mutateAsync({
          parentSku,
          sku: form.sku.trim().toUpperCase(),
          purityCode: form.purityCode,
          metalColor: form.metalColor,
          size: form.size,
          centerStoneCarat: form.centerStoneCarat,
          grossWeightGram: form.grossWeightGram,
          initialStockQty: 0,
          isDefault: form.isDefault,
          isActive: true,
        });
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
    }
  };

  const handleToggleActive = async (v: OpsVariant) => {
    setError(null);
    try {
      if (v.isActive) {
        await deactivateMutation.mutateAsync(v.id);
      } else {
        await patchMutation.mutateAsync({ variantId: v.id, body: { isActive: true } });
      }
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Durum güncellenemedi.');
    }
  };

  if (!canManage) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-8 text-center space-y-2">
        <Layers className="w-5 h-5 mx-auto text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">Varyantlar ürün kaydından sonra yönetilir</p>
        <p className="text-xs text-muted-foreground max-w-md mx-auto">
          Önce ürün kartını oluşturun. Satılabilir seçenekler (renk, ayar, ölçü, karat) ayrı{' '}
          <span className="font-mono">ProductVariant</span> kayıtlarıdır; stok bu sekmede yazılmaz.
        </p>
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
            Bu ürünün satılabilir seçenekleri. Stok miktarı Stok &amp; Depo sekmesinde; fiyat Fiyatlandırma
            motorundan üretilir.
          </p>
        </div>
        <Button type="button" size="sm" variant="success" onClick={openCreate}>
          <Plus className="w-3.5 h-3.5" />
          Yeni varyant ekle
        </Button>
      </div>

      {error && (
        <div className="px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs font-medium">
          {error}
        </div>
      )}

      <div className="border border-border rounded-lg overflow-hidden">
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
                  Henüz varyant yok. Katalog ipuçları: {(catalogHints.colors as string[]).join(', ') || '—'}
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
                    <button
                      type="button"
                      className="text-[11px] font-medium text-zinc-700 hover:text-foreground cursor-pointer"
                      onClick={() => void handleToggleActive(v)}
                    >
                      {v.isActive ? 'Pasifleştir' : 'Aktifleştir'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-muted-foreground">
        * Stok sütunu WarehouseStock aggregate özetidir; yazma Stok &amp; Depo sekmesinden yapılır.
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
                {(colorOptions.length ? colorOptions : ['Beyaz', 'Sarı', 'Rose']).map((c) => (
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
                {purityOptions.length === 0 ? (
                  <option value={form.purityCode || ''}>
                    Tanım tablosunda aktif kayıt bulunamadı
                  </option>
                ) : null}
                {purityOptions.map((p) => (
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
                  min={6}
                  max={70}
                  className="font-mono text-right"
                  value={form.size}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, size: Math.max(6, Math.round(Number(e.target.value) || 14)) }))
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
              <Label className="text-[11px]">Katalog gramaj (tahmini)</Label>
              <Input
                type="number"
                step="0.01"
                min={0.01}
                className="font-mono text-right"
                value={form.grossWeightGram}
                onChange={(e) => setForm((f) => ({ ...f, grossWeightGram: e.target.value }))}
              />
            </div>
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

import { useEffect, useState } from 'react';
import { Loader2, Package, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
} from '../../../components/ui';
import { ApiClientError } from '../../../lib/api/client';
import {
  useCreateStockMovementMutation,
  useOpsVariantsQuery,
  useOpsWarehousesQuery,
} from '../../ops/hooks/useOpsQueries';
import type { ProductState } from '../types';

const SELECT_CLS =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

export function QuickStockModal({
  product,
  open,
  onOpenChange,
}: {
  product: ProductState | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const sku = product?.parentSku ?? '';
  const variantsQuery = useOpsVariantsQuery({ parentSku: sku, pageSize: 100, isActive: true }, open && Boolean(sku));
  const warehousesQuery = useOpsWarehousesQuery({ isActive: true, pageSize: 100 });
  const movementMutation = useCreateStockMovementMutation();

  const variants = variantsQuery.data?.items ?? [];
  const warehouses = warehousesQuery.data?.items ?? [];

  const [variantId, setVariantId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [mode, setMode] = useState<'SET' | 'INBOUND' | 'SHIP'>('SET');
  const [qty, setQty] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const effectiveVariant = variants.find((v) => v.id === variantId) ?? variants[0];
  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || '';

  useEffect(() => {
    if (open && product) {
      setError(null);
      setMode('SET');
      setQty(product.stockQty ?? 0);
      setVariantId('');
      setWarehouseId('');
    }
  }, [open, product]);

  useEffect(() => {
    if (mode === 'SET' && effectiveVariant) {
      setQty(effectiveVariant.stockQty);
    }
  }, [effectiveVariant?.id, mode]);

  const submit = async (overrideMode?: 'SET' | 'INBOUND' | 'SHIP', overrideQty?: number) => {
    if (!product || !effectiveVariant || !effectiveWarehouseId) {
      setError('Aktif varyant ve depo bulunamadı.');
      return;
    }
    const targetMode = overrideMode ?? mode;
    const targetQty = overrideQty ?? qty;
    if (targetMode !== 'SET' && targetQty < 1) {
      setError('Adet en az 1 olmalıdır.');
      return;
    }
    if (targetQty < 0) {
      setError('Stok adedi negatif olamaz.');
      return;
    }
    setError(null);
    try {
      await movementMutation.mutateAsync({
        variantId: effectiveVariant.id,
        warehouseId: effectiveWarehouseId,
        movementType: targetMode,
        quantity: targetQty,
        referenceNo: `QUICK-${targetMode}-${Date.now()}`,
      });
      toast.success(
        targetMode === 'SET'
          ? `${effectiveVariant.sku} stoğu ${targetQty} adet olarak güncellendi.`
          : targetMode === 'INBOUND'
            ? `${effectiveVariant.sku} için +${targetQty} stok eklendi.`
            : `${effectiveVariant.sku} için -${targetQty} stok düşüldü.`
      );
      onOpenChange(false);
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : 'Stok güncellenemedi.';
      setError(msg);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Package className="w-4 h-4" />
            Hızlı Stok Yönetimi · {product?.parentSku}
          </DialogTitle>
          <DialogDescription className="text-xs">
            Stok girişi yapabilir, mevcut adedi düzeltebilir veya stoğu sıfırlayabilirsiniz.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-1">
          <div className="space-y-1">
            <Label className="text-xs">Varyant</Label>
            <select
              className={SELECT_CLS}
              value={effectiveVariant?.id ?? ''}
              onChange={(e) => setVariantId(e.target.value)}
            >
              {variants.length === 0 && <option value="">Aktif varyant yok</option>}
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.sku} (Mevcut: {v.stockQty} adet)
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Depo</Label>
            <select
              className={SELECT_CLS}
              value={effectiveWarehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
            >
              {warehouses.length === 0 && <option value="">Aktif depo yok</option>}
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} · {w.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <div className="space-y-1">
              <Label className="text-xs">İşlem</Label>
              <select
                className={SELECT_CLS}
                value={mode}
                onChange={(e) => {
                  const next = e.target.value as 'SET' | 'INBOUND' | 'SHIP';
                  setMode(next);
                  setQty(next === 'SET' ? (effectiveVariant?.stockQty ?? 0) : 1);
                }}
              >
                <option value="SET">Düzelt / Eşitle (=)</option>
                <option value="INBOUND">Stok Ekle (+)</option>
                <option value="SHIP">Stok Düş (-)</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">{mode === 'SET' ? 'Yeni Stok Adedi' : 'Adet'}</Label>
              <Input
                type="number"
                min={mode === 'SET' ? 0 : 1}
                step={1}
                className="h-9 text-right font-mono tabular-nums"
                value={qty}
                onChange={(e) => setQty(Math.max(mode === 'SET' ? 0 : 1, Math.round(Number(e.target.value) || 0)))}
              />
            </div>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}
        </div>

        <DialogFooter className="flex flex-wrap items-center justify-between gap-2 sm:justify-between">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            disabled={movementMutation.isPending || !effectiveVariant || !effectiveWarehouseId}
            onClick={() => void submit('SET', 0)}
          >
            <Trash2 className="w-3.5 h-3.5" />
            Stoğu Sıfırla (0)
          </Button>
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
              Vazgeç
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={movementMutation.isPending || !effectiveVariant || !effectiveWarehouseId}
              onClick={() => void submit()}
            >
              {movementMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Kaydet
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownCircle, ArrowUpCircle, ArrowUpRight, Loader2, Package } from 'lucide-react';
import { toast } from 'sonner';
import { Button, Input, Label } from '../../../components/ui';
import { ApiClientError } from '../../../lib/api/client';
import {
  useCreateStockMovementMutation,
  useOpsStockMovementsQuery,
  useOpsStocksQuery,
  useOpsVariantsQuery,
  useOpsWarehousesQuery,
} from '../../ops/hooks/useOpsQueries';
import { formatTrNumber } from '../../../utils/pricingEngine';

const FIELD_SELECT_CLASS =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1';

export function ProductStockPanel({
  parentSku,
  mode,
  catalogStockQty,
  onInitialStockQtyChange,
  stockStatus,
  onStockStatusChange,
  leadTimeDays,
  onLeadTimeChange,
  ownershipType,
  onOwnershipChange,
  ownershipOptions,
  stockStatusOptions,
}: {
  parentSku: string;
  mode: 'create' | 'edit';
  catalogStockQty: number;
  onInitialStockQtyChange?: (qty: number) => void;
  stockStatus: string;
  onStockStatusChange: (v: string) => void;
  leadTimeDays: number;
  onLeadTimeChange: (v: number) => void;
  ownershipType: string;
  onOwnershipChange: (v: string) => void;
  ownershipOptions: { value: string; label: string }[];
  stockStatusOptions: { value: string; label: string }[];
}) {
  const sku = parentSku.trim().toUpperCase();
  const canLoad = mode === 'edit' && Boolean(sku);
  const stocksQuery = useOpsStocksQuery({ parentSku: sku, pageSize: 100 }, canLoad);
  const variantsQuery = useOpsVariantsQuery({ parentSku: sku, pageSize: 100, isActive: true }, canLoad);
  const warehousesQuery = useOpsWarehousesQuery({ isActive: true, pageSize: 100 });
  const movementsQuery = useOpsStockMovementsQuery(
    canLoad ? { parentSku: sku, pageSize: 20 } : { pageSize: 1 },
    canLoad
  );
  const movementMutation = useCreateStockMovementMutation();

  const stocks = canLoad ? (stocksQuery.data?.items ?? []) : [];
  const variants = canLoad ? (variantsQuery.data?.items ?? []) : [];
  const warehouses = warehousesQuery.data?.items ?? [];
  const movements = canLoad ? (movementsQuery.data?.items ?? []) : [];

  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [selectedWarehouseId, setSelectedWarehouseId] = useState('');
  const [movementType, setMovementType] = useState<'INBOUND' | 'SHIP' | 'SET'>('INBOUND');
  const [moveQty, setMoveQty] = useState<number>(1);
  const [moveRef, setMoveRef] = useState<string>('');
  const [moveError, setMoveError] = useState<string | null>(null);

  const effectiveVariantId = selectedVariantId || variants[0]?.id || '';
  const effectiveWarehouseId = selectedWarehouseId || warehouses[0]?.id || '';

  const handleQuickMovement = async () => {
    if (!canLoad) return;
    setMoveError(null);
    if (!effectiveVariantId) {
      setMoveError('Stok hareketi için aktif bir varyant seçin.');
      return;
    }
    if (!effectiveWarehouseId) {
      setMoveError('Stok hareketi için aktif bir depo seçin.');
      return;
    }
    if (movementType !== 'SET' && (!Number.isInteger(moveQty) || moveQty < 1)) {
      setMoveError('Miktar en az 1 tam sayı olmalıdır.');
      return;
    }
    if (movementType === 'SET' && (!Number.isInteger(moveQty) || moveQty < 0)) {
      setMoveError('Hedef stok 0 veya pozitif bir tam sayı olmalıdır.');
      return;
    }
    const ref = moveRef.trim() || `QUICK-${movementType}-${Date.now()}`;
    try {
      await movementMutation.mutateAsync({
        variantId: effectiveVariantId,
        warehouseId: effectiveWarehouseId,
        movementType,
        quantity: moveQty,
        referenceNo: ref,
      });
      toast.success(
        movementType === 'SET'
          ? `Stok ${moveQty} adet olarak güncellendi.`
          : movementType === 'INBOUND'
            ? `${moveQty} adet stok girişi kaydedildi.`
            : `${moveQty} adet stok çıkışı kaydedildi.`
      );
      setMoveQty(movementType === 'SET' ? moveQty : 1);
      setMoveRef('');
    } catch (err) {
      const msg =
        err instanceof ApiClientError ? err.message : 'Stok hareketi kaydedilemedi.';
      setMoveError(msg);
      toast.error(msg);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Stok &amp; Depo</h3>
          <p className="text-xs text-muted-foreground mt-0.5 max-w-xl">
            Fiziksel stok <span className="font-mono">WarehouseStock</span> kayıtlarıdır (varyant × depo).
            Mevcut ürünlerde stok değişiklikleri denetim izli stok hareketi olarak kaydedilir.
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" asChild>
          <Link to="/ops/stok-depo">
            Stok ekranı
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 p-3 rounded-lg border border-border bg-muted/40">
        {mode === 'create' && (
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-foreground">
              Başlangıç Stoğu (Adet)
            </label>
            <Input
              type="number"
              min={0}
              step={1}
              className="h-9 text-right font-mono tabular-nums"
              value={catalogStockQty}
              onChange={(e) =>
                onInitialStockQtyChange?.(Math.max(0, Math.round(Number(e.target.value) || 0)))
              }
            />
          </div>
        )}
        <div className="space-y-1">
          <label className="text-[11px] font-medium text-muted-foreground">Katalog stok durumu</label>
          <select
            className={FIELD_SELECT_CLASS}
            value={stockStatus}
            onChange={(e) => onStockStatusChange(e.target.value)}
          >
            {stockStatusOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[11px] font-medium text-muted-foreground">Mülkiyet</label>
          <select
            className={FIELD_SELECT_CLASS}
            value={ownershipType}
            onChange={(e) => onOwnershipChange(e.target.value)}
          >
            {ownershipOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[11px] font-medium text-muted-foreground">Teslim (gün)</label>
          <input
            type="number"
            min={0}
            max={90}
            className={`${FIELD_SELECT_CLASS} text-right font-mono`}
            value={leadTimeDays}
            onChange={(e) => onLeadTimeChange(Math.max(0, Math.round(Number(e.target.value) || 0)))}
          />
        </div>
        <div className="sm:col-span-2 lg:col-span-4 text-[11px] text-muted-foreground">
          {mode === 'create'
            ? 'Girilen başlangıç stoğu ürün oluşturulduğunda varsayılan varyant ve merkez depo stok kaydına otomatik işlenir.'
            : (
              <>
                Toplam satılabilir stok:{' '}
                <span className="font-mono font-semibold text-foreground">{catalogStockQty} adet</span>
                {' · '}Gerçek bakiyeler aşağıdaki depo satırlarından gelir.
              </>
            )}
        </div>
      </div>

      {!canLoad ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-6 text-center space-y-1.5">
          <Package className="w-5 h-5 mx-auto text-muted-foreground" />
          <p className="text-sm font-medium">Depo hareket defteri ürün kaydından sonra açılır</p>
          <p className="text-xs text-muted-foreground">
            Yukarıdan başlangıç stok adedini girebilirsiniz; çoklu depo transfer ve giriş/çıkışları ürün kaydedildikten sonra aktifleşir.
          </p>
        </div>
      ) : (
        <>
          {/* Quick stock entry / exit via inventory API */}
          <div className="rounded-lg border border-border bg-card p-3.5 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-xs font-semibold text-foreground">
                Hızlı Stok Giriş / Çıkış (Envanter Hareketi)
              </h4>
              <span className="text-[10px] font-mono text-muted-foreground">
                POST /api/v1/ops/stock-movements
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5 items-end">
              <div className="space-y-1">
                <Label className="text-[11px]">Varyant</Label>
                <select
                  className={FIELD_SELECT_CLASS}
                  value={effectiveVariantId}
                  onChange={(e) => setSelectedVariantId(e.target.value)}
                >
                  {variants.length === 0 && <option value="">Aktif varyant yok</option>}
                  {variants.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.sku} ({v.stockQty} adet)
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <Label className="text-[11px]">Depo</Label>
                <select
                  className={FIELD_SELECT_CLASS}
                  value={effectiveWarehouseId}
                  onChange={(e) => setSelectedWarehouseId(e.target.value)}
                >
                  {warehouses.length === 0 && <option value="">Aktif depo yok</option>}
                  {warehouses.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.code} · {w.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <Label className="text-[11px]">İşlem Tipi</Label>
                <select
                  className={FIELD_SELECT_CLASS}
                  value={movementType}
                  onChange={(e) => {
                    const next = e.target.value as 'INBOUND' | 'SHIP' | 'SET';
                    setMovementType(next);
                    if (next === 'SET') {
                      const currentVar = variants.find((v) => v.id === effectiveVariantId);
                      setMoveQty(currentVar?.stockQty ?? catalogStockQty ?? 0);
                    } else if (moveQty < 1) {
                      setMoveQty(1);
                    }
                  }}
                >
                  <option value="INBOUND">Stok Girişi (+)</option>
                  <option value="SHIP">Stok Çıkışı (-)</option>
                  <option value="SET">Stok Düzelt / Eşitle (=)</option>
                </select>
              </div>

              <div className="space-y-1">
                <Label className="text-[11px]">{movementType === 'SET' ? 'Hedef Adet' : 'Adet'}</Label>
                <Input
                  type="number"
                  min={movementType === 'SET' ? 0 : 1}
                  step={1}
                  className="h-9 text-right font-mono tabular-nums"
                  value={moveQty}
                  onChange={(e) => {
                    const minVal = movementType === 'SET' ? 0 : 1;
                    setMoveQty(Math.max(minVal, Math.round(Number(e.target.value) || 0)));
                  }}
                />
              </div>

              <div className="space-y-1">
                <Label className="text-[11px]">Referans / Açıklama</Label>
                <Input
                  type="text"
                  value={moveRef}
                  onChange={(e) => setMoveRef(e.target.value)}
                  placeholder="Örn. SAYIM-2026"
                  className="h-9 font-mono text-xs"
                />
              </div>
            </div>

            {moveError && (
              <div className="px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs font-medium">
                {moveError}
              </div>
            )}

            <div className="flex justify-end">
              <Button
                type="button"
                size="sm"
                variant={movementType === 'INBOUND' ? 'success' : 'outline'}
                disabled={movementMutation.isPending || variants.length === 0 || warehouses.length === 0}
                onClick={() => void handleQuickMovement()}
              >
                {movementMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : movementType === 'INBOUND' ? (
                  <ArrowUpCircle className="w-3.5 h-3.5" />
                ) : (
                  <ArrowDownCircle className="w-3.5 h-3.5" />
                )}
                {movementType === 'SET'
                  ? 'Stok Düzeltmesini Kaydet'
                  : movementType === 'INBOUND'
                    ? 'Stok Girişi Kaydet'
                    : 'Stok Çıkışı Kaydet'}
              </Button>
            </div>
          </div>

          <div className="border border-border rounded-lg overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-muted/60 text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Varyant</th>
                  <th className="px-3 py-2 font-medium">Depo</th>
                  <th className="px-3 py-2 font-medium text-right">Fiziksel</th>
                  <th className="px-3 py-2 font-medium text-right">Rezerve</th>
                  <th className="px-3 py-2 font-medium text-right">Satılabilir</th>
                  <th className="px-3 py-2 font-medium">Renk / Ölçü</th>
                </tr>
              </thead>
              <tbody>
                {stocksQuery.isLoading && (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">
                      Yükleniyor…
                    </td>
                  </tr>
                )}
                {!stocksQuery.isLoading && stocks.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">
                      Bu ürün için depo stok kaydı yok. Yukarıdaki formdan ilk stok girişini yapabilirsiniz.
                    </td>
                  </tr>
                )}
                {stocks.map((s) => (
                  <tr key={s.id} className="border-t border-border">
                    <td className="px-3 py-2 font-mono">{s.variantSku}</td>
                    <td className="px-3 py-2">
                      <span className="font-mono">{s.warehouseCode}</span>
                      <span className="text-muted-foreground"> · {s.warehouseName}</span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{s.quantity}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{s.reservedQty}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums font-medium">
                      {s.availableQty}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {s.metalColor} / {s.size}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-foreground mb-2">Son stok hareketleri</h4>
            <div className="border border-border rounded-lg overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead className="bg-muted/60 text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">Tarih</th>
                    <th className="px-3 py-2 font-medium">Tip</th>
                    <th className="px-3 py-2 font-medium">Varyant</th>
                    <th className="px-3 py-2 font-medium">Depo</th>
                    <th className="px-3 py-2 font-medium text-right">Δ</th>
                    <th className="px-3 py-2 font-medium">Referans</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">
                        Hareket yok
                      </td>
                    </tr>
                  )}
                  {movements.map((m) => (
                    <tr key={m.id} className="border-t border-border">
                      <td className="px-3 py-2 font-mono text-muted-foreground whitespace-nowrap">
                        {new Date(m.createdAt).toLocaleString('tr-TR')}
                      </td>
                      <td className="px-3 py-2">{m.movementType}</td>
                      <td className="px-3 py-2 font-mono">{m.variantSku ?? '—'}</td>
                      <td className="px-3 py-2 font-mono">{m.warehouseCode ?? '—'}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">
                        {m.quantityDelta > 0 ? '+' : ''}
                        {formatTrNumber(m.quantityDelta, 0)}
                      </td>
                      <td className="px-3 py-2 font-mono text-muted-foreground">{m.referenceNo}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

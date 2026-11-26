import { Link } from 'react-router-dom';
import { ArrowUpRight, Package } from 'lucide-react';
import { Button } from '../../../components/ui';
import {
  useOpsStockMovementsQuery,
  useOpsStocksQuery,
} from '../../ops/hooks/useOpsQueries';
import { formatTrNumber } from '../../../utils/pricingEngine';

export function ProductStockPanel({
  parentSku,
  mode,
  catalogStockQty,
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
  const movementsQuery = useOpsStockMovementsQuery(
    canLoad ? { parentSku: sku, pageSize: 20 } : { pageSize: 1 },
    canLoad
  );

  const stocks = canLoad ? (stocksQuery.data?.items ?? []) : [];
  const movements = canLoad ? (movementsQuery.data?.items ?? []) : [];

  const FIELD_SELECT_CLASS =
    'flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1';

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Stok &amp; Depo</h3>
          <p className="text-xs text-muted-foreground mt-0.5 max-w-xl">
            Fiziksel stok <span className="font-mono">WarehouseStock</span> kayıtlarıdır (varyant × depo).
            Ürün kartındaki stok adedi yalnızca aggregate özet; buradan yazılmaz.
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" asChild>
          <Link to="/ops/stok-depo">
            Stok ekranı
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-lg border border-border bg-muted/40">
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
        <div className="sm:col-span-3 text-[11px] text-muted-foreground">
          Aggregate satılabilir: <span className="font-mono text-foreground">{catalogStockQty}</span>
          {' · '}
          Gerçek bakiyeler aşağıdaki depo satırlarından gelir.
        </div>
      </div>

      {!canLoad ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center space-y-2">
          <Package className="w-5 h-5 mx-auto text-muted-foreground" />
          <p className="text-sm font-medium">Stok satırları ürün kaydından sonra görünür</p>
          <p className="text-xs text-muted-foreground">
            Aynı varyantın birden fazla depoda stoğu olabilir; miktar Product/ProductVariant tablosuna
            yazılmaz.
          </p>
        </div>
      ) : (
        <>
          <div className="border border-border rounded-lg overflow-hidden">
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
                      Bu ürün için depo stok kaydı yok. Giriş için Stok &amp; Depo ekranını kullanın.
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
            <div className="border border-border rounded-lg overflow-hidden">
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
                      <td className="px-3 py-2 font-mono text-muted-foreground">
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

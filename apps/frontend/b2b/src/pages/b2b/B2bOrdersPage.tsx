import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ClipboardList, Copy, History, RotateCcw, Search } from 'lucide-react';
import {
  PortalDataCard,
  PortalOrderCardsSkeleton,
  PortalPageHeader,
} from '@taragold/shared/components/portal';
import { Badge, Button, Input } from '@taragold/shared/components/ui';
import {
  useB2bOrdersQuery,
  useCommerceUI,
  useReorderB2bOrderMutation,
} from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import type { B2bOrderRecord } from '@taragold/shared/features/commerce/types';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';

const STATUS_LABELS: Record<B2bOrderRecord['status'], string> = {
  PROFORMA_ONAYLANDI: 'Proforma Onaylandı',
  ATOLYE_PLANLANDI: 'Atölye Planlandı',
  SEVK_HAZIR: 'Sevke Hazır',
  IPTAL_EDILDI: 'İptal Edildi',
  IADE_EDILDI: 'İade Edildi',
};

const STATUS_BADGE: Record<
  B2bOrderRecord['status'],
  { variant: 'default' | 'secondary' | 'destructive' | 'outline'; className?: string }
> = {
  PROFORMA_ONAYLANDI: { variant: 'outline', className: 'border-blue-200 text-blue-800 bg-blue-50' },
  ATOLYE_PLANLANDI: { variant: 'outline', className: 'border-amber-200 text-amber-900 bg-amber-50' },
  SEVK_HAZIR: { variant: 'outline', className: 'border-emerald-200 text-emerald-800 bg-emerald-50' },
  IPTAL_EDILDI: { variant: 'destructive' },
  IADE_EDILDI: { variant: 'destructive' },
};

const SETTLEMENT_LABELS: Record<B2bOrderRecord['settlementMethod'], string> = {
  HAS_PLUS_CURRENCY: 'Has Altın + İşçilik/Taş',
  FX_CASH: 'Döviz Nakit / Havale',
  CONSIGNMENT: 'Konsinye / Emanet',
  OPEN_ACCOUNT: 'Cari Hesap / Vadeli',
};

export function B2bOrdersPage() {
  const ordersQuery = useB2bOrdersQuery();
  const reorderMutation = useReorderB2bOrderMutation();
  const { setB2bOrderOpen } = useCommerceUI();

  const [statusFilter, setStatusFilter] = useState<'ALL' | B2bOrderRecord['status']>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedNo, setCopiedNo] = useState<string | null>(null);
  const [reorderedNo, setReorderedNo] = useState<string | null>(null);

  const orders = ordersQuery.data ?? [];

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLocaleLowerCase('tr-TR');
    return orders.filter((o) => {
      if (statusFilter !== 'ALL' && o.status !== statusFilter) return false;
      if (!q) return true;
      return (
        o.orderNo.toLowerCase().includes(q) ||
        o.dealerName.toLocaleLowerCase('tr-TR').includes(q) ||
        o.dealerCode.toLowerCase().includes(q) ||
        o.branchName.toLocaleLowerCase('tr-TR').includes(q)
      );
    });
  }, [orders, statusFilter, searchQuery]);

  const handleCopyProforma = (order: B2bOrderRecord) => {
    const text = [
      `TARA GOLD B2B PROFORMA — ${order.orderNo}`,
      `Firma: ${order.dealerName} (${order.dealerCode}) · Şube: ${order.branchName}`,
      `Hesaplaşma: ${SETTLEMENT_LABELS[order.settlementMethod]}`,
      `Toplam: ${order.totalPieces} ad · ${formatTrNumber(order.totalGrossGram, 2)} gr brüt · ${formatTrNumber(order.totalHasGoldGram ?? 0, 4)} gr Has`,
      `Tutar: $${formatTrNumber(order.totalWholesaleUsd, 2)} (${formatTrNumber(order.totalWholesaleTry, 0)} TL)`,
    ].join('\n');
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopiedNo(order.orderNo);
    window.setTimeout(() => setCopiedNo(null), 1800);
  };

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Organizasyon Bazlı İzole Sipariş Kayıtları"
        title={`Sipariş Geçmişi (${orders.length})`}
        actions={
          <>
            <div className="relative w-full sm:w-48">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Fiş no, firma..."
                className="h-9 pl-8 text-xs w-full"
                aria-label="Sipariş ara"
              />
            </div>
            <select
              aria-label="Durum filtresi"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'ALL' | B2bOrderRecord['status'])}
              className="h-9 px-3 rounded-md border border-border bg-background text-xs text-foreground"
            >
              <option value="ALL">Tüm Durumlar ({orders.length})</option>
              <option value="PROFORMA_ONAYLANDI">Proforma Onaylandı</option>
              <option value="ATOLYE_PLANLANDI">Atölye Planlandı</option>
              <option value="SEVK_HAZIR">Sevke Hazır</option>
              <option value="IPTAL_EDILDI">İptal Edildi</option>
              <option value="IADE_EDILDI">İade Edildi</option>
            </select>
            <Button variant="outline" size="sm" asChild>
              <Link to="/b2b/siparis-fisi">
                <ClipboardList className="w-3.5 h-3.5" />
                Sipariş Fişi
              </Link>
            </Button>
          </>
        }
      />

      {ordersQuery.isLoading ? (
        <PortalOrderCardsSkeleton count={3} />
      ) : filtered.length === 0 ? (
        <PortalDataCard contentClassName="py-16 px-6 text-center space-y-3">
          <History className="w-9 h-9 text-muted-foreground/40 mx-auto" />
          <div className="text-base font-semibold text-foreground">
            {orders.length === 0
              ? 'Henüz sipariş kaydı yok'
              : 'Bu filtrede sipariş kaydı bulunmuyor'}
          </div>
          <Button size="sm" variant="outline" asChild>
            <Link to="/b2b/katalog">Toptan Kataloğa Dön</Link>
          </Button>
        </PortalDataCard>
      ) : (
        <div className="space-y-4">
          {filtered.map((order) => (
            <PortalDataCard key={order.orderNo} contentClassName="p-5 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="font-mono text-sm font-semibold text-foreground">
                      {order.orderNo}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(order.createdAt).toLocaleString('tr-TR')}
                    </span>
                    <Badge
                      variant={STATUS_BADGE[order.status].variant}
                      className={STATUS_BADGE[order.status].className}
                    >
                      {STATUS_LABELS[order.status]}
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {order.branchName} · {SETTLEMENT_LABELS[order.settlementMethod]} · Kur:{' '}
                    <span className="font-mono">{order.snapshotId}</span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleCopyProforma(order)}
                  >
                    {copiedNo === order.orderNo ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-700" />
                        Kopyalandı
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        Proforma
                      </>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      await reorderMutation.mutateAsync(order.orderNo);
                      setReorderedNo(order.orderNo);
                      window.setTimeout(() => setReorderedNo(null), 1600);
                      setB2bOrderOpen(true);
                    }}
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    {reorderedNo === order.orderNo ? 'Aktarıldı' : 'Tekrar Sipariş'}
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-muted/40 rounded-md p-3.5 text-xs font-mono tabular-nums">
                <div>
                  <div className="font-sans text-[11px] text-muted-foreground">Toplam Adet / Brüt</div>
                  <div className="font-semibold text-foreground mt-0.5">
                    {order.totalPieces} ad · {formatTrNumber(order.totalGrossGram, 2)} gr
                  </div>
                </div>
                <div>
                  <div className="font-sans text-[11px] text-muted-foreground">Fire Dahil Has</div>
                  <div className="font-semibold text-foreground mt-0.5">
                    {formatTrNumber(order.totalHasGoldGram ?? 0, 4)} gr
                  </div>
                </div>
                <div>
                  <div className="font-sans text-[11px] text-muted-foreground">İşçilik + Taş</div>
                  <div className="font-semibold text-foreground mt-0.5">
                    ${formatTrNumber(order.totalLaborAndStoneUsd ?? 0, 2)}
                  </div>
                </div>
                <div>
                  <div className="font-sans text-[11px] text-muted-foreground">Toptan Değer</div>
                  <div className="font-semibold text-foreground mt-0.5">
                    ${formatTrNumber(order.totalWholesaleUsd, 2)}
                  </div>
                </div>
              </div>

              <div className="divide-y divide-border text-xs">
                {order.lines.map((line) => (
                  <div
                    key={line.id}
                    className="py-2 flex flex-wrap items-center justify-between gap-2"
                  >
                    <span className="text-muted-foreground">
                      <strong className="text-foreground">{line.qty}×</strong>{' '}
                      <span className="font-sku text-muted-foreground">{line.sku}</span> · {line.title} (
                      {line.sizeUnitLabel} {line.size}) ·{' '}
                      {line.supplyType === 'STOCK' ? 'Stok' : 'Atölye'}
                    </span>
                    <span className="font-mono tabular-nums text-foreground">
                      {formatTrNumber((line.unitFireIncludedFineGram ?? 0) * line.qty, 4)} gr Has · $
                      {formatTrNumber((line.unitLaborAndStoneUsd ?? 0) * line.qty, 2)}
                    </span>
                  </div>
                ))}
              </div>
            </PortalDataCard>
          ))}
        </div>
      )}
    </div>
  );
}

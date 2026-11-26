import { Link } from 'react-router-dom';
import {
  ArrowRight,
  ClipboardList,
  Gem,
  History,
  RotateCcw,
  Scale,
} from 'lucide-react';
import {
  PortalDataCard,
  PortalPageHeader,
  PortalStatsSkeleton,
  PortalTableSkeleton,
} from '@taragold/shared/components/portal';
import {
  Button,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import { useActiveProductMetrics } from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import {
  useB2bDraftQuery,
  useB2bOrdersQuery,
  useCommerceUI,
  useReorderB2bOrderMutation,
} from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';

const STATUS_LABELS: Record<string, string> = {
  PROFORMA_ONAYLANDI: 'Proforma Onaylandı',
  ATOLYE_PLANLANDI: 'Atölye Planlandı',
  SEVK_HAZIR: 'Sevke Hazır',
  IPTAL_EDILDI: 'İptal Edildi',
  IADE_EDILDI: 'İade Edildi',
};

export function B2bDashboardPage() {
  const { activeOrganization, activeBranch } = useAuth();
  const { products, rates } = useActiveProductMetrics();
  const draftQuery = useB2bDraftQuery();
  const ordersQuery = useB2bOrdersQuery();
  const reorderMutation = useReorderB2bOrderMutation();
  const { setB2bOrderOpen } = useCommerceUI();

  const lines = draftQuery.data?.lines ?? [];
  const orders = ordersQuery.data ?? [];
  const dealer = draftQuery.data?.dealer;

  const creditLimitUsd = Number(activeOrganization?.creditLimitUsd ?? dealer?.creditLimitUsd ?? 0);
  const usedCreditUsd = Number(activeOrganization?.usedCreditUsd ?? dealer?.usedCreditUsd ?? 0);
  const remainingCreditUsd = Math.max(0, creditLimitUsd - usedCreditUsd);
  const creditPct = creditLimitUsd > 0 ? Math.min(100, (usedCreditUsd / creditLimitUsd) * 100) : 0;

  const hasLimitGram = Number(activeOrganization?.hasLimitGram ?? dealer?.hasLimitGram ?? 0);
  const usedHasGram = Number(activeOrganization?.usedHasGram ?? dealer?.usedHasGram ?? 0);
  const remainingHasGram = Math.max(0, hasLimitGram - usedHasGram);
  const hasPct = hasLimitGram > 0 ? Math.min(100, (usedHasGram / hasLimitGram) * 100) : 0;

  const openOrders = orders.filter(
    (o) => o.status !== 'IPTAL_EDILDI' && o.status !== 'IADE_EDILDI' && o.status !== 'SEVK_HAZIR'
  );
  const draftPieces = lines.reduce((sum, l) => sum + l.qty, 0);
  const draftHasGram = lines.reduce((sum, l) => sum + (l.unitFireIncludedFineGram ?? 0) * l.qty, 0);
  const draftWholesaleUsd = lines.reduce((sum, l) => sum + l.unitWholesaleUsd * l.qty, 0);

  const commerceLoading = draftQuery.isLoading || ordersQuery.isLoading;

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow={`${activeOrganization?.name ?? 'Bayi Hesabı'} · ${activeBranch?.name ?? 'Aktif Şube'}`}
        title="Bayi Operasyon Özeti"
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link to="/b2b/katalog">
                <Gem className="w-3.5 h-3.5" />
                Toptan Katalog ({products.length})
              </Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link to="/b2b/siparis-fisi">
                <ClipboardList className="w-3.5 h-3.5" />
                Sipariş Fişi ({draftPieces} ad)
              </Link>
            </Button>
            <Button size="sm" onClick={() => setB2bOrderOpen(true)}>
              Proforma Onayla
            </Button>
          </>
        }
      />

      {commerceLoading ? (
        <PortalStatsSkeleton count={4} />
      ) : (
      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Card className="shadow-none">
          <CardContent className="p-5 space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Açık Toptan Siparişler</div>
            <div className="font-mono text-2xl font-semibold text-foreground tabular-nums">
              {openOrders.length}
            </div>
            <div className="text-[11px] text-muted-foreground">
              Toplam {orders.length} geçmiş sipariş kaydı
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="p-5 space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Aktif Sipariş Fişi (Taslak)</div>
            <div className="font-mono text-2xl font-semibold text-foreground tabular-nums">
              {draftPieces} adet
            </div>
            <div className="font-mono text-[11px] text-muted-foreground tabular-nums">
              {formatTrNumber(draftHasGram, 3)} gr Has · ${formatTrNumber(draftWholesaleUsd, 2)}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="p-5 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-muted-foreground">Kalan Has Altın Limiti</span>
              <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                %{formatTrNumber(hasPct, 0)} dolu
              </span>
            </div>
            <div className="font-mono text-2xl font-semibold text-foreground tabular-nums">
              {formatTrNumber(remainingHasGram, 2)} gr
            </div>
            <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-foreground/80" style={{ width: `${hasPct}%` }} />
            </div>
            <div className="font-mono text-[11px] text-muted-foreground tabular-nums">
              Açık: {formatTrNumber(usedHasGram, 2)} / {formatTrNumber(hasLimitGram, 2)} gr Has
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="p-5 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-muted-foreground">Kalan Cari Kredi Limiti</span>
              <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                %{formatTrNumber(creditPct, 0)} dolu
              </span>
            </div>
            <div className="font-mono text-2xl font-semibold text-foreground tabular-nums">
              ${formatTrNumber(remainingCreditUsd, 0)}
            </div>
            <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-foreground" style={{ width: `${creditPct}%` }} />
            </div>
            <div className="font-mono text-[11px] text-muted-foreground tabular-nums">
              Kullanılan: ${formatTrNumber(usedCreditUsd, 0)} / ${formatTrNumber(creditLimitUsd, 0)}
            </div>
          </CardContent>
        </Card>
      </section>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-8">
          <PortalDataCard
            title="Son Bayi Siparişleri"
            toolbar={
              <Link
                to="/b2b/siparisler"
                className="text-xs font-medium text-muted-foreground hover:underline inline-flex items-center gap-1"
              >
                Tüm Geçmiş <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          >
            <p className="px-4 py-2 text-xs text-muted-foreground border-b border-border">
              Tek tıkla eski sipariş kalemlerini aktif fişinize aktarabilirsiniz.
            </p>
            {ordersQuery.isLoading ? (
              <PortalTableSkeleton rows={5} />
            ) : orders.length === 0 ? (
              <div className="p-10 text-center text-xs text-muted-foreground space-y-3">
                <History className="w-7 h-7 text-muted-foreground/40 mx-auto" />
                <p>Firmanıza ait tamamlanmış B2B sipariş kaydı bulunmuyor.</p>
                <Button variant="outline" size="sm" asChild>
                  <Link to="/b2b/katalog">Toptan Kataloğu İncele</Link>
                </Button>
              </div>
            ) : (
              <Table className="text-xs">
                <TableHeader className="bg-muted/40">
                  <TableRow>
                    <TableHead className="px-4 uppercase text-[11px]">Fiş No</TableHead>
                    <TableHead className="px-4 uppercase text-[11px]">Tarih</TableHead>
                    <TableHead className="px-4 uppercase text-[11px]">Adet / Has</TableHead>
                    <TableHead className="px-4 text-right uppercase text-[11px]">Toptan Tutar</TableHead>
                    <TableHead className="px-4 uppercase text-[11px]">Durum</TableHead>
                    <TableHead className="px-4 text-right uppercase text-[11px]">İşlem</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {orders.slice(0, 6).map((order) => (
                    <TableRow key={order.orderNo}>
                      <TableCell className="px-4 font-mono font-semibold text-foreground">
                        {order.orderNo}
                      </TableCell>
                      <TableCell className="px-4 text-muted-foreground tabular-nums">
                        {new Date(order.createdAt).toLocaleDateString('tr-TR')}
                      </TableCell>
                      <TableCell className="px-4 font-mono tabular-nums text-muted-foreground">
                        {order.totalPieces} ad · {formatTrNumber(order.totalHasGoldGram ?? 0, 3)} gr
                      </TableCell>
                      <TableCell className="px-4 font-mono font-semibold text-foreground text-right tabular-nums">
                        ${formatTrNumber(order.totalWholesaleUsd, 2)}
                      </TableCell>
                      <TableCell className="px-4 text-muted-foreground">
                        {STATUS_LABELS[order.status] ?? order.status}
                      </TableCell>
                      <TableCell className="px-4 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={async () => {
                            await reorderMutation.mutateAsync(order.orderNo);
                            setB2bOrderOpen(true);
                          }}
                        >
                          <RotateCcw className="w-3 h-3" />
                          Tekrarla
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </PortalDataCard>
        </div>

        <div className="lg:col-span-4 space-y-4">
          <Card className="bg-zinc-950 text-zinc-50 border-zinc-800 shadow-none">
            <CardContent className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-xs font-medium text-zinc-300">Canlı Kur &amp; Maden Tahtası</div>
              <span className="font-mono text-[10px] text-zinc-300">{rates.snapshotId}</span>
            </div>

            <div className="space-y-2.5 text-xs font-mono tabular-nums">
              <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
                <span className="text-zinc-400 font-sans">Has Altın (995/999)</span>
                <span className="text-base font-semibold text-zinc-300">
                  {formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-400 font-sans">USD / TRY Satış</span>
                <span className="font-semibold text-white">
                  {formatTrNumber(rates.liveUsdSell, 4)} TL
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-400 font-sans">EUR / TRY Satış</span>
                <span className="font-semibold text-white">
                  {formatTrNumber(rates.liveEurSell, 4)} TL
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-400 font-sans">Has Altın (USD/gr)</span>
                <span className="text-zinc-200">
                  $
                  {formatTrNumber(
                    rates.liveUsdSell > 0 ? rates.liveHasGoldTrySell / rates.liveUsdSell : 0,
                    2
                  )}
                </span>
              </div>
            </div>
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardContent className="p-5 space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Hızlı İşlemler
              </h3>
              <div className="space-y-2">
                <Link
                  to="/b2b/katalog"
                  className="flex items-center justify-between p-3 rounded-md border border-border hover:bg-muted/50 transition-colors text-xs font-medium text-foreground"
                >
                  <span className="flex items-center gap-2">
                    <Gem className="w-4 h-4 text-muted-foreground" />
                    Asorti &amp; Toptan Sipariş Oluştur
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
                </Link>
                <Link
                  to="/b2b/siparis-fisi"
                  className="flex items-center justify-between p-3 rounded-md border border-border hover:bg-muted/50 transition-colors text-xs font-medium text-foreground"
                >
                  <span className="flex items-center gap-2">
                    <ClipboardList className="w-4 h-4 text-muted-foreground" />
                    Taslak Fişi Düzenle ({draftPieces} adet)
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
                </Link>
                <Link
                  to="/b2b/cari-hesap"
                  className="flex items-center justify-between p-3 rounded-md border border-border hover:bg-muted/50 transition-colors text-xs font-medium text-foreground"
                >
                  <span className="flex items-center gap-2">
                    <Scale className="w-4 h-4 text-muted-foreground" />
                    Cari Hesap &amp; Limit Durumu
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}

import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Calculator,
  ClipboardCheck,
  Hammer,
  Package,
} from 'lucide-react';
import { PortalDataCard, PortalPageHeader, PortalStat } from '@taragold/shared/components/portal';
import {
  Badge,
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
import { useActiveProductMetrics } from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import {
  useOpsB2bOrdersQuery,
  useOpsB2cOrdersQuery,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { computeJewelryMetrics, formatTrNumber } from '@taragold/shared/utils/pricingEngine';

export function OpsDashboardPage() {
  const { products, rates } = useActiveProductMetrics();
  const b2bOrdersQuery = useOpsB2bOrdersQuery({ pageSize: 100 });
  const b2cOrdersQuery = useOpsB2cOrdersQuery({ pageSize: 100 });

  const b2bOrders = b2bOrdersQuery.data?.items ?? [];
  const b2cOrders = b2cOrdersQuery.data?.items ?? [];

  const stats = useMemo(() => {
    const pendingB2b = b2bOrders.filter((o) => o.status === 'PROFORMA_ONAYLANDI').length;
    const pendingB2c = b2cOrders.filter((o) => o.status === 'ONAYLANDI').length;
    const workshopB2b = b2bOrders.filter((o) => o.status === 'ATOLYE_PLANLANDI').length;
    const workshopB2c = b2cOrders.filter((o) => o.status === 'ATOLYE_URETIMDE').length;

    const totalVariants = products.reduce(
      (sum, p) => sum + (p.variants && p.variants.length > 0 ? p.variants.length : 1),
      0
    );
    const lowStockProducts = products.filter(
      (p) => p.stockStatus === 'Tükendi' || (p.stockQty ?? 0) <= 2
    );

    const b2bRevenueUsd = b2bOrders
      .filter((o) => o.status !== 'IPTAL_EDILDI' && o.status !== 'IADE_EDILDI')
      .reduce((sum, o) => sum + o.totalWholesaleUsd, 0);
    const b2cRevenueTry = b2cOrders
      .filter((o) => o.status !== 'IPTAL_EDILDI' && o.status !== 'IADE_EDILDI')
      .reduce((sum, o) => sum + o.grandTotalTry, 0);

    return {
      totalOrders: b2bOrders.length + b2cOrders.length,
      pendingOrders: pendingB2b + pendingB2c,
      workshopOrders: workshopB2b + workshopB2c,
      totalVariants,
      lowStockProducts,
      b2bRevenueUsd,
      b2cRevenueTry,
    };
  }, [b2bOrders, b2cOrders, products]);

  const recipeSnapshot = useMemo(
    () =>
      products.slice(0, 6).map((p) => ({
        product: p,
        metrics: computeJewelryMetrics(p, rates),
      })),
    [products, rates]
  );

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Canlı Katalog, Sipariş Operasyonu &amp; Fiyatlandırma Özeti"
        title="OPS Genel Bakış"
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link to="/ops/urunler">
                <Package className="w-3.5 h-3.5" />
                Ürün Yönetimi ({products.length})
              </Link>
            </Button>
            <Button size="sm" asChild>
              <Link to="/ops/fiyat-motoru">
                <Calculator className="w-3.5 h-3.5" />
                Fiyat Motoru &amp; Kur
              </Link>
            </Button>
          </>
        }
      />

      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <PortalStat
          label="Toplam Sipariş (B2B + B2C)"
          value={stats.totalOrders}
          icon={<ClipboardCheck className="w-4 h-4 text-muted-foreground" />}
          hint={
            <>
              {b2bOrders.length} B2B · {b2cOrders.length} B2C ·{' '}
              <Badge variant="outline" className="ml-0.5">
                {stats.pendingOrders} onay/işlem bekleyen
              </Badge>
            </>
          }
        />
        <PortalStat
          label="Atölye / Üretim Kuyruğu"
          value={stats.workshopOrders}
          icon={<Hammer className="w-4 h-4 text-muted-foreground" />}
          hint={
            <Link
              to="/ops/uretim"
              className="inline-flex items-center gap-1 font-medium text-muted-foreground hover:underline"
            >
              Üretim kuyruğuna git <ArrowRight className="w-3 h-3" />
            </Link>
          }
        />
        <PortalStat
          label="Stok Uyarıları"
          value={stats.lowStockProducts.length}
          icon={<AlertTriangle className="w-4 h-4 text-muted-foreground" />}
          hint={`${products.length} model · ${stats.totalVariants} varyant kayıtlı`}
        />
        <PortalStat
          label="Aktif Sipariş Hacmi"
          value={
            <>
              ${formatTrNumber(stats.b2bRevenueUsd, 0)}{' '}
              <span className="text-xs font-sans font-normal text-muted-foreground">B2B</span>
            </>
          }
          valueClassName="text-lg"
          hint={`${formatTrNumber(stats.b2cRevenueTry, 0)} TL B2C`}
        />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-7 space-y-6">
          <PortalDataCard
            title="Fiyatlama Reçetesi Durumu"
            toolbar={
              <Link
                to="/ops/receteler"
                className="text-xs font-medium text-muted-foreground hover:underline inline-flex items-center gap-1"
              >
                Tüm Reçeteler <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          >
            <p className="px-4 py-2 text-xs text-muted-foreground border-b border-border">
              Aktif snapshot ({rates.snapshotId}) üzerinden canlı B2B / B2C çıkışları.
            </p>
            <Table className="text-xs">
              <TableHeader className="bg-muted/40">
                <TableRow>
                  <TableHead className="px-4 uppercase text-[11px]">Parent SKU</TableHead>
                  <TableHead className="px-4 uppercase text-[11px]">Mod / LC</TableHead>
                  <TableHead className="px-4 text-right uppercase text-[11px]">B2B Net</TableHead>
                  <TableHead className="px-4 text-right uppercase text-[11px]">B2C Net (TL)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recipeSnapshot.map(({ product, metrics }) => (
                  <TableRow key={product.parentSku}>
                    <TableCell className="px-4">
                      <div className="font-sku font-semibold text-foreground">{product.parentSku}</div>
                      <div className="text-[11px] text-muted-foreground truncate max-w-[220px]">
                        {product.title}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 font-mono text-muted-foreground">
                      Model {product.pricingMode} · {product.ledger?.lcCurrency ?? product.pricingCurrency ?? 'TRY'}
                    </TableCell>
                    <TableCell className="px-4 text-right font-mono tabular-nums text-foreground">
                      {formatTrNumber(metrics.finalB2bPriceCurrency, 2)} {product.pricingCurrency}
                    </TableCell>
                    <TableCell className="px-4 text-right font-mono font-semibold tabular-nums text-foreground">
                      {formatTrNumber(metrics.discountedB2cPriceTry, 0)} TL
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </PortalDataCard>

          <PortalDataCard
            title="Kritik Stok &amp; Siparişe Özel Modeller"
            toolbar={
              <Link to="/ops/stok-depo" className="text-xs font-medium text-muted-foreground hover:underline">
                Stok &amp; Depo
              </Link>
            }
          >
            <div className="divide-y divide-border text-xs">
              {stats.lowStockProducts.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground">
                  Kritik stok uyarısı veren ürün bulunmuyor.
                </div>
              ) : (
                stats.lowStockProducts.slice(0, 6).map((p) => (
                  <div key={p.parentSku} className="px-5 py-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-sku font-semibold text-foreground">{p.parentSku}</div>
                      <div className="text-muted-foreground truncate">{p.title}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <Badge variant={p.stockStatus === 'Tükendi' ? 'destructive' : 'outline'}>
                        {p.stockStatus}
                      </Badge>
                      <div className="font-mono text-[11px] text-muted-foreground tabular-nums mt-1">
                        Stok: {p.stockQty ?? 0} · {p.warehouseLocation ?? 'Merkez'}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </PortalDataCard>
        </div>

        <div className="xl:col-span-5 space-y-6">
          <Card className="bg-zinc-950 text-zinc-50 border-zinc-800 shadow-none">
            <CardContent className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs text-zinc-400">Aktif Kur Snapshot</div>
                  <div className="font-mono text-sm font-semibold text-zinc-200 mt-0.5">
                    {rates.snapshotId}
                  </div>
                </div>
                <Button size="sm" variant="secondary" className="h-8 text-xs" asChild>
                  <Link to="/ops/fiyat-motoru">Kurları Düzenle</Link>
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-zinc-800 font-mono tabular-nums text-xs">
                <div>
                  <div className="font-sans text-[11px] text-zinc-400">Has 995</div>
                  <div className="text-base font-semibold text-zinc-50 mt-0.5">
                    {formatTrNumber(rates.liveHasGoldTrySell, 2)}
                  </div>
                </div>
                <div>
                  <div className="font-sans text-[11px] text-zinc-400">USD / TRY</div>
                  <div className="text-base font-semibold text-zinc-50 mt-0.5">
                    {formatTrNumber(rates.liveUsdSell, 2)}
                  </div>
                </div>
                <div>
                  <div className="font-sans text-[11px] text-zinc-400">EUR / TRY</div>
                  <div className="text-base font-semibold text-zinc-50 mt-0.5">
                    {formatTrNumber(rates.liveEurSell, 2)}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <PortalDataCard
            title="Son Sipariş Hareketleri"
            toolbar={
              <Link to="/ops/siparisler" className="text-xs font-medium text-muted-foreground hover:underline">
                Yönet
              </Link>
            }
          >
            <div className="divide-y divide-border text-xs">
              {b2bOrders.slice(0, 4).map((o) => (
                <div key={o.orderNo} className="px-5 py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-mono font-semibold text-foreground">[B2B] {o.orderNo}</div>
                    <div className="text-muted-foreground truncate">{o.dealerName}</div>
                  </div>
                  <div className="text-right shrink-0 font-mono tabular-nums">
                    <div className="font-semibold text-foreground">
                      ${formatTrNumber(o.totalWholesaleUsd, 2)}
                    </div>
                    <div className="font-sans text-[11px] text-muted-foreground">{o.status}</div>
                  </div>
                </div>
              ))}
              {b2cOrders.slice(0, 4).map((o) => (
                <div key={o.orderNo} className="px-5 py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-mono font-semibold text-foreground">[B2C] {o.orderNo}</div>
                    <div className="text-muted-foreground truncate">{o.customerName}</div>
                  </div>
                  <div className="text-right shrink-0 font-mono tabular-nums">
                    <div className="font-semibold text-foreground">
                      {formatTrNumber(o.grandTotalTry, 0)} TL
                    </div>
                    <div className="font-sans text-[11px] text-muted-foreground">{o.status}</div>
                  </div>
                </div>
              ))}
              {b2bOrders.length === 0 && b2cOrders.length === 0 && (
                <div className="p-6 text-center text-muted-foreground">Henüz sipariş hareketi yok.</div>
              )}
            </div>
          </PortalDataCard>
        </div>
      </section>
    </div>
  );
}
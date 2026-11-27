import { useEffect, useState } from 'react';
import { Eye, Search } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import {
  useCustomer360DashboardQuery,
  useOpsCartsQuery,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { opsService } from '@taragold/shared/features/ops/services/opsService';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <PortalDataCard title={label}>
      <div className="px-4 py-5 text-2xl font-semibold tabular-nums text-foreground">{value}</div>
    </PortalDataCard>
  );
}

type CartDetailData = Awaited<ReturnType<typeof opsService.getCart>>;

export function OpsCartTrackingPage() {
  const [status, setStatus] = useState<string>('ALL');
  const [checkoutState, setCheckoutState] = useState<string>('ALL');
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [selectedCartId, setSelectedCartId] = useState<string | null>(null);
  const [cartDetail, setCartDetail] = useState<CartDetailData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(q.trim()), 300);
    return () => window.clearTimeout(t);
  }, [q]);

  const dash = useCustomer360DashboardQuery();
  const carts = useOpsCartsQuery({
    status: status === 'ALL' ? undefined : status,
    q: debouncedQ || undefined,
    pageSize: 50,
  });
  const d = dash.data;
  const rows = (carts.data?.items ?? []).filter(
    (c) => checkoutState === 'ALL' || c.checkoutState === checkoutState
  );

  const openDetail = async (id: string) => {
    setSelectedCartId(id);
    setCartDetail(null);
    setDetailLoading(true);
    try {
      const detail = await opsService.getCart(id);
      setCartDetail(detail);
    } catch {
      setCartDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <PortalPageHeader
        title="Sepet Takibi"
        description="B2C sepet header’ları, checkout durumu ve siparişe dönüşüm."
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Aktif sepet" value={String(d?.activeCartSessions ?? '—')} />
        <Kpi label="Terk edilmiş" value={String(d?.abandonedCartSessions ?? '—')} />
        <Kpi label="Siparişe dönüşen" value={String(d?.convertedCartSessions ?? '—')} />
        <Kpi label="Geri kazanılan" value={String(d?.recoveredCartSessions ?? '—')} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="E-posta veya sepet ara…"
            className="h-9 pl-8 w-56 text-xs"
          />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[180px] h-9 text-xs">
            <SelectValue placeholder="Durum" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">Tüm durumlar</SelectItem>
            <SelectItem value="ACTIVE">Aktif</SelectItem>
            <SelectItem value="ABANDONED">Terk edilmiş</SelectItem>
            <SelectItem value="CONVERTED">Dönüşen</SelectItem>
            <SelectItem value="EXPIRED">Süresi dolmuş</SelectItem>
          </SelectContent>
        </Select>
        <Select value={checkoutState} onValueChange={setCheckoutState}>
          <SelectTrigger className="w-[190px] h-9 text-xs">
            <SelectValue placeholder="Checkout" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">Tüm checkout aşamaları</SelectItem>
            <SelectItem value="OPEN">Açık</SelectItem>
            <SelectItem value="ADDRESS_ENTERED">Adres Girildi</SelectItem>
            <SelectItem value="PAYMENT_STARTED">Ödeme Başlatıldı</SelectItem>
            <SelectItem value="COMPLETED">Tamamlandı</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {carts.isLoading ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : carts.isError ? (
        <p className="text-sm text-muted-foreground">Sepet listesi yüklenemedi (yetki: carts:view).</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Müşteri / Misafir</TableHead>
              <TableHead>Durum</TableHead>
              <TableHead>Checkout</TableHead>
              <TableHead className="text-right">Satır</TableHead>
              <TableHead className="text-right">Tutar</TableHead>
              <TableHead>Sipariş</TableHead>
              <TableHead>Son aktivite</TableHead>
              <TableHead className="text-right">Detay</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="text-xs">
                  {c.userEmail || c.guestEmail || c.externalId || '—'}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{c.status}</Badge>
                </TableCell>
                <TableCell className="text-xs">{c.checkoutState}</TableCell>
                <TableCell className="text-right tabular-nums">{c.lineCount}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatTrNumber(Number(c.totalTry), 2)} {c.currency}
                </TableCell>
                <TableCell className="font-mono text-xs">{c.convertedOrderNo || '—'}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {c.lastActivityAt ? new Date(c.lastActivityAt).toLocaleString('tr-TR') : '—'}
                </TableCell>
                <TableCell className="text-right">
                  <Button size="sm" variant="ghost" onClick={() => void openDetail(c.id)}>
                    <Eye className="w-3.5 h-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                  Sepet kaydı yok
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <Dialog open={Boolean(selectedCartId)} onOpenChange={(v) => !v && setSelectedCartId(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Sepet Detayı</DialogTitle>
          </DialogHeader>
          {detailLoading ? (
            <p className="text-xs text-muted-foreground py-4">Yükleniyor…</p>
          ) : !cartDetail ? (
            <p className="text-xs text-muted-foreground py-4">Sepet detayı alınamadı.</p>
          ) : (
            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2 border-b border-border pb-3">
                <div>
                  <span className="text-muted-foreground">Müşteri:</span>{' '}
                  <span className="font-medium">{cartDetail.userEmail || cartDetail.guestEmail || '—'}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Durum:</span>{' '}
                  <Badge variant="outline">{cartDetail.status}</Badge>
                </div>
                <div>
                  <span className="text-muted-foreground">Tutar:</span>{' '}
                  <span className="font-mono font-semibold">
                    {formatTrNumber(Number(cartDetail.totalTry), 2)} {cartDetail.currency}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Sipariş:</span>{' '}
                  <span className="font-mono">{cartDetail.convertedOrderNo || '—'}</span>
                </div>
              </div>
              <div className="space-y-1.5 max-h-60 overflow-y-auto">
                {(cartDetail.items ?? []).length === 0 ? (
                  <p className="text-muted-foreground">Sepet kalemi bulunmuyor.</p>
                ) : (
                  (cartDetail.items ?? []).map((item, idx) => (
                    <div key={item.id || idx} className="flex items-center justify-between border rounded px-3 py-2">
                      <div>
                        <div className="font-medium">{item.title || item.sku}</div>
                        <div className="text-[11px] text-muted-foreground font-mono">
                          {item.sku} · {item.qty} adet
                        </div>
                      </div>
                      <div className="font-mono font-semibold">
                        {formatTrNumber(Number(item.unitFinalPriceTry ?? 0) * item.qty, 2)} TL
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

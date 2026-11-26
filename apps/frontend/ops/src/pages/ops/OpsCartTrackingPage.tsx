import { useState } from 'react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
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
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <PortalDataCard title={label}>
      <div className="px-4 py-5 text-2xl font-semibold tabular-nums text-foreground">{value}</div>
    </PortalDataCard>
  );
}

export function OpsCartTrackingPage() {
  const [status, setStatus] = useState<string>('ALL');
  const dash = useCustomer360DashboardQuery();
  const carts = useOpsCartsQuery({
    status: status === 'ALL' ? undefined : status,
    pageSize: 50,
  });
  const d = dash.data;
  const rows = carts.data?.items ?? [];

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

      <div className="flex items-center gap-2">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Durum" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">Tümü</SelectItem>
            <SelectItem value="ACTIVE">Aktif</SelectItem>
            <SelectItem value="ABANDONED">Terk edilmiş</SelectItem>
            <SelectItem value="CONVERTED">Dönüşen</SelectItem>
            <SelectItem value="EXPIRED">Süresi dolmuş</SelectItem>
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
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  Sepet kaydı yok
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

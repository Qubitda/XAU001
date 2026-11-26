import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { toast } from 'sonner';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
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
  useOpsWorkOrdersQuery,
  useUpdateOpsWorkOrderStatusMutation,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { ApiClientError } from '@taragold/shared/lib/api/client';

const WO_STATUS_LABELS: Record<string, string> = {
  PLANNED: 'Planlandı',
  CASTING: 'Döküm / Montür',
  SETTING: 'Mıhlama',
  QUALITY_CHECK: 'Kalite Kontrol',
  COMPLETED: 'Tamamlandı',
};

export function OpsProductionPage() {
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [status, setStatus] = useState<string>('all');
  const [page, setPage] = useState(1);
  const updateStatus = useUpdateOpsWorkOrderStatusMutation();

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedQ(q.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(t);
  }, [q]);

  const listQuery = useOpsWorkOrdersQuery({
    q: debouncedQ || undefined,
    status: status === 'all' ? undefined : status,
    page,
    pageSize: 40,
  });

  const rows = listQuery.data?.items ?? [];
  const pagination = listQuery.data?.pagination;

  const onStatusChange = async (workOrderNo: string, next: string) => {
    try {
      await updateStatus.mutateAsync({ workOrderId: workOrderNo, status: next });
      toast.success('İş emri durumu güncellendi');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Güncellenemedi');
    }
  };

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Atölye İş Emri Kuyruğu & Aşama Takibi"
        title={`Üretim / Atölye${pagination ? ` (${pagination.total})` : ''}`}
        actions={
          <>
            <Select
              value={status}
              onValueChange={(v) => {
                setStatus(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="h-9 w-44 text-xs">
                <SelectValue placeholder="Durum" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm aşamalar</SelectItem>
                {Object.entries(WO_STATUS_LABELS).map(([val, label]) => (
                  <SelectItem key={val} value={val}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="İş emri veya SKU ara..."
                className="h-9 pl-8 w-52 text-xs"
              />
            </div>
          </>
        }
      />

      <PortalDataCard>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">İş Emri</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Kaynak Sipariş</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">SKU</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Bayi</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Adet</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Aşama</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {listQuery.isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                  Yükleniyor...
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                  İş emri bulunamadı.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((wo) => (
                <TableRow key={wo.id}>
                  <TableCell className="px-4 font-mono font-semibold">{wo.workOrderNo}</TableCell>
                  <TableCell className="px-4 font-mono text-muted-foreground">{wo.sourceOrderNo}</TableCell>
                  <TableCell className="px-4 font-sku">
                    {wo.sku}
                    <span className="text-muted-foreground"> · {wo.size}</span>
                  </TableCell>
                  <TableCell className="px-4 text-muted-foreground">
                    {wo.organizationName ?? '—'}
                  </TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums">{wo.quantity}</TableCell>
                  <TableCell className="px-4">
                    <Select
                      value={wo.status}
                      onValueChange={(v) => void onStatusChange(wo.workOrderNo, v)}
                      disabled={updateStatus.isPending}
                    >
                      <SelectTrigger className="h-8 w-44 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(WO_STATUS_LABELS).map(([val, label]) => (
                          <SelectItem key={val} value={val}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {wo.engravingOrStampNote ? (
                      <Badge variant="outline" className="mt-1 text-[10px]">
                        {wo.engravingOrStampNote}
                      </Badge>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </PortalDataCard>

      {pagination && pagination.totalPages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-xs">
          <Button type="button" size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Önceki
          </Button>
          <span className="text-muted-foreground font-mono tabular-nums">
            {pagination.page} / {pagination.totalPages}
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page >= pagination.totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Sonraki
          </Button>
        </div>
      ) : null}
    </div>
  );
}
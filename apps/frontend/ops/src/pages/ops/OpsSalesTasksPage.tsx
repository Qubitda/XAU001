import { useCallback, useEffect, useState } from 'react';
import { Check, RefreshCw, X } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { apiFetch } from '@taragold/shared/lib/api/client';

type SalesTask = {
  id: string;
  kind: string;
  segment: string;
  status: string;
  cartValueTry: string;
  dueAt: string;
  scriptKey: string;
  context: Record<string, unknown>;
  note: string;
  customerEmail: string;
  customerName: string;
  organizationName?: string | null;
  createdAt: string;
};

const STATUS_TR: Record<string, string> = {
  OPEN: 'Açık',
  DONE: 'Tamamlandı',
  DISMISSED: 'Kapatıldı',
};

export function OpsSalesTasksPage() {
  const [rows, setRows] = useState<SalesTask[]>([]);
  const [status, setStatus] = useState('OPEN');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = status ? `?status=${encodeURIComponent(status)}` : '';
      const res = await apiFetch<SalesTask[]>(`/api/v1/ops/sales-tasks${qs}`);
      setRows(res.data ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Liste alınamadı');
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  const patchStatus = async (id: string, next: 'DONE' | 'DISMISSED') => {
    setError(null);
    setOk(null);
    try {
      await apiFetch(`/api/v1/ops/sales-tasks/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: next }),
      });
      setOk(next === 'DONE' ? 'Görev tamamlandı.' : 'Görev kapatıldı.');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Güncelleme başarısız');
    }
  };

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Satış Takibi"
        title="Terk Sepet / Taslak Görevleri"
        description="B2B taslak ve yüksek tutarlı B2C sepetler için otomatik arama / teklif destek görevleri."
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {ok && (
        <div className="rounded-md border border-border bg-muted/40 px-4 py-3 text-sm text-foreground">
          {ok}
        </div>
      )}

      <PortalDataCard
        title="Görevler"
        toolbar={
          <div className="flex items-center gap-2">
            <div className="space-y-1">
              <Label htmlFor="sales-task-status" className="text-[11px] text-muted-foreground">
                Durum
              </Label>
              <select
                id="sales-task-status"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-2 text-xs"
              >
                <option value="OPEN">Açık</option>
                <option value="DONE">Tamamlandı</option>
                <option value="DISMISSED">Kapatıldı</option>
                <option value="">Tümü</option>
              </select>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw className="w-3.5 h-3.5" />
              Yenile
            </Button>
          </div>
        }
      >
        {loading ? (
          <p className="text-sm text-muted-foreground py-6">Yükleniyor…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6">Kayıt yok.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Segment</TableHead>
                <TableHead>Müşteri / Bayi</TableHead>
                <TableHead>Tutar</TableHead>
                <TableHead>Script</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead className="text-right">Aksiyon</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const script =
                  typeof row.context?.call_script === 'string' ? row.context.call_script : '';
                return (
                  <TableRow key={row.id}>
                    <TableCell>
                      <Badge variant="outline">{row.segment}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      <div className="font-medium text-foreground">
                        {row.organizationName || row.customerName || '—'}
                      </div>
                      <div className="text-muted-foreground">{row.customerEmail}</div>
                    </TableCell>
                    <TableCell className="text-xs font-mono">{row.cartValueTry} TRY</TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[280px]">
                      {script || row.scriptKey}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{STATUS_TR[row.status] || row.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {row.status === 'OPEN' ? (
                        <div className="inline-flex gap-1">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void patchStatus(row.id, 'DONE')}
                          >
                            <Check className="w-3.5 h-3.5" />
                            Tamam
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => void patchStatus(row.id, 'DISMISSED')}
                          >
                            <X className="w-3.5 h-3.5" />
                            Kapat
                          </Button>
                        </div>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </PortalDataCard>
    </div>
  );
}

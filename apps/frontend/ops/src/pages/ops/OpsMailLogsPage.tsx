import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, RotateCcw } from 'lucide-react';
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

type MailLog = {
  id: string;
  recipient: string;
  templateKey: string;
  subject: string;
  status: string;
  errorMessage: string;
  sentAt: string | null;
  createdAt: string;
};

const STATUS_TR: Record<string, string> = {
  QUEUED: 'Kuyrukta',
  SENT: 'İletildi',
  FAILED: 'Hata',
};

export function OpsMailLogsPage() {
  const [rows, setRows] = useState<MailLog[]>([]);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = status ? `?status=${encodeURIComponent(status)}` : '';
      const res = await apiFetch<MailLog[]>(`/api/v1/ops/mail/logs${qs}`);
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

  const onRetry = async (id: string) => {
    setError(null);
    setOk(null);
    try {
      await apiFetch(`/api/v1/ops/mail/logs/${id}/retry`, { method: 'POST' });
      setOk('Tekrar gönderim kuyruğa alındı.');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retry başarısız');
    }
  };

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Transactional Mail"
        title="Mail Logları"
        description="Gönderilen mailler, SMTP hataları ve başarısızlar için tekrar gönder."
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      )}
      {ok && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {ok}
        </div>
      )}

      <PortalDataCard title="Filtre" contentClassName="p-4 flex flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <Label>Durum</Label>
          <select
            className="flex h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Tümü</option>
            <option value="SENT">İletildi</option>
            <option value="FAILED">Hata</option>
            <option value="QUEUED">Kuyrukta</option>
          </select>
        </div>
        <Button type="button" variant="outline" onClick={() => void load()}>
          <RefreshCw className="w-4 h-4" />
          Yenile
        </Button>
      </PortalDataCard>

      <div className="md:hidden space-y-3">
        {rows.map((r) => (
          <PortalDataCard key={r.id} title={r.templateKey} contentClassName="p-4 space-y-2 text-xs">
            <div className="truncate">{r.recipient}</div>
            <Badge variant={r.status === 'FAILED' ? 'destructive' : 'secondary'}>
              {STATUS_TR[r.status] ?? r.status}
            </Badge>
            {r.errorMessage ? <p className="text-red-700 break-words">{r.errorMessage}</p> : null}
            {r.status === 'FAILED' && (
              <Button size="sm" variant="outline" className="min-h-11" onClick={() => void onRetry(r.id)}>
                <RotateCcw className="w-3.5 h-3.5" />
                Tekrar Gönder
              </Button>
            )}
          </PortalDataCard>
        ))}
      </div>

      <PortalDataCard
        title={loading ? 'Yükleniyor…' : `Kayıtlar (${rows.length})`}
        className="hidden md:block"
        contentClassName="p-0 overflow-x-auto"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Alıcı</TableHead>
              <TableHead>Şablon</TableHead>
              <TableHead>Konu</TableHead>
              <TableHead>Durum</TableHead>
              <TableHead>Hata</TableHead>
              <TableHead>Tarih</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="text-xs">{r.recipient}</TableCell>
                <TableCell className="font-mono text-xs">{r.templateKey}</TableCell>
                <TableCell className="text-xs max-w-[200px] truncate">{r.subject || '—'}</TableCell>
                <TableCell>
                  <Badge variant={r.status === 'FAILED' ? 'destructive' : 'secondary'}>
                    {STATUS_TR[r.status] ?? r.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-[11px] text-red-700 max-w-[220px] truncate">
                  {r.errorMessage || '—'}
                </TableCell>
                <TableCell className="text-xs">
                  {new Date(r.sentAt || r.createdAt).toLocaleString('tr-TR')}
                </TableCell>
                <TableCell className="text-right">
                  {r.status === 'FAILED' && (
                    <Button size="sm" variant="outline" onClick={() => void onRetry(r.id)}>
                      <RotateCcw className="w-3.5 h-3.5" />
                      Tekrar Gönder
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!loading && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-8">
                  Kayıt yok
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </PortalDataCard>
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Download, RefreshCw } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { useCustomer360DashboardQuery } from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { apiFetch } from '@taragold/shared/lib/api/client';

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <PortalDataCard title={label}>
      <div className="px-4 py-5 text-2xl font-semibold tabular-nums text-foreground">{value}</div>
    </PortalDataCard>
  );
}

type ConsentItem = {
  id: string;
  purpose: string;
  status: string;
  channel?: string;
  email?: string;
  phone?: string;
  iysReference?: string;
  createdAt: string;
};

export function OpsConsentsOverviewPage() {
  const dash = useCustomer360DashboardQuery();
  const d = dash.data;
  const [items, setItems] = useState<ConsentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<{ items?: ConsentItem[] }>('/api/v1/ops/consents/iys-export');
      setItems(Array.isArray(res.data?.items) ? res.data.items : []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = items.filter((item) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (
      (item.email || '').toLowerCase().includes(q) ||
      (item.phone || '').toLowerCase().includes(q) ||
      (item.purpose || '').toLowerCase().includes(q)
    );
  });

  const downloadExport = () => {
    const blob = new Blob([JSON.stringify(items, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `iys-consents-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <PortalPageHeader
        title="İzin ve Onay Yönetimi"
        description="Ticari ileti ve KVKK izin kayıtları."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Yenile
            </Button>
            <Button variant="outline" size="sm" onClick={downloadExport} disabled={items.length === 0}>
              <Download className="w-3.5 h-3.5 mr-1.5" />
              İYS JSON İndir
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/ops/musteriler">Müşteriler</Link>
            </Button>
          </div>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi label="Ticari e-posta izni" value={String(d?.commercialEmailGranted ?? '—')} />
        <Kpi label="İzin geri çekilmiş" value={String(d?.commercialEmailWithdrawn ?? '—')} />
        <Kpi label="Toplam B2C müşteri" value={String(d?.totalB2cCustomers ?? '—')} />
      </div>

      <PortalDataCard
        title={`İYS / Ticari İzin Kayıtları (${filtered.length})`}
        toolbar={
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="E-posta, telefon veya amaç ara…"
            className="h-8 w-64 text-xs"
          />
        }
      >
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground">Yükleniyor…</p>
        ) : filtered.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">Kayıt bulunamadı.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Amaç</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>İletişim</TableHead>
                <TableHead>İYS Ref</TableHead>
                <TableHead>Tarih</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.slice(0, 100).map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-mono text-xs">{row.purpose}</TableCell>
                  <TableCell>
                    <Badge variant={row.status === 'GRANTED' ? 'default' : 'secondary'}>
                      {row.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">{row.email || row.phone || '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{row.iysReference || '—'}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(row.createdAt).toLocaleString('tr-TR')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </PortalDataCard>
    </div>
  );
}

type AuditRow = {
  id: string;
  actorEmail: string | null;
  actorName: string | null;
  organizationCode: string | null;
  action: string;
  entityType: string;
  entityId: string;
  createdAt: string;
};

export function OpsCustomerActivityPage() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<AuditRow[]>('/api/v1/ops/audit-logs?pageSize=100');
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = rows.filter((r) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (
      r.action.toLowerCase().includes(q) ||
      r.entityType.toLowerCase().includes(q) ||
      (r.actorEmail || '').toLowerCase().includes(q) ||
      r.entityId.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-4">
      <PortalPageHeader
        title="Müşteri & Sistem İşlem Geçmişi"
        description="Tüm denetim kayıtları (AuditLog)."
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Yenile
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/ops/musteriler">Müşteriler</Link>
            </Button>
          </div>
        }
      />

      <PortalDataCard
        title={`Denetim Kayıtları (${filtered.length})`}
        toolbar={
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Aksiyon, aktör veya nesne ara…"
            className="h-8 w-64 text-xs"
          />
        }
      >
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground">Yükleniyor…</p>
        ) : filtered.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">Kayıt bulunamadı.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Aksiyon</TableHead>
                <TableHead>Nesne</TableHead>
                <TableHead>Aktör</TableHead>
                <TableHead>Tarih</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.action}</TableCell>
                  <TableCell className="text-xs">
                    <span className="font-medium">{r.entityType}</span>{' '}
                    <span className="font-mono text-muted-foreground">{r.entityId}</span>
                  </TableCell>
                  <TableCell className="text-xs">{r.actorEmail || r.actorName || 'Sistem'}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(r.createdAt).toLocaleString('tr-TR')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </PortalDataCard>
    </div>
  );
}

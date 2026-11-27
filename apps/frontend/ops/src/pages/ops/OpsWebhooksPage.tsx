import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Input,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { apiFetch } from '@taragold/shared/lib/api/client';

const EVENT_OPTIONS = ['b2c.order.created', 'b2b.order.created', 'b2b.order.status'] as const;

type WebhookRow = {
  id: string;
  organizationName: string;
  url: string;
  events: string[];
  isActive: boolean;
  createdAt: string;
};

type OrgOption = { id: string; name: string };

type CreateResponse = WebhookRow & { secret?: string; meta?: { note?: string } };

export function OpsWebhooksPage() {
  const [rows, setRows] = useState<WebhookRow[]>([]);
  const [orgs, setOrgs] = useState<OrgOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState('');
  const [isPlatform, setIsPlatform] = useState(false);
  const [organizationId, setOrganizationId] = useState('');
  const [events, setEvents] = useState<string[]>(['b2b.order.created']);
  const [plaintextSecret, setPlaintextSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [hooksRes, orgsRes] = await Promise.all([
        apiFetch<WebhookRow[]>('/api/v1/ops/webhooks'),
        apiFetch<OrgOption[]>('/api/v1/ops/organizations?pageSize=200&isActive=true'),
      ]);
      setRows(hooksRes.data ?? []);
      const list = Array.isArray(orgsRes.data) ? orgsRes.data : [];
      setOrgs(list.map((o) => ({ id: String(o.id), name: String(o.name ?? '') })));
      setOrganizationId((prev) => prev || (list[0] ? String(list[0].id) : ''));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Liste alınamadı');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleEvent = (event: string) => {
    setEvents((prev) => (prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]));
  };

  const onCreate = async () => {
    setError(null);
    setPlaintextSecret(null);
    try {
      const res = await apiFetch<CreateResponse>('/api/v1/ops/webhooks', {
        method: 'POST',
        body: isPlatform ? { isPlatform: true, url, events } : { organizationId, url, events },
      });
      if (res.data?.secret) setPlaintextSecret(res.data.secret);
      setUrl('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Oluşturulamadı');
    }
  };

  const onRevoke = async (id: string) => {
    if (!window.confirm('Bu webhook iptal edilsin mi?')) return;
    setError(null);
    try {
      await apiFetch(`/api/v1/ops/webhooks/${id}/revoke`, { method: 'POST' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'İptal edilemedi');
    }
  };

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Harici entegrasyonlar"
        title="Webhooklar"
        description="B2C/B2B sipariş olayları için HMAC imzalı POST bildirimleri (X-Tara-Signature)."
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {plaintextSecret ? (
        <PortalDataCard title="Webhook secret (bir kez)">
          <code className="text-xs break-all">{plaintextSecret}</code>
        </PortalDataCard>
      ) : null}

      <PortalDataCard title="Yeni webhook">
        <div className="mb-3 flex items-center gap-2 text-xs">
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isPlatform}
              onChange={(e) => {
                const next = e.target.checked;
                setIsPlatform(next);
                setEvents(next ? ['b2c.order.created'] : ['b2b.order.created']);
              }}
            />
            <span>Platform Webhook (B2C olayları için)</span>
          </label>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label>Firma</Label>
            <select
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm disabled:opacity-50"
              disabled={isPlatform}
              value={organizationId}
              onChange={(e) => setOrganizationId(e.target.value)}
            >
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label>Hedef URL</Label>
            <Input className="mt-1" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {EVENT_OPTIONS.filter((ev) => (isPlatform ? true : ev !== 'b2c.order.created')).map((ev) => (
            <Button
              key={ev}
              type="button"
              size="sm"
              variant={events.includes(ev) ? 'default' : 'outline'}
              onClick={() => toggleEvent(ev)}
            >
              {ev}
            </Button>
          ))}
        </div>
        <Button
          className="mt-4"
          variant="success"
          disabled={!url || (!isPlatform && !organizationId) || events.length === 0}
          onClick={() => void onCreate()}
        >
          <Plus className="w-4 h-4 mr-1" />
          Oluştur
        </Button>
      </PortalDataCard>

      <PortalDataCard title="Kayıtlı uç noktalar">
        {loading ? (
          <p className="text-sm text-muted-foreground">Yükleniyor…</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Firma</TableHead>
                <TableHead>URL</TableHead>
                <TableHead>Olaylar</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.organizationName || 'Platform'}</TableCell>
                  <TableCell className="max-w-xs truncate font-mono text-xs">{row.url}</TableCell>
                  <TableCell className="text-xs">{row.events.join(', ')}</TableCell>
                  <TableCell>
                    <Badge variant={row.isActive ? 'default' : 'secondary'}>{row.isActive ? 'Aktif' : 'İptal'}</Badge>
                  </TableCell>
                  <TableCell>
                    {row.isActive ? (
                      <Button size="sm" variant="ghost" onClick={() => void onRevoke(row.id)}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    ) : null}
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
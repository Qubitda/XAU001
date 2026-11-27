import { useCallback, useEffect, useState } from 'react';
import { Copy, KeyRound, Plus, Trash2 } from 'lucide-react';
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

type ApiKeyRow = {
  id: string;
  name: string;
  prefix: string;
  organizationName: string;
  scopes: string[];
  isActive: boolean;
  lastUsedAt: string | null;
  createdAt: string;
};

type OrgOption = { id: string; name: string; code: string };

type CreateResponse = ApiKeyRow & { key?: string; meta?: { note?: string } };

const DEFAULT_SCOPES = ['storefront:read', 'storefront:write', 'market:read'] as const;
const ALL_SCOPES = [
  'storefront:read',
  'storefront:write',
  'market:read',
  'b2b:read',
  'b2b:write',
  'integrations:b2c:write',
] as const;

export function OpsApiKeysPage() {
  const [rows, setRows] = useState<ApiKeyRow[]>([]);
  const [orgs, setOrgs] = useState<OrgOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [organizationId, setOrganizationId] = useState('');
  const [scopes, setScopes] = useState<string[]>([...DEFAULT_SCOPES]);
  const [expiresAt, setExpiresAt] = useState('');
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [keysRes, orgsRes] = await Promise.all([
        apiFetch<ApiKeyRow[]>('/api/v1/ops/api-keys'),
        apiFetch<OrgOption[]>('/api/v1/ops/organizations?pageSize=200&isActive=true'),
      ]);
      setRows(keysRes.data ?? []);
      const list = Array.isArray(orgsRes.data) ? orgsRes.data : [];
      setOrgs(
        list.map((o) => ({
          id: String(o.id),
          name: String(o.name ?? ''),
          code: String(o.code ?? ''),
        }))
      );
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

  const toggleScope = (scope: string) => {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  };

  const onCreate = async () => {
    setError(null);
    setPlaintext(null);
    setCopied(false);
    try {
      const res = await apiFetch<CreateResponse>('/api/v1/ops/api-keys', {
        method: 'POST',
        body: {
          name,
          organizationId,
          scopes,
          ...(expiresAt ? { expiresAt: new Date(`${expiresAt}T23:59:59Z`).toISOString() } : {}),
        },
      });
      if (res.data?.key) setPlaintext(res.data.key);
      setName('');
      setExpiresAt('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Oluşturulamadı');
    }
  };

  const onRevoke = async (id: string) => {
    if (!window.confirm('Bu API anahtarını iptal etmek istiyor musunuz?')) return;
    setError(null);
    try {
      await apiFetch(`/api/v1/ops/api-keys/${id}/revoke`, { method: 'POST' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'İptal edilemedi');
    }
  };

  const copyKey = async () => {
    if (!plaintext) return;
    await navigator.clipboard.writeText(plaintext);
    setCopied(true);
  };

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Harici entegrasyonlar"
        title="API Anahtarları"
        description="Harici B2C / ERP sistemleri Authorization: Bearer tg_live_… veya X-Api-Key ile bağlanır. Session auth etkilenmez."
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {plaintext ? (
        <PortalDataCard title="Anahtar — yalnızca bir kez gösterilir" contentClassName="p-4 space-y-3">
          <code className="block break-all rounded-md border border-border bg-muted px-3 py-2 text-xs font-mono">
            {plaintext}
          </code>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void copyKey()}>
              <Copy className="w-3.5 h-3.5 mr-1" />
              {copied ? 'Kopyalandı' : 'Kopyala'}
            </Button>
            <p className="text-xs text-muted-foreground">
              Güvenli saklayın; sunucu tekrar göstermez. Cart/order bu anahtarı oluşturan OPS kullanıcısına bağlanır.
            </p>
          </div>
        </PortalDataCard>
      ) : null}

      <PortalDataCard title="Yeni anahtar" contentClassName="p-4 space-y-3">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="space-y-1.5">
            <Label htmlFor="api-key-name">Ad</Label>
            <Input
              id="api-key-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Partner storefront prod"
              className="w-56"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="api-key-org">Firma</Label>
            <select
              id="api-key-org"
              value={organizationId}
              onChange={(e) => setOrganizationId(e.target.value)}
              className="flex h-9 w-72 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">Firma seçin</option>
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.code} — {o.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="api-key-exp">Son Geçerlilik (Opsiyonel)</Label>
            <Input
              id="api-key-exp"
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-44"
            />
          </div>
          <Button
            type="button"
            variant="success"
            onClick={() => void onCreate()}
            disabled={!name.trim() || !organizationId.trim() || scopes.length === 0}
          >
            <Plus className="w-4 h-4 mr-1" />
            Oluştur
          </Button>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          {ALL_SCOPES.map((sc) => (
            <Button
              key={sc}
              type="button"
              size="sm"
              variant={scopes.includes(sc) ? 'default' : 'outline'}
              onClick={() => toggleScope(sc)}
              className="text-xs font-mono h-7"
            >
              {sc}
            </Button>
          ))}
        </div>
      </PortalDataCard>

      <PortalDataCard title="Kayıtlı anahtarlar">
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4">Ad</TableHead>
              <TableHead className="px-4">Prefix</TableHead>
              <TableHead className="px-4">Firma</TableHead>
              <TableHead className="px-4">Kapsamlar</TableHead>
              <TableHead className="px-4">Durum</TableHead>
              <TableHead className="px-4 w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="px-4 text-muted-foreground">
                  Yükleniyor…
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="px-4 text-muted-foreground">
                  Henüz anahtar yok.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="px-4 font-medium">
                    <KeyRound className="inline w-3.5 h-3.5 mr-1 text-muted-foreground" />
                    {row.name}
                  </TableCell>
                  <TableCell className="px-4 font-mono">{row.prefix}…</TableCell>
                  <TableCell className="px-4">{row.organizationName}</TableCell>
                  <TableCell className="px-4">
                    <div className="flex flex-wrap gap-1">
                      {row.scopes.map((s) => (
                        <Badge key={s} variant="secondary" className="font-mono text-[10px]">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="px-4">
                    <Badge variant={row.isActive ? 'default' : 'secondary'}>
                      {row.isActive ? 'Aktif' : 'İptal'}
                    </Badge>
                  </TableCell>
                  <TableCell className="px-4">
                    {row.isActive ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => void onRevoke(row.id)}
                        aria-label="İptal et"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-destructive" />
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </PortalDataCard>
    </div>
  );
}

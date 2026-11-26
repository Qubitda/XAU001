import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import { Badge, Button, Input, Label, RichTextEditor } from '@taragold/shared/components/ui';
import { apiFetch, ApiClientError } from '@taragold/shared/lib/api/client';
import type { OpsLegalDocument } from '@taragold/shared/features/ops/types';

type LegalDetail = OpsLegalDocument & { bodyHtml?: string; bodyMd?: string };

const SEED_DOCS: { code: string; version: string; title: string; bodyHtml: string }[] = [
  {
    code: 'KVKK',
    version: '1.0',
    title: 'KVKK Aydınlatma Metni',
    bodyHtml: '<p>Kişisel verilerinizin işlenmesi hakkında aydınlatma metni.</p>',
  },
  {
    code: 'PRIVACY',
    version: '1.0',
    title: 'Gizlilik İlkeleri',
    bodyHtml: '<p>Gizlilik ilkelerimiz.</p>',
  },
  {
    code: 'COOKIE',
    version: '1.0',
    title: 'Çerez Politikası',
    bodyHtml: '<p>Çerez kullanım politikası.</p>',
  },
  {
    code: 'DISTANCE_SALES',
    version: '1.0',
    title: 'Mesafeli Satış Sözleşmesi',
    bodyHtml: '<p>Mesafeli satış sözleşmesi metni.</p>',
  },
  {
    code: 'PRE_INFO',
    version: '1.0',
    title: 'Ön Bilgilendirme Formu',
    bodyHtml: '<p>Ön bilgilendirme formu.</p>',
  },
  {
    code: 'MEMBERSHIP',
    version: '1.0',
    title: 'Üyelik Sözleşmesi',
    bodyHtml: '<p>Üyelik sözleşmesi metni.</p>',
  },
];

export function OpsLegalDocumentsPage() {
  const [items, setItems] = useState<OpsLegalDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<LegalDetail | null>(null);
  const [title, setTitle] = useState('');
  const [bodyHtml, setBodyHtml] = useState('');
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<OpsLegalDocument[]>('/api/v1/ops/legal-documents');
      setItems(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      const msg = e instanceof ApiClientError ? e.message : 'Belgeler yüklenemedi';
      setError(msg);
      setItems([]);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch<LegalDetail>(`/api/v1/ops/legal-documents/${selectedId}`);
        if (cancelled) return;
        setDetail(res.data);
        setTitle(res.data.title);
        setBodyHtml(res.data.bodyHtml || '');
      } catch (e) {
        toast.error(e instanceof ApiClientError ? e.message : 'Belge yüklenemedi');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function save(publish?: boolean) {
    if (!selectedId) return;
    setSaving(true);
    try {
      const res = await apiFetch<LegalDetail>(`/api/v1/ops/legal-documents/${selectedId}`, {
        method: 'PATCH',
        body: {
          title,
          bodyHtml,
          ...(publish !== undefined ? { isPublished: publish } : {}),
        },
      });
      setDetail(res.data);
      toast.success(publish ? 'Yayınlandı' : 'Kaydedildi');
      await loadList();
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Kayıt başarısız');
    } finally {
      setSaving(false);
    }
  }

  async function seedDefaults() {
    setSeeding(true);
    try {
      let created = 0;
      for (const seed of SEED_DOCS) {
        const exists = items.some((d) => d.code === seed.code && d.version === seed.version);
        if (exists) continue;
        try {
          await apiFetch('/api/v1/ops/legal-documents', {
            method: 'POST',
            body: { ...seed, isPublished: true, audience: 'ALL' },
          });
          created += 1;
        } catch {
          // already exists or validation — continue
        }
      }
      await loadList();
      toast.success(created > 0 ? `${created} belge oluşturuldu` : 'Belgeler zaten mevcut veya oluşturulamadı');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Seed başarısız');
    } finally {
      setSeeding(false);
    }
  }

  async function exportIys() {
    try {
      const res = await apiFetch<{ items: unknown[]; note: string }>('/api/v1/ops/consents/iys-export');
      toast.success(`İYS export: ${Array.isArray(res.data.items) ? res.data.items.length : 0} kayıt`);
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Export başarısız');
    }
  }

  return (
    <div className="space-y-4">
      <PortalPageHeader
        title="Kvkk ve Sözleşmeler"
        description="Versioned yasal metinler (KVKK, mesafeli satış, üyelik). Storefront footer yayınlanan sürümü okur."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void loadList()}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Yenile
            </Button>
            {items.length === 0 && (
              <Button type="button" size="sm" disabled={seeding} onClick={() => void seedDefaults()}>
                {seeding ? 'Oluşturuluyor…' : 'Varsayılan belgeleri oluştur'}
              </Button>
            )}
            <Button type="button" size="sm" variant="outline" onClick={() => void exportIys()}>
              İYS Export Hook
            </Button>
          </div>
        }
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <PortalDataCard title="Belgeler" contentClassName="divide-y divide-border">
          {loading ? (
            <p className="p-4 text-sm text-muted-foreground">Yükleniyor…</p>
          ) : items.length === 0 ? (
            <div className="p-4 space-y-2">
              <p className="text-sm text-muted-foreground">Henüz belge yok.</p>
              <Button type="button" size="sm" disabled={seeding} onClick={() => void seedDefaults()}>
                Varsayılan belgeleri oluştur
              </Button>
            </div>
          ) : (
            items.map((doc) => (
              <button
                key={doc.id}
                type="button"
                onClick={() => setSelectedId(doc.id)}
                className={`w-full text-left px-4 py-3 text-sm transition-colors hover:bg-muted/40 ${
                  selectedId === doc.id ? 'bg-muted/60' : ''
                }`}
              >
                <div className="font-medium text-foreground">
                  {doc.title}{' '}
                  <span className="font-mono text-xs text-muted-foreground">
                    {doc.code} v{doc.version}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground flex items-center gap-2 mt-1">
                  <Badge variant={doc.isPublished ? 'secondary' : 'outline'}>
                    {doc.isPublished ? 'Yayında' : 'Taslak'}
                  </Badge>
                  <span>{doc.audience}</span>
                </div>
              </button>
            ))
          )}
        </PortalDataCard>

        <PortalDataCard title="Düzenle" contentClassName="p-4 space-y-3">
          {!detail ? (
            <p className="text-sm text-muted-foreground">Soldan bir belge seçin.</p>
          ) : (
            <>
              <div className="text-xs font-mono text-muted-foreground">
                {detail.code} · v{detail.version} · hash {(detail.contentHash || '').slice(0, 16) || '—'}
                …
              </div>
              <div>
                <Label className="text-[11px]">Başlık</Label>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">İçerik</Label>
                <RichTextEditor
                  contentKey={selectedId || detail.id}
                  value={bodyHtml}
                  onChange={setBodyHtml}
                  placeholder="Yasal metni yazın…"
                  minHeightClassName="min-h-[280px]"
                  disabled={saving}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" disabled={saving} onClick={() => void save()}>
                  Kaydet
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={saving}
                  onClick={() => void save(true)}
                >
                  Kaydet & Yayınla
                </Button>
                {detail.isPublished && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost-destructive"
                    disabled={saving}
                    onClick={() => void save(false)}
                  >
                    Yayından kaldır
                  </Button>
                )}
              </div>
            </>
          )}
        </PortalDataCard>
      </div>
    </div>
  );
}

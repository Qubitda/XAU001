import { useCallback, useEffect, useState, type ChangeEvent } from 'react';
import { toast } from 'sonner';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import { Button, Input, Label } from '@taragold/shared/components/ui';
import { apiFetch, ApiClientError } from '@taragold/shared/lib/api/client';

type SiteContact = {
  id: string;
  companyName: string;
  tagline: string;
  addressLine: string;
  phone: string;
  email: string;
  workingHours: string;
  whatsapp: string;
  instagramUrl: string;
  youtubeUrl: string;
  tiktokUrl: string;
  pinterestUrl: string;
  mapUrl: string;
};

const EMPTY: SiteContact = {
  id: '',
  companyName: '',
  tagline: '',
  addressLine: '',
  phone: '',
  email: '',
  workingHours: '',
  whatsapp: '',
  instagramUrl: '',
  youtubeUrl: '',
  tiktokUrl: '',
  pinterestUrl: '',
  mapUrl: '',
};

export function OpsSiteContactPage() {
  const [form, setForm] = useState<SiteContact>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<SiteContact>('/api/v1/ops/site-contact');
      setForm({ ...EMPTY, ...res.data });
    } catch (e) {
      const msg = e instanceof ApiClientError ? e.message : 'Yüklenemedi';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const set =
    (key: keyof SiteContact) =>
    (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setForm((prev) => ({ ...prev, [key]: e.target.value }));
    };

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch<SiteContact>('/api/v1/ops/site-contact', {
        method: 'PUT',
        body: {
          companyName: form.companyName,
          tagline: form.tagline,
          addressLine: form.addressLine,
          phone: form.phone,
          email: form.email,
          workingHours: form.workingHours,
          whatsapp: form.whatsapp,
          instagramUrl: form.instagramUrl,
          youtubeUrl: form.youtubeUrl,
          tiktokUrl: form.tiktokUrl,
          pinterestUrl: form.pinterestUrl,
          mapUrl: form.mapUrl,
        },
      });
      setForm({ ...EMPTY, ...res.data });
      toast.success('İletişim bilgileri kaydedildi');
    } catch (e) {
      const msg = e instanceof ApiClientError ? e.message : 'Kayıt başarısız';
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <PortalPageHeader
        title="Şirket İletişim"
        description="Storefront footer ve müşteri hizmetleri alanında görünen şirket iletişim bilgileri."
        actions={
          <Button type="button" size="sm" disabled={saving || loading} onClick={() => void save()}>
            {saving ? 'Kaydediliyor…' : 'Kaydet'}
          </Button>
        }
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <PortalDataCard title="Genel" contentClassName="p-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-[11px]">Şirket / marka adı</Label>
            <Input value={form.companyName} onChange={set('companyName')} disabled={loading} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-[11px]">Kısa slogan</Label>
            <Input value={form.tagline} onChange={set('tagline')} disabled={loading} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-[11px]">Adres</Label>
            <Input value={form.addressLine} onChange={set('addressLine')} disabled={loading} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px]">Telefon</Label>
            <Input value={form.phone} onChange={set('phone')} disabled={loading} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px]">E-posta</Label>
            <Input type="email" value={form.email} onChange={set('email')} disabled={loading} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px]">Çalışma saatleri</Label>
            <Input value={form.workingHours} onChange={set('workingHours')} disabled={loading} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px]">WhatsApp</Label>
            <Input
              value={form.whatsapp}
              onChange={set('whatsapp')}
              disabled={loading}
              placeholder="905xxxxxxxxx"
            />
          </div>
        </div>
      </PortalDataCard>

      <PortalDataCard title="Sosyal & Harita" contentClassName="p-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label className="text-[11px]">Instagram URL</Label>
            <Input value={form.instagramUrl} onChange={set('instagramUrl')} disabled={loading} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px]">YouTube URL</Label>
            <Input value={form.youtubeUrl} onChange={set('youtubeUrl')} disabled={loading} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px]">TikTok URL</Label>
            <Input value={form.tiktokUrl} onChange={set('tiktokUrl')} disabled={loading} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px]">Pinterest URL</Label>
            <Input value={form.pinterestUrl} onChange={set('pinterestUrl')} disabled={loading} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-[11px]">Harita / konum URL</Label>
            <Input value={form.mapUrl} onChange={set('mapUrl')} disabled={loading} />
          </div>
        </div>
      </PortalDataCard>
    </div>
  );
}

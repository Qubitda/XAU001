import { useCallback, useEffect, useState } from 'react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import { Button, Input, Label, RichTextEditor } from '@taragold/shared/components/ui';
import { apiFetch } from '@taragold/shared/lib/api/client';

type TemplateRow = {
  id: string;
  templateKey: string;
  subject: string;
  bodyHtml: string;
  primaryColor: string;
  logoUrl: string;
  isActive: boolean;
};

const TEMPLATE_KEYS = [
  'welcome',
  'bank_transfer_pending',
  'payment_success',
  'payment_failed',
  'order_cancelled',
  'payment_refunded',
] as const;

export function OpsMailTemplatesPage() {
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [editKey, setEditKey] = useState<string>('welcome');
  const [subject, setSubject] = useState('');
  const [bodyHtml, setBodyHtml] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const loadTemplates = useCallback(async () => {
    const res = await apiFetch<TemplateRow[]>('/api/v1/ops/mail/templates');
    setTemplates(Array.isArray(res.data) ? res.data : []);
  }, []);

  useEffect(() => {
    setError(null);
    void loadTemplates().catch((e) => {
      setError(e instanceof Error ? e.message : 'Şablonlar yüklenemedi');
    });
  }, [loadTemplates]);

  useEffect(() => {
    const existing = templates.find((t) => t.templateKey === editKey);
    setSubject(existing?.subject ?? '');
    setBodyHtml(existing?.bodyHtml ?? '');
  }, [editKey, templates]);

  const saveTemplate = async () => {
    setError(null);
    setOk(null);
    try {
      await apiFetch('/api/v1/ops/mail/templates', {
        method: 'POST',
        body: {
          templateKey: editKey,
          subject,
          bodyHtml,
          isActive: true,
        },
      });
      setOk(`Şablon kaydedildi: ${editKey}`);
      await loadTemplates();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Şablon kaydedilemedi');
    }
  };

  return (
    <div className="space-y-6">
      <PortalPageHeader
        title="E-posta Şablonları"
        description="Transactional e-posta şablonları (ödeme, sipariş, hoş geldin). Yasal metinler bu sayfada değildir."
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}
      {ok && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          {ok}
        </div>
      )}

      <PortalDataCard title="E-posta Şablonları" contentClassName="p-6 space-y-4">
        <p className="text-xs text-muted-foreground">
          Değişkenler: {'{{customer_name}}'}, {'{{amount}}'}, {'{{order_no}}'}, {'{{refund_amount}}'},{' '}
          {'{{error_message}}'}
        </p>
        <div className="flex flex-wrap gap-2">
          {TEMPLATE_KEYS.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setEditKey(k)}
              className={`px-2.5 py-1 rounded text-xs font-mono ${
                editKey === k ? 'bg-zinc-900 text-white' : 'bg-muted text-muted-foreground'
              }`}
            >
              {k}
            </button>
          ))}
        </div>
        <div className="space-y-1.5">
          <Label>Konu</Label>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>İçerik</Label>
          <RichTextEditor
            contentKey={editKey}
            value={bodyHtml}
            onChange={setBodyHtml}
            placeholder="Merhaba {{ customer_name }}, …"
            minHeightClassName="min-h-[260px]"
          />
        </div>
        <Button type="button" onClick={() => void saveTemplate()}>
          Şablonu Kaydet
        </Button>
      </PortalDataCard>
    </div>
  );
}

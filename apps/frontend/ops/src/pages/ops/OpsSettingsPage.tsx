import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Mail, CreditCard, FileText, Send, Landmark, MessageSquare } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import { Badge, Button, Input, Label, RichTextEditor } from '@taragold/shared/components/ui';
import { apiFetch } from '@taragold/shared/lib/api/client';

type Tab = 'payment' | 'banks' | 'smtp' | 'templates' | 'messaging';

const TAB_VALUES: Tab[] = ['payment', 'banks', 'smtp', 'templates', 'messaging'];

type MessagingStatus = {
  smsEnabled: boolean;
  whatsappEnabled: boolean;
  smsProvider: string;
  whatsappProvider: string;
  smsWebhookConfigured: boolean;
  whatsappWebhookConfigured: boolean;
};

type MessagingLog = {
  id: string;
  channel: string;
  recipient: string;
  templateKey: string;
  status: string;
  provider: string;
  skipReason: string | null;
  createdAt: string;
};

type ProviderSetting = {
  id: string;
  baseUrl: string;
  callbackBaseUrl: string;
  isSandbox: boolean;
  isActive: boolean;
  hasApiKey: boolean;
  hasSecretKey: boolean;
  updatedAt: string;
};

type SmtpRow = {
  id: string;
  host: string;
  port: number;
  encryption: string;
  username: string;
  hasPassword: boolean;
  fromName: string;
  fromEmail: string;
  isActive: boolean;
};

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

type BankRow = {
  id: string;
  bankName: string;
  accountHolder: string;
  iban: string;
  branchCode: string;
  accountNumber: string;
  currency: string;
  isActive: boolean;
};

export function OpsSettingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const initialTab: Tab =
    tabParam && TAB_VALUES.includes(tabParam as Tab) ? (tabParam as Tab) : 'payment';
  const [tab, setTab] = useState<Tab>(initialTab);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    const next: Tab =
      tabParam && TAB_VALUES.includes(tabParam as Tab) ? (tabParam as Tab) : 'payment';
    if (next !== tab) setTab(next);
  }, [tabParam, tab]);

  const selectTab = (next: Tab) => {
    setTab(next);
    setSearchParams(next === 'payment' ? {} : { tab: next }, { replace: true });
  }

  // Payment
  const [provider, setProvider] = useState<ProviderSetting | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('sandbox-api.iyzipay.com');
  const [callbackBaseUrl, setCallbackBaseUrl] = useState('');
  const [isSandbox, setIsSandbox] = useState(true);
  const [passFee, setPassFee] = useState(true);
  const [iyzicoTest, setIyzicoTest] = useState<{
    status: 'idle' | 'testing' | 'connected' | 'disconnected';
    message: string;
    latencyMs?: number;
    errorCode?: string;
  }>({ status: 'idle', message: '' });

  // Banks
  const [banks, setBanks] = useState<BankRow[]>([]);
  const [bankName, setBankName] = useState('');
  const [accountHolder, setAccountHolder] = useState('');
  const [iban, setIban] = useState('');
  const [branchCode, setBranchCode] = useState('');

  // SMTP
  const [smtp, setSmtp] = useState<SmtpRow | null>(null);
  const [host, setHost] = useState('');
  const [port, setPort] = useState(587);
  const [encryption, setEncryption] = useState('TLS');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fromName, setFromName] = useState('Tara Gold');
  const [fromEmail, setFromEmail] = useState('');
  const [testTo, setTestTo] = useState('');

  // Templates
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [editKey, setEditKey] = useState<string>('welcome');
  const [subject, setSubject] = useState('');
  const [bodyHtml, setBodyHtml] = useState('');

  // Messaging (SMS / WhatsApp)
  const [msgStatus, setMsgStatus] = useState<MessagingStatus | null>(null);
  const [msgLogs, setMsgLogs] = useState<MessagingLog[]>([]);

  const loadPayment = useCallback(async () => {
    const res = await apiFetch<ProviderSetting[]>('/api/v1/ops/payments/provider-settings?scope=platform');
    const row = (res.data ?? [])[0] ?? null;
    setProvider(row);
    if (row) {
      setBaseUrl(row.baseUrl || 'sandbox-api.iyzipay.com');
      setCallbackBaseUrl(row.callbackBaseUrl || '');
      setIsSandbox(row.isSandbox);
    }
  }, []);

  const loadSmtp = useCallback(async () => {
    const res = await apiFetch<SmtpRow[]>('/api/v1/ops/mail/smtp-settings');
    const platform = (res.data ?? []).find((r) => !(r as { organizationId?: string }).organizationId) ?? (res.data ?? [])[0] ?? null;
    setSmtp(platform);
    if (platform) {
      setHost(platform.host);
      setPort(platform.port);
      setEncryption(platform.encryption);
      setUsername(platform.username);
      setFromName(platform.fromName);
      setFromEmail(platform.fromEmail);
    }
  }, []);

  const loadTemplates = useCallback(async () => {
    const res = await apiFetch<TemplateRow[]>('/api/v1/ops/mail/templates');
    setTemplates(res.data ?? []);
  }, []);

  const loadBanks = useCallback(async () => {
    const res = await apiFetch<BankRow[]>('/api/v1/ops/payments/bank-accounts?scope=platform');
    setBanks(res.data ?? []);
  }, []);

  const loadMessaging = useCallback(async () => {
    const statusRes = await apiFetch<MessagingStatus>('/api/v1/ops/messaging/status');
    setMsgStatus(statusRes.data);
    const logsRes = await apiFetch<MessagingLog[]>('/api/v1/ops/messaging/logs?pageSize=20');
    setMsgLogs(Array.isArray(logsRes.data) ? logsRes.data : []);
  }, []);

  useEffect(() => {
    setError(null);
    setOk(null);
    void (async () => {
      try {
        if (tab === 'payment') await loadPayment();
        if (tab === 'banks') await loadBanks();
        if (tab === 'smtp') await loadSmtp();
        if (tab === 'templates') await loadTemplates();
        if (tab === 'messaging') await loadMessaging();
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Yüklenemedi');
      }
    })();
  }, [tab, loadPayment, loadBanks, loadSmtp, loadTemplates, loadMessaging]);

  useEffect(() => {
    const existing = templates.find((t) => t.templateKey === editKey);
    setSubject(existing?.subject ?? '');
    setBodyHtml(existing?.bodyHtml ?? '');
  }, [editKey, templates]);

  const testPaymentConnection = useCallback(async () => {
    setError(null);
    setIyzicoTest({ status: 'testing', message: 'iyzico API bağlantısı test ediliyor...' });
    try {
      const res = await apiFetch<{
        connected: boolean;
        status: 'connected' | 'disconnected';
        baseUrl: string;
        latencyMs: number;
        errorCode?: string;
        message: string;
      }>('/api/v1/ops/payments/provider-settings/test', {
        method: 'POST',
        body: {},
      });
      const data = res.data;
      if (data?.connected) {
        setIyzicoTest({
          status: 'connected',
          message: data.message,
          latencyMs: data.latencyMs,
        });
      } else {
        setIyzicoTest({
          status: 'disconnected',
          message: data?.message || 'iyzico bağlantısı kurulamadı.',
          latencyMs: data?.latencyMs,
          errorCode: data?.errorCode,
        });
      }
    } catch (e) {
      setIyzicoTest({
        status: 'disconnected',
        message: e instanceof Error ? e.message : 'Bağlantı testi başarısız.',
      });
    }
  }, []);

  useEffect(() => {
    if (
      tab === 'payment' &&
      provider?.hasApiKey &&
      provider?.hasSecretKey &&
      iyzicoTest.status === 'idle'
    ) {
      void testPaymentConnection();
    }
  }, [tab, provider?.hasApiKey, provider?.hasSecretKey, iyzicoTest.status, testPaymentConnection]);

  const savePayment = async () => {
    setError(null);
    setOk(null);
    try {
      await apiFetch('/api/v1/ops/payments/provider-settings', {
        method: 'POST',
        body: {
          apiKey: apiKey || undefined,
          secretKey: secretKey || undefined,
          baseUrl,
          callbackBaseUrl,
          isSandbox,
          passInstallmentFeeToCustomer: passFee,
          isActive: true,
        },
      });
      setApiKey('');
      setSecretKey('');
      setOk('Ödeme ayarları kaydedildi (anahtarlar AES-256 ile şifrelendi).');
      await loadPayment();
      await testPaymentConnection();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kaydedilemedi');
    }
  };

  const saveBank = async () => {
    setError(null);
    setOk(null);
    try {
      await apiFetch('/api/v1/ops/payments/bank-accounts', {
        method: 'POST',
        body: {
          bankName,
          accountHolder,
          iban,
          branchCode,
          currency: 'TRY',
          isActive: true,
        },
      });
      setBankName('');
      setAccountHolder('');
      setIban('');
      setBranchCode('');
      setOk('Banka hesabı eklendi.');
      await loadBanks();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Banka kaydedilemedi');
    }
  };

  const saveSmtp = async () => {
    setError(null);
    setOk(null);
    try {
      await apiFetch('/api/v1/ops/mail/smtp-settings', {
        method: 'POST',
        body: {
          host,
          port,
          encryption,
          username,
          password: password || undefined,
          fromName,
          fromEmail,
          isActive: true,
        },
      });
      setPassword('');
      setOk('SMTP ayarları kaydedildi.');
      await loadSmtp();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kaydedilemedi');
    }
  };

  const sendTestMail = async () => {
    setError(null);
    setOk(null);
    try {
      const res = await apiFetch<{ to: string }>('/api/v1/ops/mail/smtp-settings/test', {
        method: 'POST',
        body: { to: testTo || undefined },
      });
      setOk(`Test maili kuyruğa alındı → ${res.data?.to ?? testTo}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Test maili gönderilemedi');
    }
  };

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

  const tabs: { id: Tab; label: string; icon: typeof CreditCard }[] = [
    { id: 'payment', label: 'Ödeme Ayarları', icon: CreditCard },
    { id: 'banks', label: 'Banka Hesapları', icon: Landmark },
    { id: 'smtp', label: 'E-posta (SMTP)', icon: Mail },
    { id: 'templates', label: 'Şablon Editörü', icon: FileText },
    { id: 'messaging', label: 'SMS / WhatsApp', icon: MessageSquare },
  ];

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Site Sahibi · Super Admin"
        title="Sistem Ayarları"
        description="iyzico ödeme kimlik bilgileri, dinamik SMTP ve transactional e-posta şablonları."
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-3">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => selectTab(t.id)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                active ? 'bg-zinc-900 text-white' : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      )}
      {ok && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {ok}
        </div>
      )}

      {tab === 'payment' && (
        <PortalDataCard title="iyzico API Kimlik Bilgileri" contentClassName="p-6 space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {provider?.hasApiKey ? <Badge variant="secondary">API Key tanımlı</Badge> : <Badge variant="outline">API Key yok</Badge>}
            {provider?.hasSecretKey ? (
              <Badge variant="secondary">Secret Key tanımlı</Badge>
            ) : (
              <Badge variant="outline">Secret Key yok</Badge>
            )}
            <Badge variant="outline">{isSandbox ? 'Sandbox' : 'Production'}</Badge>
            {iyzicoTest.status === 'connected' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium text-[11px]">
                <span className="w-2 h-2 rounded-full bg-emerald-600" />
                Bağlı {iyzicoTest.latencyMs != null ? `(${iyzicoTest.latencyMs} ms)` : ''}
              </span>
            )}
            {iyzicoTest.status === 'disconnected' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-red-100 text-red-800 font-medium text-[11px]">
                <span className="w-2 h-2 rounded-full bg-red-600" />
                Kopuk
              </span>
            )}
            {iyzicoTest.status === 'testing' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-zinc-100 text-zinc-700 font-medium text-[11px]">
                Test ediliyor...
              </span>
            )}
            {iyzicoTest.status === 'idle' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-zinc-100 text-zinc-600 font-medium text-[11px]">
                Test edilmedi
              </span>
            )}
          </div>

          {iyzicoTest.status === 'connected' && (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-xs text-emerald-800 font-medium">
              {iyzicoTest.message}
            </div>
          )}
          {iyzicoTest.status === 'disconnected' && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-800 font-medium">
              {iyzicoTest.message}
              {iyzicoTest.errorCode ? ` (Kod: ${iyzicoTest.errorCode})` : ''}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>API Key</Label>
              <Input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider?.hasApiKey ? '•••• (değiştirmek için yazın)' : 'sandbox-…'}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Secret Key</Label>
              <Input
                type="password"
                value={secretKey}
                onChange={(e) => setSecretKey(e.target.value)}
                placeholder={provider?.hasSecretKey ? '•••• (değiştirmek için yazın)' : 'sandbox-…'}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Base URL</Label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Callback Base URL</Label>
              <Input
                value={callbackBaseUrl}
                onChange={(e) => setCallbackBaseUrl(e.target.value)}
                placeholder="https://api.example.com"
              />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input
                id="sandbox"
                type="checkbox"
                checked={isSandbox}
                onChange={(e) => {
                  setIsSandbox(e.target.checked);
                  setBaseUrl(e.target.checked ? 'sandbox-api.iyzipay.com' : 'api.iyzipay.com');
                }}
              />
              <Label htmlFor="sandbox">Sandbox ortamı</Label>
            </div>
            <div className="flex items-center gap-2 pt-2 md:col-span-2">
              <input
                id="passFee"
                type="checkbox"
                checked={passFee}
                onChange={(e) => setPassFee(e.target.checked)}
              />
              <Label htmlFor="passFee">Taksit vade farkını müşteriye yansıt</Label>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => void savePayment()}>
              Kaydet
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={iyzicoTest.status === 'testing'}
              onClick={() => void testPaymentConnection()}
            >
              {iyzicoTest.status === 'testing' ? 'Test Ediliyor...' : 'Bağlantıyı Test Et'}
            </Button>
          </div>
        </PortalDataCard>
      )}

      {tab === 'banks' && (
        <div className="space-y-4">
          <PortalDataCard title="Yeni Havale Hesabı" contentClassName="p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Banka Adı</Label>
                <Input value={bankName} onChange={(e) => setBankName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Hesap Sahibi</Label>
                <Input value={accountHolder} onChange={(e) => setAccountHolder(e.target.value)} />
              </div>
              <div className="space-y-1.5 md:col-span-2">
                <Label>IBAN</Label>
                <Input value={iban} onChange={(e) => setIban(e.target.value)} placeholder="TR…" />
              </div>
              <div className="space-y-1.5">
                <Label>Şube Kodu</Label>
                <Input value={branchCode} onChange={(e) => setBranchCode(e.target.value)} />
              </div>
            </div>
            <Button
              type="button"
              variant="success"
              onClick={() => void saveBank()}
              disabled={!bankName || !iban || !accountHolder}
            >
              Hesap Ekle
            </Button>
          </PortalDataCard>
          <PortalDataCard title={`Aktif Hesaplar (${banks.length})`} contentClassName="p-6 space-y-3">
            {banks.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Henüz hesap yok. Havale siparişleri için en az bir platform hesabı ekleyin.
              </p>
            ) : (
              banks.map((b) => (
                <div
                  key={b.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3 text-xs"
                >
                  <div>
                    <div className="font-medium">{b.bankName}</div>
                    <div className="text-muted-foreground">{b.accountHolder}</div>
                    <div className="font-mono mt-1">{b.iban}</div>
                  </div>
                  <Badge variant={b.isActive ? 'secondary' : 'outline'}>
                    {b.isActive ? 'Aktif' : 'Pasif'}
                  </Badge>
                </div>
              ))
            )}
          </PortalDataCard>
        </div>
      )}

      {tab === 'smtp' && (
        <PortalDataCard title="Platform SMTP" contentClassName="p-6 space-y-4">
          {smtp && (
            <p className="text-xs text-muted-foreground">
              Son kayıt: {smtp.host}:{smtp.port} · {smtp.hasPassword ? 'Şifre tanımlı' : 'Şifre yok'}
            </p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Host</Label>
              <Input value={host} onChange={(e) => setHost(e.target.value)} placeholder="smtp.example.com" />
            </div>
            <div className="space-y-1.5">
              <Label>Port</Label>
              <Input
                type="number"
                value={port}
                onChange={(e) => setPort(Number(e.target.value) || 587)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Encryption</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={encryption}
                onChange={(e) => setEncryption(e.target.value)}
              >
                <option value="TLS">TLS (587)</option>
                <option value="SSL">SSL (465)</option>
                <option value="NONE">NONE</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Kullanıcı Adı</Label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Şifre</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={smtp?.hasPassword ? '•••• (değiştirmek için yazın)' : ''}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Gönderici Adı</Label>
              <Input value={fromName} onChange={(e) => setFromName(e.target.value)} />
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label>Gönderici E-posta</Label>
              <Input type="email" value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => void saveSmtp()}>
              Kaydet
            </Button>
            <div className="flex items-center gap-2">
              <Input
                className="w-56"
                type="email"
                placeholder="Test alıcısı (opsiyonel)"
                value={testTo}
                onChange={(e) => setTestTo(e.target.value)}
              />
              <Button type="button" variant="outline" onClick={() => void sendTestMail()}>
                <Send className="w-4 h-4" />
                Test Maili Gönder
              </Button>
            </div>
          </div>
        </PortalDataCard>
      )}

      {tab === 'templates' && (
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
      )}

      {tab === 'messaging' && (
        <div className="space-y-4">
          <PortalDataCard title="Kanal Durumu" contentClassName="p-6 space-y-3">
            <p className="text-xs text-muted-foreground">
              Ortam değişkenleri: <code>MESSAGING_SMS_ENABLED</code>,{' '}
              <code>MESSAGING_WHATSAPP_ENABLED</code>, provider = console | webhook.
              Recovery: T2→SMS, T3→WhatsApp (ticari izin + telefon zorunlu).
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-border p-3 text-sm space-y-1">
                <div className="font-medium">SMS</div>
                <Badge variant={msgStatus?.smsEnabled ? 'secondary' : 'outline'}>
                  {msgStatus?.smsEnabled ? 'Açık' : 'Kapalı'}
                </Badge>
                <div className="text-xs text-muted-foreground font-mono">
                  {msgStatus?.smsProvider || '—'}
                  {msgStatus?.smsWebhookConfigured ? ' · webhook OK' : ''}
                </div>
              </div>
              <div className="rounded-md border border-border p-3 text-sm space-y-1">
                <div className="font-medium">WhatsApp</div>
                <Badge variant={msgStatus?.whatsappEnabled ? 'secondary' : 'outline'}>
                  {msgStatus?.whatsappEnabled ? 'Açık' : 'Kapalı'}
                </Badge>
                <div className="text-xs text-muted-foreground font-mono">
                  {msgStatus?.whatsappProvider || '—'}
                  {msgStatus?.whatsappWebhookConfigured ? ' · webhook OK' : ''}
                </div>
              </div>
            </div>
          </PortalDataCard>
          <PortalDataCard title="Son Gönderimler" contentClassName="divide-y divide-border">
            {msgLogs.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">Henüz kanal logu yok.</p>
            ) : (
              msgLogs.map((log) => (
                <div key={log.id} className="px-4 py-3 text-xs flex flex-wrap gap-3 justify-between">
                  <span className="font-mono">
                    {log.channel} · {log.recipient}
                  </span>
                  <span>
                    <Badge variant="outline">{log.status}</Badge>
                    {log.skipReason ? ` · ${log.skipReason}` : ''}
                  </span>
                  <span className="text-muted-foreground">
                    {new Date(log.createdAt).toLocaleString('tr-TR')}
                  </span>
                </div>
              ))
            )}
          </PortalDataCard>
        </div>
      )}
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { ShieldCheck, User, Send, RotateCcw } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Card,
  CardContent,
  Input,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import { useB2bOrdersQuery } from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';
import { BackendPendingNotice } from '@taragold/shared/components/PortalRouteGuard';
import { apiFetch } from '@taragold/shared/lib/api/client';

export function B2bCurrentAccountPage() {
  const { activeOrganization } = useAuth();
  const ordersQuery = useB2bOrdersQuery();
  const orders = ordersQuery.data ?? [];

  const creditLimitUsd = Number(activeOrganization?.creditLimitUsd ?? 0);
  const usedCreditUsd = Number(activeOrganization?.usedCreditUsd ?? 0);
  const remainingCreditUsd = Math.max(0, creditLimitUsd - usedCreditUsd);
  const creditPct = creditLimitUsd > 0 ? Math.min(100, (usedCreditUsd / creditLimitUsd) * 100) : 0;

  const hasLimitGram = Number(activeOrganization?.hasLimitGram ?? 0);
  const usedHasGram = Number(activeOrganization?.usedHasGram ?? 0);
  const remainingHasGram = Math.max(0, hasLimitGram - usedHasGram);
  const hasPct = hasLimitGram > 0 ? Math.min(100, (usedHasGram / hasLimitGram) * 100) : 0;

  const activeOrders = orders.filter(
    (o) => o.status !== 'IPTAL_EDILDI' && o.status !== 'IADE_EDILDI'
  );
  const totalOrderHas = activeOrders.reduce((s, o) => s + (o.totalHasGoldGram ?? 0), 0);
  const totalOrderUsd = activeOrders.reduce((s, o) => s + o.totalWholesaleUsd, 0);

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow={`${activeOrganization?.name ?? 'Bayi Firması'} · Finansal Limitler &amp; Has Bakiye`}
        title="Cari Hesap &amp; Limitler"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card className="shadow-none">
          <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Has Altın Limiti (995/999)
            </span>
            <span className="font-mono text-xs text-muted-foreground tabular-nums">
              %{formatTrNumber(hasPct, 1)} Kullanım
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 font-mono tabular-nums">
            <div>
              <div className="font-sans text-[11px] text-muted-foreground">Toplam Limit</div>
              <div className="text-base font-semibold text-foreground mt-0.5">
                {formatTrNumber(hasLimitGram, 2)} gr
              </div>
            </div>
            <div>
              <div className="font-sans text-[11px] text-muted-foreground">Açık Bakiye</div>
              <div className="text-base font-semibold text-muted-foreground mt-0.5">
                {formatTrNumber(usedHasGram, 2)} gr
              </div>
            </div>
            <div>
              <div className="font-sans text-[11px] text-muted-foreground">Kullanılabilir</div>
              <div className="text-base font-semibold text-emerald-700 mt-0.5">
                {formatTrNumber(remainingHasGram, 2)} gr
              </div>
            </div>
          </div>
          <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-foreground/80" style={{ width: `${hasPct}%` }} />
          </div>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Döviz Cari Kredi Limiti (USD)
              </span>
              <span className="font-mono text-xs text-muted-foreground tabular-nums">
                %{formatTrNumber(creditPct, 1)} Kullanım
              </span>
            </div>
            <div className="grid grid-cols-3 gap-3 font-mono tabular-nums">
              <div>
                <div className="font-sans text-[11px] text-muted-foreground">Toplam Limit</div>
                <div className="text-base font-semibold text-foreground mt-0.5">
                  ${formatTrNumber(creditLimitUsd, 0)}
                </div>
              </div>
              <div>
                <div className="font-sans text-[11px] text-muted-foreground">Açık Cari</div>
                <div className="text-base font-semibold text-foreground mt-0.5">
                  ${formatTrNumber(usedCreditUsd, 0)}
                </div>
              </div>
              <div>
                <div className="font-sans text-[11px] text-muted-foreground">Kullanılabilir</div>
                <div className="text-base font-semibold text-emerald-700 mt-0.5">
                  ${formatTrNumber(remainingCreditUsd, 0)}
                </div>
              </div>
            </div>
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-foreground" style={{ width: `${creditPct}%` }} />
            </div>
          </CardContent>
        </Card>
      </div>

      <BackendPendingNotice
        title="Detaylı Cari Ekstre / Tahsilat Hareketleri API'si Henüz Açık Değil"
        description="Backend tarafında DealerLedgerEntry kayıtları sipariş ve iptal/iade işlemlerinde otomatik tutulmaktadır; ancak kronolojik cari hesap hareket listesi ve tahsilat/has teslimat dekontu sorgulama endpoint'i henüz dışa açılmamıştır. Aşağıda sipariş kaynaklı borç özetiniz görüntülenir."
        endpointHint="GET /api/v1/b2b/ledger"
      />

      <PortalDataCard
        title={`Sipariş Kaynaklı Hesaplaşma Özeti (${activeOrders.length} aktif sipariş)`}
        toolbar={
          <div className="font-mono text-xs text-muted-foreground tabular-nums">
            Toplam: {formatTrNumber(totalOrderHas, 4)} gr Has · ${formatTrNumber(totalOrderUsd, 2)}
          </div>
        }
      >
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Fiş No</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Tarih</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Hesaplaşma</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Has Altın</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">İşçilik+Taş</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Toplam USD</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((order) => (
              <TableRow key={order.orderNo}>
                <TableCell className="px-4 font-mono font-medium text-foreground">
                  {order.orderNo}
                </TableCell>
                <TableCell className="px-4 text-muted-foreground tabular-nums">
                  {new Date(order.createdAt).toLocaleDateString('tr-TR')}
                </TableCell>
                <TableCell className="px-4 text-muted-foreground">{order.settlementMethod}</TableCell>
                <TableCell className="px-4 text-right font-mono text-muted-foreground tabular-nums">
                  {formatTrNumber(order.totalHasGoldGram ?? 0, 4)} gr
                </TableCell>
                <TableCell className="px-4 text-right font-mono tabular-nums text-muted-foreground">
                  ${formatTrNumber(order.totalLaborAndStoneUsd ?? 0, 2)}
                </TableCell>
                <TableCell className="px-4 text-right font-mono font-semibold text-foreground tabular-nums">
                  ${formatTrNumber(order.totalWholesaleUsd, 2)}
                </TableCell>
              </TableRow>
            ))}
            {orders.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                  Henüz sipariş kaynaklı hareket bulunmuyor.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </PortalDataCard>
    </div>
  );
}

export function B2bCompanyUsersPage() {
  const { user, activeMembership, activeOrganization } = useAuth();

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow={`${activeOrganization?.name ?? 'Bayi Firması'} · Kurumsal Erişim`}
        title="Firma Kullanıcıları"
      />

      <BackendPendingNotice
        title="Firma Kullanıcı Yönetimi API'si Backend'de Henüz Tanımlı Değil"
        description="Aynı bayi firmasına bağlı diğer çalışanları listeleme, yeni kullanıcı davet etme ve şube/rol atama işlemleri için backend uç noktaları henüz açılmamıştır. Aşağıda yalnızca aktif oturumunuza ait sunucu doğrulamalı yetki kaydı görüntülenir."
        endpointHint="GET / POST / PATCH /api/v1/b2b/organization/users"
      />

      <PortalDataCard title="Aktif Oturum Kullanıcısı" contentClassName="p-6 space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <User className="w-4 h-4 text-muted-foreground" />
          Oturum detayı
        </div>
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <dt className="text-muted-foreground">Ad Soyad</dt>
            <dd className="font-medium text-foreground mt-0.5">{user.fullName}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Kurumsal E-posta</dt>
            <dd className="font-medium text-foreground mt-0.5">{user.email}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Rol Anahtarı</dt>
            <dd className="font-mono text-foreground mt-0.5">
              {activeMembership?.roleKey ?? user.roleKey}
            </dd>
          </div>
        </dl>

        <div className="pt-4 border-t border-border space-y-2">
          <div className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-muted-foreground" />
            Sunucu Tarafından Atanmış Aktif Yetkiler
          </div>
          <div className="flex flex-wrap gap-1.5">
            {user.capabilities.map((cap) => (
              <Badge key={cap} variant="secondary" className="font-mono text-[11px]">
                {cap}
              </Badge>
            ))}
          </div>
        </div>
      </PortalDataCard>
    </div>
  );
}

export function B2bCompanySettingsPage() {
  const { activeOrganization } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const [host, setHost] = useState('');
  const [port, setPort] = useState(587);
  const [encryption, setEncryption] = useState('TLS');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fromName, setFromName] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [testTo, setTestTo] = useState('');

  const [apiKey, setApiKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('sandbox-api.iyzipay.com');
  const [isSandbox, setIsSandbox] = useState(true);
  const [hasProviderKeys, setHasProviderKeys] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [smtpRes, payRes] = await Promise.all([
        apiFetch<
          Array<{
            host: string;
            port: number;
            encryption: string;
            username: string;
            fromName: string;
            fromEmail: string;
            hasPassword: boolean;
          }>
        >('/api/v1/ops/mail/smtp-settings'),
        apiFetch<
          Array<{ hasApiKey: boolean; hasSecretKey: boolean; baseUrl: string; isSandbox: boolean }>
        >('/api/v1/ops/payments/provider-settings'),
      ]);
      const smtp = (smtpRes.data ?? [])[0];
      if (smtp) {
        setHost(smtp.host);
        setPort(smtp.port);
        setEncryption(smtp.encryption);
        setUsername(smtp.username);
        setFromName(smtp.fromName);
        setFromEmail(smtp.fromEmail);
      }
      const pay = (payRes.data ?? [])[0];
      if (pay) {
        setHasProviderKeys(Boolean(pay.hasApiKey && pay.hasSecretKey));
        setBaseUrl(pay.baseUrl || 'sandbox-api.iyzipay.com');
        setIsSandbox(pay.isSandbox);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ayarlar yüklenemedi');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

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
          fromName: fromName || activeOrganization?.name || 'Tara Gold Bayi',
          fromEmail,
          isActive: true,
        },
      });
      if (logoUrl) {
        await apiFetch('/api/v1/ops/mail/templates', {
          method: 'POST',
          body: {
            templateKey: 'welcome',
            subject: 'Hoş geldiniz',
            bodyHtml: '<p>Merhaba {{ customer_name }}</p>',
            logoUrl,
            isActive: true,
          },
        });
      }
      setPassword('');
      setOk('Firma SMTP ayarları kaydedildi. Tanımlı değilse platform SMTP kullanılır.');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'SMTP kaydedilemedi');
    }
  };

  const sendTest = async () => {
    setError(null);
    setOk(null);
    try {
      const res = await apiFetch<{ to: string }>('/api/v1/ops/mail/smtp-settings/test', {
        method: 'POST',
        body: { to: testTo || undefined },
      });
      setOk(`Test maili kuyruğa alındı → ${res.data?.to ?? ''}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Test başarısız');
    }
  };

  const saveIyzico = async () => {
    setError(null);
    setOk(null);
    try {
      await apiFetch('/api/v1/ops/payments/provider-settings', {
        method: 'POST',
        body: {
          apiKey: apiKey || undefined,
          secretKey: secretKey || undefined,
          baseUrl,
          isSandbox,
          isActive: true,
        },
      });
      setApiKey('');
      setSecretKey('');
      setOk('Firma iyzico bilgileri kaydedildi (AES-256). Boş bırakılırsa platform ayarlarına düşülür.');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'iyzico kaydedilemedi');
    }
  };

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Kurumsal Profil &amp; Yetkili Şubeler"
        title="Firma Ayarları"
        description="SMTP, logo ve isteğe bağlı iyzico alt üye işyeri bilgileri. Tanımlanmazsa Super Admin ayarlarına fallback yapılır."
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      )}
      {ok && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {ok}
        </div>
      )}

      <BackendPendingNotice
        title="Firma Profili Güncelleme API'si Backend'de Henüz Tanımlı Değil"
        description="Firma ünvanı, vergi bilgisi, fatura adresi ve şube düzenleme işlemleri için backend güncelleme endpoint'i henüz bulunmamaktadır. Mevcut kurumsal kayıtlarınız salt okunur olarak sunulmaktadır."
        endpointHint="PATCH /api/v1/b2b/organization"
      />

      {activeOrganization && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <PortalDataCard
            title="Kurumsal Firma Bilgileri"
            className="lg:col-span-7"
            contentClassName="p-6 space-y-4"
          >
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <dt className="text-slate-500">Firma Ünvanı</dt>
                <dd className="font-medium text-slate-950 mt-0.5">{activeOrganization.name}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Bayi Kodu</dt>
                <dd className="font-mono font-medium text-slate-950 mt-0.5">
                  {activeOrganization.code}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Vergi Dairesi &amp; No</dt>
                <dd className="font-medium text-slate-950 mt-0.5">
                  {activeOrganization.taxOfficeAndNo || '—'}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Yetkili İrtibat</dt>
                <dd className="font-medium text-slate-950 mt-0.5">
                  {activeOrganization.contactName || '—'}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Şehir</dt>
                <dd className="font-medium text-slate-950 mt-0.5">
                  {activeOrganization.city || '—'}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Varsayılan Konsinye Vadesi</dt>
                <dd className="font-mono text-slate-950 mt-0.5">
                  {activeOrganization.defaultConsignmentDays} gün
                </dd>
              </div>
            </dl>
          </PortalDataCard>

          <PortalDataCard
            title={`Yetkili Şubeler (${activeOrganization.branches.length})`}
            className="lg:col-span-5"
            contentClassName="p-6 space-y-4"
          >
            {activeOrganization.branches.length === 0 ? (
              <p className="text-xs text-slate-500">
                Üyeliğinize atanmış aktif şube bulunmuyor.
              </p>
            ) : (
              <div className="space-y-2.5">
                {activeOrganization.branches.map((branch) => (
                  <div
                    key={branch.id}
                    className="p-3 rounded-md border border-slate-200 bg-slate-50/70 text-xs flex items-center justify-between"
                  >
                    <div>
                      <div className="font-medium text-slate-950">{branch.name}</div>
                      <div className="text-[11px] text-slate-500">
                        {branch.code} · {branch.city}
                      </div>
                      {branch.address && (
                        <div className="text-[11px] text-slate-500 mt-0.5">{branch.address}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </PortalDataCard>
        </div>
      )}

      <PortalDataCard title="Firma SMTP &amp; Logo" contentClassName="p-6 space-y-4">
        <p className="text-xs text-muted-foreground">
          Tanımlanmazsa sistem Super Admin platform SMTP ayarlarına düşer.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Host</Label>
            <Input value={host} onChange={(e) => setHost(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Port</Label>
            <Input type="number" value={port} onChange={(e) => setPort(Number(e.target.value) || 587)} />
          </div>
          <div className="space-y-1.5">
            <Label>Encryption</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={encryption}
              onChange={(e) => setEncryption(e.target.value)}
            >
              <option value="TLS">TLS</option>
              <option value="SSL">SSL</option>
              <option value="NONE">NONE</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <Label>Kullanıcı</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Şifre</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Gönderici Adı</Label>
            <Input value={fromName} onChange={(e) => setFromName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Gönderici Mail</Label>
            <Input type="email" value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Logo URL (şablon)</Label>
            <Input value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} placeholder="https://…" />
          </div>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <Button type="button" onClick={() => void saveSmtp()}>
            SMTP Kaydet
          </Button>
          <Input
            className="w-52"
            placeholder="Test alıcısı"
            value={testTo}
            onChange={(e) => setTestTo(e.target.value)}
          />
          <Button type="button" variant="outline" onClick={() => void sendTest()}>
            <Send className="w-4 h-4" />
            Test Maili
          </Button>
        </div>
      </PortalDataCard>

      <PortalDataCard title="Firma Havale Hesapları" contentClassName="p-6 space-y-4">
        <p className="text-xs text-muted-foreground">
          Tanımlanmazsa platform (Super Admin) banka hesapları kullanılır. B2B pazaryeri
          senaryoları için firmaya özel IBAN ekleyin.
        </p>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            void (async () => {
              const name = window.prompt('Banka adı');
              const holder = window.prompt('Hesap sahibi');
              const ibanVal = window.prompt('IBAN');
              if (!name || !holder || !ibanVal) return;
              try {
                await apiFetch('/api/v1/ops/payments/bank-accounts', {
                  method: 'POST',
                  body: {
                    bankName: name,
                    accountHolder: holder,
                    iban: ibanVal,
                    currency: 'TRY',
                    isActive: true,
                  },
                });
                setOk('Banka hesabı eklendi.');
              } catch (e) {
                setError(e instanceof Error ? e.message : 'Banka eklenemedi');
              }
            })();
          }}
        >
          Banka Hesabı Ekle
        </Button>
      </PortalDataCard>

      <PortalDataCard title="iyzico Alt Üye İşyeri (Opsiyonel)" contentClassName="p-6 space-y-4">
        <p className="text-xs text-muted-foreground">
          {hasProviderKeys
            ? 'Firma anahtarları tanımlı.'
            : 'Tanımlı değil — ödemelerde platform (Super Admin) iyzico ayarları kullanılır.'}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>API Key</Label>
            <Input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Secret Key</Label>
            <Input type="password" value={secretKey} onChange={(e) => setSecretKey(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Base URL</Label>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </div>
          <div className="flex items-center gap-2 pt-6">
            <input
              id="b2b-sandbox"
              type="checkbox"
              checked={isSandbox}
              onChange={(e) => setIsSandbox(e.target.checked)}
            />
            <Label htmlFor="b2b-sandbox">Sandbox</Label>
          </div>
        </div>
        <Button type="button" onClick={() => void saveIyzico()}>
          iyzico Kaydet
        </Button>
      </PortalDataCard>
    </div>
  );
}

export function B2bMailLogsPage() {
  const [rows, setRows] = useState<
    Array<{
      id: string;
      recipient: string;
      templateKey: string;
      subject: string;
      status: string;
      errorMessage: string;
      createdAt: string;
    }>
  >([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await apiFetch<typeof rows>('/api/v1/ops/mail/logs');
      setRows(res.data ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Yüklenemedi');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const retry = async (id: string) => {
    try {
      await apiFetch(`/api/v1/ops/mail/logs/${id}/retry`, { method: 'POST' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retry başarısız');
    }
  };

  return (
    <div className="space-y-6">
      <PortalPageHeader eyebrow="Firma İletişim" title="Mail Logları" />
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      )}
      <PortalDataCard title={`Kayıtlar (${rows.length})`} contentClassName="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Alıcı</TableHead>
              <TableHead>Şablon</TableHead>
              <TableHead>Durum</TableHead>
              <TableHead>Hata</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="text-xs">{r.recipient}</TableCell>
                <TableCell className="font-mono text-xs">{r.templateKey}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{r.status}</Badge>
                </TableCell>
                <TableCell className="text-[11px] text-red-700 max-w-[200px] truncate">
                  {r.errorMessage || '—'}
                </TableCell>
                <TableCell className="text-right">
                  {r.status === 'FAILED' && (
                    <Button size="sm" variant="outline" onClick={() => void retry(r.id)}>
                      <RotateCcw className="w-3.5 h-3.5" />
                      Tekrar
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-8">
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

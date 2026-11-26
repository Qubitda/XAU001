import { FormEvent, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Lock,
  Mail,
  MapPin,
  Phone,
  Scale,
  ShieldCheck,
} from 'lucide-react';
import { Button, Input, Label } from '@taragold/shared/components/ui';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import {
  BackendPendingNotice,
  hasB2bAccess,
  resolveHomeForSession,
} from '@taragold/shared/components/PortalRouteGuard';
import {
  isB2cStorefrontEnabled,
  isOpsPortalEnabled,
} from '@taragold/shared/config/commercialModules';

const STOREFRONT_URL = import.meta.env.VITE_STOREFRONT_URL || 'http://localhost:3000/';
const OPS_URL = import.meta.env.VITE_OPS_URL || 'http://localhost:3002/ops/giris';

export function B2bLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, switchMembership, isLoggingIn } = useAuth();

  const [tab, setTab] = useState<'login' | 'apply'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [applyAttempted, setApplyAttempted] = useState(false);

  const from = (location.state as { from?: string } | null)?.from;

  const handleLoginSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const session = await login({ email: email.trim(), password });
      if (!hasB2bAccess(session)) {
        setError(
          'Bu hesapta tanımlı B2B bayi üyeliği bulunmuyor. Yetkili portalınıza yönlendiriliyorsunuz...'
        );
        window.setTimeout(() => {
          navigate(resolveHomeForSession(session), { replace: true });
        }, 1200);
        return;
      }

      const b2bMembership = session.memberships.find((m) => m.audience === 'b2b');
      if (b2bMembership && session.activeMembershipId !== b2bMembership.id) {
        await switchMembership(b2bMembership.id);
      }

      const target =
        from && from.startsWith('/b2b/') && from !== '/b2b/giris' ? from : '/b2b/panel';
      navigate(target, { replace: true });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Giriş yapılamadı. Bilgilerinizi kontrol ediniz.'
      );
    }
  };

  return (
    <div className="min-h-screen bg-background grid grid-cols-1 lg:grid-cols-12 font-sans">
      <div className="lg:col-span-5 bg-zinc-950 text-zinc-100 p-7 sm:p-11 lg:p-14 flex flex-col justify-between gap-10">
        <div className="space-y-7">
          <div className="space-y-2.5">
            <div className="text-label text-xl tracking-tight text-white">TARA GOLD</div>
            <div className="flex items-center gap-2.5 pt-1">
              <span className="w-6 h-px bg-zinc-700" aria-hidden="true" />
              <span className="text-[11px] uppercase tracking-wider text-zinc-400">
                Kurumsal B2B Bayi Portalı
              </span>
            </div>
          </div>

          <div className="space-y-3 pt-2">
            <h1 className="text-page-title text-white max-w-md">
              Kuyumculuk Profesyonelleri İçin Güvenilir Toptan Sipariş Altyapısı
            </h1>
            <p className="text-caption text-zinc-400 leading-relaxed max-w-md">
              Canlı Has Altın ve döviz kurlarıyla anlık toptan fiyatlama, çoklu ölçü asorti sipariş
              fişi, cari limit takibi ve proforma otomasyonu tek kurumsal portalda.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 pt-2 text-caption">
            <div className="flex items-start gap-3.5 p-4 rounded-md border border-zinc-800 bg-zinc-900/80">
              <Scale className="w-4 h-4 text-zinc-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-label text-zinc-100">Has + İşçilik &amp; Döviz Hesaplaşma</div>
                <p className="text-zinc-400 leading-relaxed">
                  Fire dahil has gram hesabı, konsinye vade yönetimi ve açık cari limit kontrolü.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3.5 p-4 rounded-md border border-zinc-800 bg-zinc-900/80">
              <Building2 className="w-4 h-4 text-zinc-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-label text-zinc-100">Çoklu Şube &amp; Yetkili İzolasyonu</div>
                <p className="text-zinc-400 leading-relaxed">
                  Her kurumsal bayi yalnızca kendi onaylı şube, fiyatlandırma ve sipariş kayıtlarını
                  görür.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-zinc-800 pt-6 space-y-2.5 text-caption">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 font-medium">
            Bayi Destek &amp; Toptan Masası
          </div>
          <div className="flex flex-wrap items-center gap-2 text-zinc-200">
            <Phone className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
            <span className="font-sku tabular-nums">+90 (212) 519 40 10</span>
            <span className="text-zinc-500">· Hafta içi 09:00 – 18:30</span>
          </div>
          <div className="flex items-center gap-2 text-zinc-200">
            <Mail className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
            <span>bayi@taradiamond.com.tr</span>
          </div>
          <div className="flex items-start gap-2 text-zinc-400">
            <MapPin className="w-3.5 h-3.5 text-zinc-500 shrink-0 mt-0.5" />
            <span>Nuruosmaniye Cad. No:54 Kat:2 Fatih / İstanbul</span>
          </div>
        </div>
      </div>

      <div className="lg:col-span-7 flex items-center justify-center p-5 sm:p-10 lg:p-14">
        <div className="max-w-md w-full space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2 text-caption">
            {isB2cStorefrontEnabled() ? (
              <a
                href={STOREFRONT_URL}
                className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>B2C Mağazaya Dön</span>
              </a>
            ) : (
              <span className="text-muted-foreground">B2C vitrin dahil değil</span>
            )}
            {isOpsPortalEnabled() ? (
              <a href={OPS_URL} className="hover:text-foreground transition-colors">
                OPS Yönetici Girişi
              </a>
            ) : null}
          </div>

          <div className="bg-card border border-border rounded-lg p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="grid grid-cols-2 rounded-md border border-border bg-muted p-1 text-caption">
              <button
                type="button"
                onClick={() => setTab('login')}
                className={`min-h-[38px] rounded-sm font-medium transition-colors cursor-pointer ${
                  tab === 'login' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Bayi Girişi
              </button>
              <button
                type="button"
                onClick={() => setTab('apply')}
                className={`min-h-[38px] rounded-sm font-medium transition-colors cursor-pointer ${
                  tab === 'apply' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Bayilik Başvurusu
              </button>
            </div>

            {tab === 'login' ? (
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div className="space-y-1">
                  <h2 className="text-page-title text-xl">Kurumsal Bayi Girişi</h2>
                  <p className="text-caption">
                    Yetkili kurumsal e-posta ve parolanız ile B2B portalına giriş yapın.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="b2b-email">Kurumsal E-posta</Label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <Input
                      id="b2b-email"
                      type="email"
                      required
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="yetkili@firmaniz.com.tr"
                      className="pl-10"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor="b2b-password">Şifre</Label>
                    {isB2cStorefrontEnabled() ? (
                      <a
                        href={`${STOREFRONT_URL}sifre-yenile`}
                        className="text-caption hover:text-foreground hover:underline underline-offset-4"
                      >
                        Şifremi Unuttum
                      </a>
                    ) : null}
                  </div>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <Input
                      id="b2b-password"
                      type="password"
                      required
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="pl-10"
                    />
                  </div>
                </div>

                {error && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-caption text-destructive leading-relaxed">
                    {error}
                  </div>
                )}

                <Button type="submit" disabled={isLoggingIn} className="w-full">
                  <span>{isLoggingIn ? 'Doğrulanıyor...' : 'Bayi Portalına Giriş Yap'}</span>
                  {!isLoggingIn && <ArrowRight className="w-4 h-4" />}
                </Button>

                <div className="pt-2 border-t border-border flex items-start gap-2 text-[11px] text-muted-foreground leading-relaxed">
                  <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>
                    Firma, şube ve cari yetkileriniz şifreli sunucu oturumu ile otomatik olarak
                    doğrulanır.
                  </span>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div className="space-y-1">
                  <h2 className="text-page-title text-xl">Bayilik Başvurusu</h2>
                  <p className="text-caption">
                    Kuyumculuk yetki belgesine sahip mağaza ve toptancılar için kurumsal üyelik.
                  </p>
                </div>

                <BackendPendingNotice
                  title="Online Bayilik Başvuru API'si Henüz Tanımlı Değil"
                  description="Bayilik başvuru kayıt servisi backend'de henüz açılmamıştır. Yeni bayi tanımlaması, vergi levhası doğrulaması ve cari limit açılışı için bayi@taradiamond.com.tr veya +90 (212) 519 40 10 üzerinden toptan ekibimizle iletişime geçiniz."
                  endpointHint="POST /api/v1/b2b/applications"
                />

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    setApplyAttempted(true);
                  }}
                  className="space-y-3 text-caption"
                >
                  <div className="space-y-1">
                    <Label htmlFor="b2b-company">Firma Ünvanı</Label>
                    <Input id="b2b-company" type="text" required placeholder="Örn: Anadolu Kuyumculuk Ltd. Şti." />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="b2b-tax">Vergi Dairesi &amp; No</Label>
                      <Input id="b2b-tax" type="text" required placeholder="VD · 10 haneli VKN" />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="b2b-city">Şehir</Label>
                      <Input id="b2b-city" type="text" required placeholder="İstanbul" />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="b2b-contact">Yetkili Ad Soyad &amp; Telefon</Label>
                    <Input id="b2b-contact" type="text" required placeholder="Ad Soyad · 05XX XXX XX XX" />
                  </div>

                  {applyAttempted && (
                    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-destructive">
                      Başvuru iletilemedi: Backend sunucusunda bayilik başvuru endpoint'i henüz
                      bulunmuyor.
                    </div>
                  )}

                  <Button type="submit" variant="secondary" className="w-full">
                    Başvuruyu Gönder (Backend Bekleniyor)
                  </Button>
                </form>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
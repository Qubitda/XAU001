import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, KeyRound, Lock, Mail, ShieldCheck, UserPlus } from 'lucide-react';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import { resolveHomeForSession } from '@taragold/shared/components/PortalRouteGuard';
import { TaraDiamondLogo, TaraStarMark } from '@taragold/shared/components/brand/TaraDiamondBrand';
import {
  TARA_INPUT_CLASS,
  TARA_PRIMARY_BTN_CLASS,
  TARA_SECONDARY_BTN_CLASS,
} from '@taragold/shared/features/storefront/components/StorefrontUI';
import { apiFetch, ApiClientError } from '@taragold/shared/lib/api/client';

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiClientError) return err.message || fallback;
  if (err instanceof Error) return err.message;
  return fallback;
}

export function B2cLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoggingIn } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const session = await login({ email: email.trim(), password });
      const target = from && !from.startsWith('/giris') ? from : resolveHomeForSession(session);
      navigate(target, { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Giriş yapılamadı. Bilgilerinizi kontrol ediniz.'));
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12 sm:py-16">
      <div className="bg-card border border-border rounded-[6px] p-6 sm:p-9 space-y-6">
        <div className="space-y-3 text-center">
          <div className="flex justify-center">
            <TaraDiamondLogo variant="stacked" tone="dark" size="sm" />
          </div>
          <div className="h-px w-12 bg-primary mx-auto" aria-hidden="true" />
          <div className="space-y-1">
            <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground font-medium">
              Müşteri Hesabı
            </p>
            <h1 className="font-serif text-3xl font-normal text-foreground">Giriş Yap</h1>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Siparişlerinizi takip etmek, favorilerinizi saklamak ve sertifikalarınıza ulaşmak
              için oturum açın.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="b2c-email" className="text-xs font-medium text-foreground block">
              E-posta Adresi
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="b2c-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ornek@eposta.com"
                className={`${TARA_INPUT_CLASS} pl-10`}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <label htmlFor="b2c-password" className="text-xs font-medium text-foreground">
                Şifre
              </label>
              <Link
                to="/sifre-yenile"
                className="text-xs text-muted-foreground hover:text-foreground underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
              >
                Şifremi Unuttum
              </Link>
            </div>
            <div className="relative">
              <Lock className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="b2c-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={`${TARA_INPUT_CLASS} pl-10`}
              />
            </div>
          </div>

          {error && (
            <div className="rounded-[4px] border border-foreground bg-primary px-3.5 py-2.5 text-xs text-foreground leading-relaxed">
              {error}
            </div>
          )}

          <button type="submit" disabled={isLoggingIn} className={`${TARA_PRIMARY_BTN_CLASS} w-full`}>
            <span>{isLoggingIn ? 'Oturum Açılıyor...' : 'Giriş Yap'}</span>
            {!isLoggingIn && <ArrowRight className="w-4 h-4" />}
          </button>
        </form>

        <div className="pt-5 border-t border-border space-y-3 text-center text-xs text-muted-foreground">
          <p>
            Henüz hesabınız yok mu?{' '}
            <Link
              to="/kayit"
              className="font-medium text-foreground hover:text-foreground underline underline-offset-4"
            >
              Yeni Hesap Oluştur
            </Link>
          </p>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-center gap-2 text-[11px] text-muted-foreground text-center">
        <ShieldCheck className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
        <span>Rol ve erişim yetkileri sunucu oturumu üzerinden güvenle doğrulanır.</span>
      </div>
    </div>
  );
}

export function B2cRegisterPage() {
  const navigate = useNavigate();
  const { register, isRegistering } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setInfo(null);
    try {
      const session = await register({
        email: email.trim(),
        password,
        fullName: fullName.trim(),
        phone: phone.trim() || undefined,
      });
      setInfo('Hesabınız oluşturuldu. Doğrulama bağlantısı e-posta adresinize gönderildi.');
      navigate(resolveHomeForSession(session), { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Kayıt tamamlanamadı.'));
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12 sm:py-16">
      <div className="bg-card border border-border rounded-[6px] p-6 sm:p-9 space-y-6">
        <div className="space-y-3 text-center">
          <div className="flex justify-center">
            <TaraStarMark className="w-7 h-7" />
          </div>
          <div className="space-y-1">
            <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground font-medium">
              Yeni Müşteri Üyeliği
            </p>
            <h1 className="font-serif text-3xl font-normal text-foreground">Hesap Oluştur</h1>
            <p className="text-xs text-muted-foreground leading-relaxed">
              TARA DIAMOND koleksiyonlarında kişiye özel sipariş, sertifika ve bakım takibi için
              üyelik oluşturun.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div className="space-y-1.5">
            <label htmlFor="b2c-reg-name" className="text-xs font-medium text-foreground block">
              Ad Soyad
            </label>
            <input
              id="b2c-reg-name"
              type="text"
              required
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Adınız Soyadınız"
              className={TARA_INPUT_CLASS}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="b2c-reg-email" className="text-xs font-medium text-foreground block">
              E-posta Adresi
            </label>
            <input
              id="b2c-reg-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ornek@eposta.com"
              className={TARA_INPUT_CLASS}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="b2c-reg-phone" className="text-xs font-medium text-foreground block">
              Telefon
            </label>
            <input
              id="b2c-reg-phone"
              type="tel"
              autoComplete="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="05XX XXX XX XX"
              className={TARA_INPUT_CLASS}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="b2c-reg-password" className="text-xs font-medium text-foreground block">
              Şifre
            </label>
            <input
              id="b2c-reg-password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="En az 8 karakter"
              className={TARA_INPUT_CLASS}
            />
          </div>

          {error && (
            <div className="rounded-[4px] border border-foreground bg-primary px-3.5 py-2.5 text-xs text-foreground">
              {error}
            </div>
          )}
          {info && (
            <div className="rounded-[4px] border border-ring bg-muted px-3.5 py-2.5 text-xs text-foreground">
              {info}
            </div>
          )}

          <button
            type="submit"
            disabled={isRegistering}
            className={`${TARA_PRIMARY_BTN_CLASS} w-full min-h-[44px]`}
          >
            <UserPlus className="w-4 h-4" />
            <span>{isRegistering ? 'Hesap Oluşturuluyor...' : 'Üyelik Oluştur'}</span>
          </button>
        </form>

        <div className="pt-5 border-t border-border text-center text-xs text-muted-foreground">
          Zaten hesabınız var mı?{' '}
          <Link
            to="/giris"
            className="font-medium text-foreground hover:text-foreground underline underline-offset-4"
          >
            Giriş Yap
          </Link>
        </div>
      </div>
    </div>
  );
}

export function PasswordResetPage() {
  const [email, setEmail] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiFetch<{ accepted: boolean }>('/api/v1/auth/password/forgot', {
        method: 'POST',
        body: { email: email.trim() },
      });
      setDone(true);
    } catch (err) {
      setError(errorMessage(err, 'Sıfırlama isteği gönderilemedi.'));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12 sm:py-16">
      <div className="bg-card border border-border rounded-[6px] p-6 sm:p-9 space-y-6">
        <div className="space-y-3 text-center">
          <div className="w-11 h-11 rounded-full bg-muted border border-border flex items-center justify-center mx-auto">
            <KeyRound className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="space-y-1">
            <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground font-medium">
              Hesap Güvenliği
            </p>
            <h1 className="font-serif text-3xl font-normal text-foreground">Şifre Yenileme</h1>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Hesabınıza kayıtlı e-posta adresine şifre sıfırlama bağlantısı gönderilir.
            </p>
          </div>
        </div>

        {done ? (
          <div className="rounded-[4px] border border-ring bg-muted px-3.5 py-3 text-xs text-foreground leading-relaxed">
            Talep alındı. E-posta kayıtlıysa sıfırlama bağlantısı kısa süre içinde iletilecektir.
            Yerel geliştirmede bağlantı Django konsol logunda görünür.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="reset-email" className="text-xs font-medium text-foreground block">
                Kayıtlı E-posta Adresi
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  id="reset-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ornek@eposta.com"
                  className={`${TARA_INPUT_CLASS} pl-10`}
                />
              </div>
            </div>

            {error && (
              <div className="rounded-[4px] border border-foreground bg-primary px-3.5 py-2.5 text-xs text-foreground">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={pending}
              className={`${TARA_PRIMARY_BTN_CLASS} w-full min-h-[44px]`}
            >
              {pending ? 'Gönderiliyor...' : 'Sıfırlama Bağlantısı Gönder'}
            </button>
          </form>
        )}

        <div className="pt-4 border-t border-border flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <Link
            to="/giris"
            className="inline-flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Müşteri Girişi</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export function PasswordResetConfirmPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const linkValid = useMemo(() => Boolean(uid && token), [uid, token]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiFetch<{ passwordReset: boolean }>('/api/v1/auth/password/reset', {
        method: 'POST',
        body: { uid, token, newPassword: password },
      });
      setDone(true);
      window.setTimeout(() => navigate('/giris', { replace: true }), 1200);
    } catch (err) {
      setError(errorMessage(err, 'Parola sıfırlanamadı.'));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-12 sm:py-16">
      <div className="bg-card border border-border rounded-[6px] p-6 sm:p-9 space-y-6">
        <div className="space-y-1 text-center">
          <h1 className="font-serif text-3xl font-normal text-foreground">Yeni Parola</h1>
          <p className="text-xs text-muted-foreground">E-postadaki bağlantı ile parolanızı belirleyin.</p>
        </div>

        {!linkValid ? (
          <div className="text-xs text-foreground">Bağlantı eksik veya geçersiz.</div>
        ) : done ? (
          <div className="text-xs text-foreground">Parola güncellendi. Giriş sayfasına yönlendiriliyorsunuz…</div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Yeni parola (en az 8 karakter)"
              className={TARA_INPUT_CLASS}
            />
            {error && <div className="text-xs text-foreground">{error}</div>}
            <button type="submit" disabled={pending} className={`${TARA_PRIMARY_BTN_CLASS} w-full`}>
              {pending ? 'Kaydediliyor...' : 'Parolayı Kaydet'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export function EmailVerifyPage() {
  const [params] = useSearchParams();
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';
  const [status, setStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [message, setMessage] = useState('Doğrulama yapılıyor…');

  useEffect(() => {
    if (!uid || !token) {
      setStatus('error');
      setMessage('Doğrulama bağlantısı eksik.');
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        await apiFetch('/api/v1/auth/email/verify', {
          method: 'POST',
          body: { uid, token },
        });
        if (!cancelled) {
          setStatus('ok');
          setMessage('E-posta adresiniz doğrulandı.');
        }
      } catch (err) {
        if (!cancelled) {
          setStatus('error');
          setMessage(errorMessage(err, 'Doğrulama başarısız.'));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [uid, token]);

  return (
    <div className="max-w-md mx-auto px-4 py-12 sm:py-16">
      <div className="bg-card border border-border rounded-[6px] p-6 sm:p-9 space-y-4 text-center">
        <h1 className="font-serif text-3xl font-normal text-foreground">E-posta Doğrulama</h1>
        <p className={`text-xs ${status === 'error' ? 'text-foreground' : 'text-foreground'}`}>{message}</p>
        <Link to="/giris" className={`${TARA_SECONDARY_BTN_CLASS} inline-flex`}>
          Giriş Sayfasına Dön
        </Link>
      </div>
    </div>
  );
}

import { FormEvent, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowRight, Lock, Mail, ShieldCheck } from 'lucide-react';
import { Button, Input, Label } from '@taragold/shared/components/ui';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import { hasOpsAccess, resolveHomeForSession } from '@taragold/shared/components/PortalRouteGuard';
import {
  isB2bPortalEnabled,
  isB2cStorefrontEnabled,
} from '@taragold/shared/config/commercialModules';

const STOREFRONT_URL = import.meta.env.VITE_STOREFRONT_URL || 'http://localhost:3000/';
const B2B_URL = import.meta.env.VITE_B2B_URL || 'http://localhost:3001/b2b/giris';

export function OpsLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, switchMembership, isLoggingIn } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const session = await login({ email: email.trim(), password });
      const opsMembership = session.memberships.find((m) => m.audience === 'erp');

      if (!hasOpsAccess(session) && !opsMembership) {
        setError(
          'Bu hesabın OPS Yönetim Paneli yetkisi bulunmuyor. Yetkili portalınıza yönlendiriliyorsunuz...'
        );
        window.setTimeout(() => {
          navigate(resolveHomeForSession(session), { replace: true });
        }, 1200);
        return;
      }

      if (opsMembership && session.activeMembershipId !== opsMembership.id) {
        await switchMembership(opsMembership.id);
      }

      const target = from && from.startsWith('/ops/') && from !== '/ops/giris' ? from : '/ops/panel';
      navigate(target, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Oturum açılamadı. Kimlik bilgilerinizi kontrol edin.');
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center px-4 py-12 font-sans">
      <div className="max-w-md w-full space-y-6">
        <div className="text-center space-y-1.5">
          <div className="text-2xl font-semibold tracking-tight text-white">TARA GOLD</div>
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 font-medium">
            OPS Operasyon &amp; PIM Yönetim Konsolu
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-7 sm:p-8 space-y-6 shadow-xl">
          <div className="space-y-1">
            <h1 className="text-page-title text-xl">Operasyon Yönetici Girişi</h1>
            <p className="text-caption">
              Katalog, fiyat motoru, canlı kur ve sipariş yönetimi için yetkili hesabınızla giriş yapın.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="ops-email">Yönetici E-posta</Label>
              <div className="relative">
                <Mail className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                <Input
                  id="ops-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operasyon@taragold.com.tr"
                  className="pl-9"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ops-password">Parola</Label>
              <div className="relative">
                <Lock className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                <Input
                  id="ops-password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-9"
                />
              </div>
            </div>

            {error && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-caption text-destructive">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full h-10" disabled={isLoggingIn}>
              {isLoggingIn ? 'Yetkiler Doğrulanıyor...' : 'OPS Paneline Giriş Yap'}
              {!isLoggingIn && <ArrowRight className="w-4 h-4" />}
            </Button>
          </form>

          <div className="pt-4 border-t border-border flex items-center justify-between text-caption gap-3">
            {isB2cStorefrontEnabled() ? (
              <a href={STOREFRONT_URL} className="hover:text-foreground">
                ← B2C Vitrin
              </a>
            ) : (
              <span className="text-muted-foreground">B2C vitrin bu kurulumda yok</span>
            )}
            {isB2bPortalEnabled() ? (
              <a href={B2B_URL} className="hover:text-foreground hover:underline ml-auto">
                B2B Bayi Girişi
              </a>
            ) : null}
          </div>
        </div>

        <div className="flex items-center justify-center gap-2 text-[11px] text-zinc-500">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Tüm OPS işlemleri sunucu tarafında denetim kaydına alınır.</span>
        </div>
      </div>
    </div>
  );
}
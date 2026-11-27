import { ReactNode, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { Lock, ShieldAlert } from 'lucide-react';
import { useAuth } from '../providers/AuthProvider';
import type { SessionUserDto } from '../lib/api/openapi';
import { Button } from './ui';
import { getStorefrontUrl } from '../lib/portalUrls';

const OPS_CAPABILITIES = [
  'catalog:write',
  'orders:manage',
  'pricing:edit',
  'rates:edit',
  'users:read',
  'orgs:manage',
  'inventory:manage',
  'production:manage',
  'finance:manage',
  'notifications:manage',
  'audit:read',
] as const;

export function hasOpsAccess(user: SessionUserDto): boolean {
  if (!user.authenticated) return false;
  return OPS_CAPABILITIES.some((cap) => user.capabilities.includes(cap));
}

export function hasB2bAccess(user: SessionUserDto): boolean {
  if (!user.authenticated) return false;
  const hasB2bCap = user.capabilities.includes('b2b:order');
  const hasB2bMembership = user.memberships.some((m) => m.audience === 'b2b');
  return hasB2bCap || hasB2bMembership;
}

export function resolveHomeForSession(user: SessionUserDto): string {
  if (!user.authenticated) return '/';
  if (hasOpsAccess(user)) return '/ops/panel';
  if (hasB2bAccess(user)) return '/b2b/panel';
  return '/hesabim';
}

interface PortalRouteGuardProps {
  portal: 'b2c-auth' | 'b2b' | 'ops';
  children: ReactNode;
}

export function PortalRouteGuard({ portal, children }: PortalRouteGuardProps) {
  const { user, authenticated, isLoading, memberships, switchMembership } = useAuth();
  const location = useLocation();
  const switchMembershipRef = useRef(switchMembership);
  switchMembershipRef.current = switchMembership;

  const [contextSwitchError, setContextSwitchError] = useState<string | null>(null);
  const [pendingSwitchId, setPendingSwitchId] = useState<string | null>(null);

  const opsMembership = memberships.find((m) => m.audience === 'erp');
  const b2bMembership = memberships.find((m) => m.audience === 'b2b');
  const needsOpsSwitch =
    portal === 'ops' && authenticated && !hasOpsAccess(user) && Boolean(opsMembership);
  const needsB2bSwitch =
    portal === 'b2b' &&
    authenticated &&
    hasB2bAccess(user) &&
    !user.capabilities.includes('b2b:order') &&
    Boolean(b2bMembership);
  const autoSwitchTargetId = needsOpsSwitch
    ? (opsMembership?.id ?? null)
    : needsB2bSwitch
      ? (b2bMembership?.id ?? null)
      : null;

  useEffect(() => {
    if (!autoSwitchTargetId) return;

    let cancelled = false;
    setPendingSwitchId(autoSwitchTargetId);
    setContextSwitchError(null);

    void switchMembershipRef
      .current(autoSwitchTargetId)
      .then(() => {
        if (!cancelled) setPendingSwitchId(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setPendingSwitchId(null);
        setContextSwitchError(
          err instanceof Error ? err.message : 'Bağlam geçişi başarısız oldu.'
        );
      });

    return () => {
      cancelled = true;
    };
  }, [autoSwitchTargetId]);

  if (isLoading || pendingSwitchId !== null) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-2.5">
          <div className="w-6 h-6 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-zinc-500">
            {pendingSwitchId
              ? portal === 'ops'
                ? 'OPS bağlamına geçiliyor...'
                : 'Bayi bağlamına geçiliyor...'
              : 'Oturum ve yetkiler doğrulanıyor...'}
          </p>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    const loginPath =
      portal === 'ops' ? '/ops/giris' : portal === 'b2b' ? '/b2b/giris' : '/giris';
    return <Navigate to={loginPath} replace state={{ from: location.pathname + location.search }} />;
  }

  if (portal === 'ops' && !hasOpsAccess(user)) {
    if (opsMembership) {
      return (
        <div className="min-h-[65vh] flex items-center justify-center px-4">
          <div className="max-w-md w-full bg-white border border-zinc-200 rounded-lg p-6 space-y-4">
            <div className="flex items-start gap-3">
              <Lock className="w-5 h-5 text-zinc-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h1 className="text-base font-semibold text-foreground">
                  Operasyon Üyeliğine Geçiş Gerekli
                </h1>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Aktif oturumunuz şu an farklı bir firma/rol bağlamında. Yetkili olduğunuz{' '}
                  <strong>{opsMembership.organizationName}</strong> operasyon bağlamına geçerek
                  devam edebilirsiniz.
                </p>
                {contextSwitchError && (
                  <p className="text-xs text-red-700 pt-1">{contextSwitchError}</p>
                )}
              </div>
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link to={resolveHomeForSession(user)}>Yetkili Panele Dön</Link>
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setPendingSwitchId(opsMembership.id);
                  setContextSwitchError(null);
                  void switchMembership(opsMembership.id)
                    .then(() => setPendingSwitchId(null))
                    .catch((err: unknown) => {
                      setPendingSwitchId(null);
                      setContextSwitchError(
                        err instanceof Error ? err.message : 'Bağlam geçişi başarısız oldu.'
                      );
                    });
                }}
              >
                OPS Bağlamına Geç
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-[65vh] flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white border border-zinc-200 rounded-lg p-6 space-y-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-red-700 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h1 className="text-base font-semibold text-foreground">
                OPS Yönetim Yetkisi Bulunmuyor
              </h1>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Bu alan yalnızca yetkili operasyon ve katalog yöneticilerine açıktır. Hesabınızın
                sunucu taraflı OPS yetkisi tanımlı değil.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button size="sm" asChild>
              <Link to={resolveHomeForSession(user)}>Yetkili Portalıma Git</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (portal === 'b2b' && !hasB2bAccess(user)) {
    return (
      <div className="min-h-[65vh] flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white border border-zinc-200 rounded-lg p-6 space-y-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-warning shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h1 className="text-base font-semibold text-foreground">
                B2B Bayi Yetkisi Bulunmuyor
              </h1>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Aktif hesabınız bir B2B bayi organizasyonuna bağlı değil. Toptan sipariş portalı
                için onaylı bayi hesabı gereklidir.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" asChild>
              <a href={getStorefrontUrl()}>Vitrine Dön</a>
            </Button>
            <Button size="sm" asChild>
              <Link to={resolveHomeForSession(user)}>Yetkili Portalıma Git</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (portal === 'b2b' && !user.capabilities.includes('b2b:order') && b2bMembership) {
    return (
      <div className="min-h-[65vh] flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white border border-zinc-200 rounded-lg p-6 space-y-4">
          <div className="flex items-start gap-3">
            <Lock className="w-5 h-5 text-zinc-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h1 className="text-base font-semibold text-foreground">
                Bayi Organizasyonuna Geçiş Gerekli
              </h1>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Toptan fiyat ve sipariş fişine erişmek için yetkili olduğunuz{' '}
                <strong>{b2bMembership.organizationName}</strong> bayi hesabını aktif edin.
              </p>
              {contextSwitchError && (
                <p className="text-xs text-red-700 pt-1">{contextSwitchError}</p>
              )}
            </div>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button
              size="sm"
              onClick={() => {
                setPendingSwitchId(b2bMembership.id);
                setContextSwitchError(null);
                void switchMembership(b2bMembership.id)
                  .then(() => setPendingSwitchId(null))
                  .catch((err: unknown) => {
                    setPendingSwitchId(null);
                    setContextSwitchError(
                      err instanceof Error ? err.message : 'Bağlam geçişi başarısız oldu.'
                    );
                  });
              }}
            >
              Bayi Hesabına Geç
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

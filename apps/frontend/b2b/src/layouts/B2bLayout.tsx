import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Building2,
  ClipboardList,
  Gem,
  Heart,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Scale,
  Settings,
  Sparkles,
  Users,
  Mail,
} from 'lucide-react';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import { useActiveProductMetrics } from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import { useB2bDraftQuery, useCommerceUI } from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { B2bOrderModal } from '@taragold/shared/features/commerce/components/B2bOrderModal';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';
import {
  Badge,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Button,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  ThemeToggle,
} from '@taragold/shared/components/ui';

import { isB2cStorefrontEnabled } from '@taragold/shared/config/commercialModules';

const STOREFRONT_URL = import.meta.env.VITE_STOREFRONT_URL || 'http://localhost:3000/';

const B2B_NAV = [
  { to: '/b2b/panel', label: 'Bayi Paneli', icon: LayoutDashboard },
  { to: '/b2b/katalog', label: 'Toptan Katalog', icon: Gem },
  { to: '/b2b/tasarla', label: 'Kendin Tasarla', icon: Sparkles },
  { to: '/b2b/siparis-fisi', label: 'Sipariş Fişi', icon: ClipboardList },
  { to: '/b2b/siparisler', label: 'Sipariş Geçmişi', icon: History },
  { to: '/b2b/cari-hesap', label: 'Cari Hesap & Limitler', icon: Scale },
  { to: '/b2b/favoriler', label: 'Favoriler', icon: Heart },
  { to: '/b2b/kullanicilar', label: 'Firma Kullanıcıları', icon: Users },
  { to: '/b2b/ayarlar', label: 'Firma Ayarları', icon: Settings },
  { to: '/b2b/mail-loglari', label: 'Mail Logları', icon: Mail },
];

const BREADCRUMB_TITLES: Record<string, string> = {
  '/b2b/panel': 'Bayi Paneli',
  '/b2b/katalog': 'Toptan Katalog',
  '/b2b/tasarla': 'Kendin Tasarla',
  '/b2b/siparis-fisi': 'Sipariş Fişi',
  '/b2b/siparisler': 'Sipariş Geçmişi',
  '/b2b/cari-hesap': 'Cari Hesap & Limitler',
  '/b2b/favoriler': 'Favoriler',
  '/b2b/kullanicilar': 'Firma Kullanıcıları',
  '/b2b/ayarlar': 'Firma Ayarları',
  '/b2b/mail-loglari': 'Mail Logları',
};

function NavLinks({ draftPieces, onNavigate }: { draftPieces: number; onNavigate?: () => void }) {
  return (
    <>
      {B2B_NAV.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center justify-between px-3 py-2 rounded-md text-caption font-medium transition-colors ${
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
              }`
            }
          >
            <span className="flex items-center gap-2.5">
              <Icon className="w-4 h-4 shrink-0" />
              {item.label}
            </span>
            {item.to === '/b2b/siparis-fisi' && draftPieces > 0 && (
              <Badge variant="secondary" className="font-sku tabular-nums">
                {draftPieces}
              </Badge>
            )}
          </NavLink>
        );
      })}
    </>
  );
}

export function B2bLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const {
    user,
    memberships,
    activeMembership,
    activeOrganization,
    activeBranch,
    switchMembership,
    switchBranch,
    logout,
  } = useAuth();
  const { rates } = useActiveProductMetrics();
  const b2bDraftQuery = useB2bDraftQuery();
  const { setB2bOrderOpen } = useCommerceUI();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const b2bMemberships = memberships.filter((m) => m.audience === 'b2b');
  const draftPieces = (b2bDraftQuery.data?.lines ?? []).reduce((s, l) => s + l.qty, 0);

  const currentPageTitle =
    location.pathname.startsWith('/b2b/urun/')
      ? 'Ürün Detayı & Asorti'
      : location.pathname.startsWith('/b2b/tasarla')
        ? 'Kendin Tasarla'
        : BREADCRUMB_TITLES[location.pathname] ?? 'Bayi Portalı';

  const handleLogout = async () => {
    await logout();
    navigate('/b2b/giris');
  };

  const orgContext = (
    <div className="p-4 border-b border-sidebar-border bg-sidebar-accent/50 space-y-2.5">
      <div className="flex items-start gap-2">
        <Building2 className="w-4 h-4 text-sidebar-foreground/50 shrink-0 mt-0.5" />
        <div className="min-w-0">
          <div className="text-label truncate text-sidebar-foreground">
            {activeOrganization?.name ?? 'Bayi Hesabı'}
          </div>
          <div className="font-sku text-caption text-sidebar-foreground/55">
            {activeOrganization?.code ?? '—'} · {activeBranch?.name ?? 'Şube Tanımsız'}
          </div>
        </div>
      </div>

      {b2bMemberships.length > 1 && (
        <select
          aria-label="Yetkili bayi firması seçimi"
          value={activeMembership?.id ?? ''}
          onChange={(e) => switchMembership(e.target.value)}
          className="w-full h-8 px-2 text-caption rounded-md border border-sidebar-border bg-sidebar text-sidebar-foreground"
        >
          {b2bMemberships.map((m) => (
            <option key={m.id} value={m.id}>
              {m.organizationName}
            </option>
          ))}
        </select>
      )}

      {activeOrganization && activeOrganization.branches.length > 1 && (
        <select
          aria-label="Yetkili şube seçimi"
          value={activeBranch?.id ?? ''}
          onChange={(e) => switchBranch(e.target.value)}
          className="w-full h-8 px-2 text-caption rounded-md border border-sidebar-border bg-sidebar text-sidebar-foreground"
        >
          {activeOrganization.branches.map((branch) => (
            <option key={branch.id} value={branch.id}>
              Şube: {branch.name}
            </option>
          ))}
        </select>
      )}
    </div>
  );

  const sidebarFooter = (
    <div className="p-4 border-t border-sidebar-border space-y-3 bg-sidebar">
      <div className="rounded-md bg-sidebar-accent border border-sidebar-border p-2.5 text-caption space-y-1 text-sidebar-foreground">
        <div className="text-label text-sidebar-foreground/55">Canlı Referans Kur</div>
        <div className="flex items-center justify-between font-sku tabular-nums">
          <span>Has 995</span>
          <span className="font-medium">{formatTrNumber(rates.liveHasGoldTrySell, 2)} TL</span>
        </div>
        <div className="flex items-center justify-between font-sku tabular-nums">
          <span>USD / EUR</span>
          <span>
            {formatTrNumber(rates.liveUsdSell, 2)} / {formatTrNumber(rates.liveEurSell, 2)}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between gap-2 text-caption text-sidebar-foreground">
        <div className="min-w-0">
          <div className="text-label truncate">{user.fullName}</div>
          <div className="text-caption truncate text-sidebar-foreground/55">{user.email}</div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => void handleLogout()}
          aria-label="Oturumu kapat"
          className="text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent"
        >
          <LogOut className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-background text-foreground font-sans">
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:fixed lg:inset-y-0 bg-sidebar text-sidebar-foreground border-r border-sidebar-border z-30">
        <div className="h-16 px-5 border-b border-sidebar-border flex items-center">
          <Link to="/b2b/panel" className="leading-none">
            <div className="text-label text-lg tracking-tight text-sidebar-foreground">TARA GOLD</div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-sidebar-foreground/50 mt-0.5">
              B2B Bayi Portalı
            </div>
          </Link>
        </div>
        {orgContext}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <NavLinks draftPieces={draftPieces} />
        </nav>
        {sidebarFooter}
      </aside>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent
          side="left"
          className="w-72 p-0 flex flex-col bg-sidebar text-sidebar-foreground border-sidebar-border lg:hidden"
          hideClose
        >
          <SheetHeader className="h-16 px-4 border-b border-sidebar-border justify-center">
            <SheetTitle className="text-left text-label text-sidebar-foreground">
              TARA GOLD · B2B
            </SheetTitle>
          </SheetHeader>
          {orgContext}
          <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
            <NavLinks draftPieces={draftPieces} onNavigate={() => setMobileNavOpen(false)} />
          </nav>
          <div className="p-4 border-t border-sidebar-border">
            <Button
              type="button"
              variant="outline"
              className="w-full border-sidebar-border text-sidebar-foreground hover:bg-sidebar-accent"
              onClick={() => {
                setMobileNavOpen(false);
                void handleLogout();
              }}
            >
              <LogOut className="w-3.5 h-3.5" />
              Çıkış Yap
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <div className="flex-1 lg:pl-64 flex flex-col min-w-0">
        <header className="sticky top-0 z-20 h-16 bg-card/95 backdrop-blur border-b border-border px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => setMobileNavOpen(true)}
              aria-label="Menü aç"
              className="lg:hidden min-h-11 min-w-11"
            >
              <Menu className="w-5 h-5" />
            </Button>
            <Breadcrumb className="min-w-0">
              <BreadcrumbList>
                <BreadcrumbItem className="hidden sm:inline">
                  <span className="text-caption">Bayi Portalı</span>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden sm:inline" />
                <BreadcrumbItem>
                  <BreadcrumbPage className="truncate text-page-title text-base sm:text-lg font-semibold">
                    {currentPageTitle}
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <ThemeToggle compact />
            {isB2cStorefrontEnabled() ? (
              <a
                href={STOREFRONT_URL}
                className="hidden sm:inline-flex text-caption hover:text-foreground transition-colors"
              >
                B2C Vitrin
              </a>
            ) : null}
            <Button type="button" size="sm" onClick={() => setB2bOrderOpen(true)}>
              <ClipboardList className="w-3.5 h-3.5" />
              <span>Sipariş Fişi</span>
              <span className="font-sku tabular-nums">({draftPieces})</span>
            </Button>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1440px] w-full mx-auto min-w-0 overflow-x-hidden">
          <Outlet />
        </main>
      </div>

      <B2bOrderModal />
    </div>
  );
}
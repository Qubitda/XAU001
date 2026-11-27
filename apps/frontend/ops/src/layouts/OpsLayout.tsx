import { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Boxes,
  Building2,
  Calculator,
  ChevronDown,
  ClipboardCheck,
  Diamond,
  FileSpreadsheet,
  Hammer,
  Layers,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Scale,
  KeyRound,
  BookMarked,
  ShieldCheck,
  UserRound,
  Webhook,
  Settings2,
  CreditCard,
  Mail,
  PhoneCall,
  ScrollText,
  ShoppingCart,
  Shield,
} from 'lucide-react';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import { useActiveProductMetrics } from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';
import { B2bOrderModal } from '@taragold/shared/features/commerce/components/B2bOrderModal';
import {
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

const OPS_NAV_GROUPS = [
  {
    group: 'Genel',
    items: [{ to: '/ops/panel', label: 'Operasyon Özeti', icon: LayoutDashboard }],
  },
  {
    group: 'Katalog & Mühendislik',
    items: [
      { to: '/ops/urunler', label: 'Ürün Yönetimi', icon: Package },
      { to: '/ops/varyantlar', label: 'Varyantlar', icon: Layers },
      { to: '/ops/tas-montur', label: 'Taş & Montür', icon: Diamond },
    ],
  },
  {
    group: 'Fiyatlandırma',
    items: [
      { to: '/ops/fiyat-motoru', label: 'Fiyat Motoru & Kur', icon: Calculator },
      { to: '/ops/receteler', label: 'Maliyet Reçeteleri', icon: FileSpreadsheet },
    ],
  },
  {
    group: 'Operasyon & Tedarik',
    items: [
      { to: '/ops/siparisler', label: 'Sipariş Yönetimi', icon: ClipboardCheck },
      { to: '/ops/satis-gorevleri', label: 'Satış Takip Görevleri', icon: PhoneCall },
      { to: '/ops/odeme-islemleri', label: 'Ödeme İşlemleri', icon: CreditCard },
      { to: '/ops/stok-depo', label: 'Stok & Depo', icon: Boxes },
      { to: '/ops/uretim', label: 'Üretim / Atölye', icon: Hammer },
    ],
  },
  {
    group: 'Müşteri Yönetimi',
    items: [
      { to: '/ops/musteriler', label: 'Müşteri Listesi', icon: UserRound },
      { to: '/ops/sepet-takibi', label: 'Sepet Takibi', icon: ShoppingCart },
      { to: '/ops/izinler', label: 'İzin ve Onay Yönetimi', icon: Shield },
      { to: '/ops/musteri-islem-gecmisi', label: 'Müşteri İşlem Geçmişi', icon: ScrollText },
    ],
  },
  {
    group: 'Kurumsal & Yetki',
    items: [
      { to: '/ops/firmalar', label: 'İş Ortakları', icon: Building2 },
      { to: '/ops/cari-hesap', label: 'Cari Hesap & Finans', icon: Scale },
      { to: '/ops/kullanicilar', label: 'Kullanıcı & Yetki', icon: ShieldCheck },
      { to: '/ops/api-anahtarlari', label: 'API Anahtarları', icon: KeyRound },
      { to: '/ops/webhookler', label: 'Webhooklar', icon: Webhook },
    ],
  },
  {
    group: 'Kurumsal & Yasal',
    items: [
      { to: '/ops/yasal-metinler', label: 'Kvkk ve Sözleşmeler', icon: BookMarked },
      { to: '/ops/eposta-sablonlari', label: 'E-posta Şablonları', icon: Mail },
      { to: '/ops/sirket-iletisim', label: 'Şirket İletişim', icon: Building2 },
    ],
  },
  {
    group: 'Ayarlar',
    items: [
      { to: '/ops/ayarlar', label: 'Sistem Ayarları', icon: Settings2 },
      { to: '/ops/mail-loglari', label: 'Mail Logları', icon: Mail },
      { to: '/ops/tanimlar', label: 'Tanım Yönetimi', icon: BookMarked },
    ],
  },
];

const OPS_TITLES: Record<string, string> = {
  '/ops/panel': 'Operasyon Özeti',
  '/ops/urunler': 'Ürün Yönetimi (PIM)',
  '/ops/varyantlar': 'Varyant Yönetimi',
  '/ops/tas-montur': 'Taş & Montür Teknik Yapısı',
  '/ops/fiyat-motoru': 'Fiyat Motoru & Canlı Kur',
  '/ops/receteler': 'Maliyet Reçeteleri',
  '/ops/siparisler': 'Sipariş Yönetimi',
  '/ops/satis-gorevleri': 'Satış Takip Görevleri',
  '/ops/odeme-islemleri': 'Ödeme İşlemleri',
  '/ops/stok-depo': 'Stok & Depo Durumu',
  '/ops/uretim': 'Üretim / Atölye Kuyruğu',
  '/ops/firmalar': 'İş Ortakları',
  '/ops/musteriler': 'Müşteri Listesi',
  '/ops/sepet-takibi': 'Sepet Takibi',
  '/ops/izinler': 'İzin ve Onay Yönetimi',
  '/ops/musteri-islem-gecmisi': 'Müşteri İşlem Geçmişi',
  '/ops/yasal-metinler': 'Kvkk ve Sözleşmeler',
  '/ops/eposta-sablonlari': 'E-posta Şablonları',
  '/ops/sirket-iletisim': 'Şirket İletişim',
  '/ops/cari-hesap': 'Cari Hesap & Finans',
  '/ops/kullanicilar': 'Kullanıcı & Yetki Yönetimi',
  '/ops/api-anahtarlari': 'API Anahtarları',
  '/ops/webhookler': 'Webhooklar',
  '/ops/ayarlar': 'Sistem Ayarları',
  '/ops/mail-loglari': 'Mail Logları',
  '/ops/tanimlar': 'Tanım Yönetimi',
};

function groupForPath(pathname: string): string | null {
  for (const section of OPS_NAV_GROUPS) {
    if (section.items.some((item) => item.to === pathname)) return section.group;
  }
  return null;
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const activeGroup = useMemo(() => groupForPath(location.pathname), [location.pathname]);

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const section of OPS_NAV_GROUPS) {
      initial[section.group] = section.group === 'Genel' || section.group === activeGroup;
    }
    return initial;
  });

  useEffect(() => {
    if (!activeGroup) return;
    setOpenGroups((prev) => (prev[activeGroup] ? prev : { ...prev, [activeGroup]: true }));
  }, [activeGroup]);

  const toggleGroup = (group: string) => {
    setOpenGroups((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  return (
    <nav className="flex-1 px-3 py-3 overflow-y-auto">
      {OPS_NAV_GROUPS.map((section, index) => {
        const isOpen = openGroups[section.group] ?? false;
        return (
          <div key={section.group} className={index === 0 ? '' : 'mt-5'}>
            <button
              type="button"
              onClick={() => toggleGroup(section.group)}
              aria-expanded={isOpen}
              className="flex w-full items-center justify-between gap-2 px-3 py-1 text-left cursor-pointer"
            >
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {section.group}
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 shrink-0 text-muted-foreground transition-transform ${
                  isOpen ? 'rotate-0' : '-rotate-90'
                }`}
              />
            </button>

            {isOpen ? (
              <div className="mt-1.5 space-y-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        `relative flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium leading-none transition-colors ${
                          isActive
                            ? 'bg-sidebar-accent text-sidebar-accent-foreground before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-0.5 before:rounded-full before:bg-primary'
                            : 'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                        }`
                      }
                    >
                      <Icon className="w-4 h-4 shrink-0 text-muted-foreground" />
                      <span className="truncate">{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}

export function OpsLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, activeOrganization, logout } = useAuth();
  const { rates } = useActiveProductMetrics();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const pageTitle = OPS_TITLES[location.pathname] ?? 'OPS Yönetim Paneli';

  const handleLogout = async () => {
    await logout();
    navigate('/ops/giris');
  };

  const sidebarFooter = (
    <div className="shrink-0 border-t border-sidebar-border bg-muted px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-label text-sidebar-foreground truncate">{user.fullName}</div>
          <div className="font-sku text-[11px] text-muted-foreground truncate">
            {user.roleKey} · {activeOrganization?.code ?? 'HQ'}
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => void handleLogout()}
          aria-label="Çıkış Yap"
          className="text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent"
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
          <Link to="/ops/panel" className="leading-none">
            <div className="text-label text-lg tracking-tight text-sidebar-foreground">TARA GOLD</div>
            <div className="text-[10px] uppercase tracking-wider text-sidebar-foreground/45 mt-0.5">
              OPS Yönetim Konsolu
            </div>
          </Link>
        </div>
        <SidebarNav />
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
              TARA GOLD · OPS
            </SheetTitle>
          </SheetHeader>
          <SidebarNav onNavigate={() => setMobileNavOpen(false)} />
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
        <header className="sticky top-0 z-20 h-16 bg-card border-b border-border px-4 sm:px-6 flex items-center justify-between gap-4">
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
                  <span className="text-caption">OPS</span>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden sm:inline" />
                <BreadcrumbItem>
                  <BreadcrumbPage className="truncate font-semibold text-foreground">{pageTitle}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>

          <div className="flex items-center gap-3 shrink-0 text-caption">
            <ThemeToggle compact className="border border-border bg-background hover:bg-muted" />
            <Link
              to="/ops/fiyat-motoru"
              className="hidden md:flex items-center gap-3 px-3 py-1.5 rounded-md border border-border bg-muted font-sku tabular-nums whitespace-nowrap shrink-0 hover:border-ring transition-colors"
            >
              <span>
                HAS <strong className="text-foreground">{formatTrNumber(rates.liveHasGoldTrySell, 2)}</strong> TL
              </span>
              <span className="text-border">|</span>
              <span>
                USD <strong className="text-foreground">{formatTrNumber(rates.liveUsdSell, 2)}</strong>
              </span>
              <span className="text-border">|</span>
              <span>
                EUR <strong className="text-foreground">{formatTrNumber(rates.liveEurSell, 2)}</strong>
              </span>
            </Link>
            {isB2cStorefrontEnabled() ? (
              <a
                href={STOREFRONT_URL}
                className="whitespace-nowrap shrink-0 hover:text-foreground font-medium transition-colors"
              >
                Vitrini Gör
              </a>
            ) : null}
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1520px] w-full mx-auto min-w-0 overflow-x-hidden">
          <Outlet />
        </main>
      </div>

      <B2bOrderModal />
    </div>
  );
}
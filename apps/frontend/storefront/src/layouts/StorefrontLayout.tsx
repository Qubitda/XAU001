import { FormEvent, useEffect, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowUp,
  Building2,
  Check,
  ChevronDown,
  Heart,
  Instagram,
  LogOut,
  Mail,
  MapPin,
  Menu,
  Package,
  Phone,
  Settings,
  ShoppingBag,
  User,
  X,
  Youtube,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@taragold/shared/components/ui';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@taragold/shared/components/ui/dropdown-menu';
import { TaraDiamondLogo, TaraStarMark } from '@taragold/shared/components/brand/TaraDiamondBrand';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import {
  useB2cCartQuery,
  useCommerceUI,
  useFavoritesQuery,
} from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { B2cCartModal } from '@taragold/shared/features/commerce/components/B2cCartModal';
import { StorefrontNotificationBell } from '@taragold/shared/features/storefront/components/StorefrontNotificationBell';
import { hasB2bAccess, hasOpsAccess } from '@taragold/shared/components/PortalRouteGuard';
import { isB2bPortalEnabled } from '@taragold/shared/config/commercialModules';
import {
  getB2bPanelUrl,
  getOpsLoginUrl,
  getOpsPanelUrl,
} from '@taragold/shared/lib/portalUrls';
import { apiFetch } from '@taragold/shared/lib/api/client';

interface PrimaryNavItem {
  to: string;
  label: string;
  filterValue: string | null;
}

const PRIMARY_NAV_LINKS: PrimaryNavItem[] = [
  { to: '/koleksiyon', label: 'Koleksiyon', filterValue: null },
  { to: '/tasarla', label: 'Kendin Tasarla', filterValue: null },
  { to: '/koleksiyon?filter=new_collection', label: 'Yeni Gelenler', filterValue: 'new_collection' },
  { to: '/koleksiyon?filter=discounted', label: 'Kampanyalar', filterValue: 'discounted' },
];

type LegalTopic =
  | 'privacy'
  | 'terms'
  | 'kvkk'
  | 'returns'
  | 'cookie'
  | 'distance'
  | 'preinfo'
  | 'membership'
  | null;

const LEGAL_CODE_MAP: Record<Exclude<LegalTopic, null>, string | null> = {
  privacy: 'PRIVACY',
  terms: 'MEMBERSHIP',
  kvkk: 'KVKK',
  returns: null,
  cookie: 'COOKIE',
  distance: 'DISTANCE_SALES',
  preinfo: 'PRE_INFO',
  membership: 'MEMBERSHIP',
};

const LEGAL_FALLBACK: Record<Exclude<LegalTopic, null>, { title: string; body: string }> = {
  privacy: {
    title: 'Gizlilik İlkeleri',
    body: 'TARA DIAMOND, müşteri kişisel verilerini ve sipariş bilgilerini yalnızca güvenli teslimat, sertifika kaydı ve yasal yükümlülükler kapsamında işler. Ödeme işlemleri 256-bit SSL ve 3D Secure altyapısı üzerinden şifrelenerek gerçekleştirilir.',
  },
  terms: {
    title: 'Kullanım Şartları',
    body: 'Sitede yer alan tüm pırlanta ve altın mücevher fiyatları canlı maden kurları esas alınarak hesaplanır. Sepette 15 dakikalık fiyat sabitleme süresi uygulanır ve tüm siparişler Brinks / Loomis sigortalı değerli kurye ile alıcı imzasına teslim edilir.',
  },
  kvkk: {
    title: 'KVKK Aydınlatma',
    body: '6698 sayılı Kişisel Verilerin Korunması Kanunu uyarınca kimlik, iletişim ve teslimat bilgileriniz yalnızca sipariş sözleşmesinin ifası, sigortalı kurye poliçesi oluşturulması ve satış sonrası bakım hizmetlerinin sunulması amacıyla saklanır.',
  },
  returns: {
    title: 'İade, Değişim ve Bakım Koşulları',
    body: 'Standart stok ürünlerinde 14 gün içinde kullanılmamış ve orijinal sertifikasıyla birlikte iade/değişim yapılabilir. Mesafeli Satışlar Yönetmeliği m.15/b uyarınca lazer gravürlü veya kişiye özel ölçüde üretilen mücevherlerde cayma hakkı uygulanmaz. Tüm TARA DIAMOND mücevherleri ömür boyu ücretsiz bakım ve temizlik kapsamındadır.',
  },
  cookie: {
    title: 'Çerez Politikası',
    body: 'Çerezler; oturum, sepet ve analitik amaçlı kullanılır. Zorunlu çerezler site işleyişi için gereklidir; tercih çerezleri onayınıza bağlıdır.',
  },
  distance: {
    title: 'Mesafeli Satış Sözleşmesi',
    body: 'Mesafeli satış sözleşmesi, sipariş onayı anında kabul edilir. Güncel metin OPS yasal şablonlarından yayınlanır.',
  },
  preinfo: {
    title: 'Ön Bilgilendirme',
    body: 'Ön bilgilendirme formu, ödeme adımında sunulan ürün, teslimat ve cayma bilgilerini içerir.',
  },
  membership: {
    title: 'Üyelik Sözleşmesi',
    body: 'Üyelik hesabı oluşturarak platform kullanım koşullarını kabul etmiş sayılırsınız.',
  },
};

export function StorefrontLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, authenticated, logout } = useAuth();
  const { setB2cCartOpen } = useCommerceUI();
  const b2cCartQuery = useB2cCartQuery();
  const favoritesQuery = useFavoritesQuery();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [newsletterEmail, setNewsletterEmail] = useState('');
  const [newsletterStatus, setNewsletterStatus] = useState<'idle' | 'subscribed' | 'error'>('idle');
  const [legalModal, setLegalModal] = useState<LegalTopic>(null);
  const [legalContent, setLegalContent] = useState<{ title: string; body: string } | null>(null);
  const [legalLoading, setLegalLoading] = useState(false);
  const [siteContact, setSiteContact] = useState({
    tagline: 'Zamansız mücevher zarafetiyle, her anınızda yanınızdayız.',
    addressLine: 'Nuruosmaniye Cad. No:54 Fatih / İstanbul',
    phone: '+90 (212) 519 40 00',
    email: 'destek@taradiamond.com.tr',
    workingHours: 'Pzt – Cmt · 09:30 – 19:00',
    instagramUrl: 'https://instagram.com',
    youtubeUrl: 'https://youtube.com',
    tiktokUrl: '',
    pinterestUrl: '',
    mapUrl: '',
  });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await apiFetch<{
          tagline?: string;
          addressLine?: string;
          phone?: string;
          email?: string;
          workingHours?: string;
          instagramUrl?: string;
          youtubeUrl?: string;
          tiktokUrl?: string;
          pinterestUrl?: string;
          mapUrl?: string;
        }>('/api/v1/storefront/site-contact');
        if (cancelled || !res.data) return;
        setSiteContact((prev) => ({
          tagline: res.data.tagline || prev.tagline,
          addressLine: res.data.addressLine || prev.addressLine,
          phone: res.data.phone || prev.phone,
          email: res.data.email || prev.email,
          workingHours: res.data.workingHours || prev.workingHours,
          instagramUrl: res.data.instagramUrl || prev.instagramUrl,
          youtubeUrl: res.data.youtubeUrl || prev.youtubeUrl,
          tiktokUrl: res.data.tiktokUrl || prev.tiktokUrl,
          pinterestUrl: res.data.pinterestUrl || prev.pinterestUrl,
          mapUrl: res.data.mapUrl || prev.mapUrl,
        }));
      } catch {
        // keep footer defaults
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!legalModal) {
      setLegalContent(null);
      return;
    }
    const fallback = LEGAL_FALLBACK[legalModal];
    const code = LEGAL_CODE_MAP[legalModal];
    if (!code) {
      setLegalContent(fallback);
      return;
    }
    let cancelled = false;
    setLegalLoading(true);
    void (async () => {
      try {
        const res = await apiFetch<{
          title: string;
          bodyHtml?: string;
          bodyMd?: string;
        }>(`/api/v1/storefront/legal-documents/${code}`);
        if (cancelled) return;
        const html = (res.data.bodyHtml || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
        setLegalContent({
          title: res.data.title || fallback.title,
          body: html || res.data.bodyMd || fallback.body,
        });
      } catch {
        if (!cancelled) setLegalContent(fallback);
      } finally {
        if (!cancelled) setLegalLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [legalModal]);

  const cartCount = (b2cCartQuery.data?.items ?? []).reduce((sum, item) => sum + item.qty, 0);
  const favCount = (favoritesQuery.data ?? []).length;

  const activeFilter = new URLSearchParams(location.search).get('filter');
  const isFavoritesActive = location.pathname === '/favoriler';
  // Only OPS-assigned B2B dealers see portal links (module + membership)
  const showB2bPortal =
    isB2bPortalEnabled() && authenticated && hasB2bAccess(user);
  const b2bPortalHref = getB2bPanelUrl();
  const opsPortalHref =
    authenticated && hasOpsAccess(user) ? getOpsPanelUrl() : getOpsLoginUrl();
  const showOpsLink = authenticated && hasOpsAccess(user);
  const firstName = user.fullName ? user.fullName.trim().split(/\s+/)[0] : 'Hesabım';

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mobileMenuOpen]);

  const isNavItemActive = (item: PrimaryNavItem): boolean => {
    if (item.to.startsWith('/tasarla')) {
      return location.pathname === '/tasarla' || location.pathname.startsWith('/tasarla/');
    }
    if (location.pathname !== '/koleksiyon') return false;
    if (item.filterValue === null) {
      return !activeFilter || (activeFilter !== 'new_collection' && activeFilter !== 'discounted');
    }
    return activeFilter === item.filterValue;
  };

  const handleLogout = async () => {
    setMobileMenuOpen(false);
    await logout();
    navigate('/');
  };

  const handleNewsletterSubmit = (e: FormEvent) => {
    e.preventDefault();
    const cleaned = newsletterEmail.trim();
    if (!cleaned || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleaned)) {
      setNewsletterStatus('error');
      return;
    }
    setNewsletterStatus('subscribed');
    setNewsletterEmail('');
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* 1. Top Utility Information Bar */}
      <div className="bg-background border-b border-border/90 text-[11px] text-muted-foreground">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-9 flex items-center justify-between gap-3">
          <div className="inline-flex items-center gap-1.5 min-w-0 truncate">
            <TaraStarMark className="w-3 h-3 shrink-0" />
            <span className="truncate">Ücretsiz Sigortalı Kargo · Güvenli Alışveriş</span>
          </div>

          <div className="hidden md:flex items-center gap-3 shrink-0">
            {showB2bPortal ? (
              <>
                <a
                  href={b2bPortalHref}
                  className="hover:text-foreground text-muted-foreground font-medium transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                >
                  Bayi Portalı
                </a>
                <span className="h-3 w-px bg-border" aria-hidden="true" />
              </>
            ) : null}
            <a
              href="#musteri-hizmetleri"
              className="hover:text-foreground transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
            >
              Müşteri Hizmetleri
            </a>
          </div>
        </div>
      </div>

      {/* 2. Main Sticky Storefront Header */}
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 md:h-[74px]">
          {/* Mobile Bar (< 768px): Hamburger Left | Centered Logo | Minimal Bag & Favorites Right */}
          <div className="md:hidden h-full grid grid-cols-[1fr_auto_1fr] items-center gap-2">
            <div className="justify-self-start flex items-center">
              <button
                type="button"
                onClick={() => setMobileMenuOpen((v) => !v)}
                aria-label={mobileMenuOpen ? 'Menüyü kapat' : 'Menüyü aç'}
                aria-expanded={mobileMenuOpen}
                aria-controls="storefront-mobile-menu"
                className="inline-flex items-center justify-center w-10 h-10 -ml-1.5 rounded-md text-foreground hover:bg-border/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>

            <Link
              to="/"
              aria-label="TARA DIAMOND Ana Sayfa"
              className="justify-self-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
            >
              <TaraDiamondLogo size="sm" />
            </Link>

            <div className="justify-self-end flex items-center gap-1">
              {authenticated ? <StorefrontNotificationBell /> : null}
              <Link
                to="/favoriler"
                aria-label={favCount > 0 ? `Favoriler (${favCount} ürün)` : 'Favoriler'}
                className={`hidden min-[375px]:inline-flex relative items-center justify-center w-10 h-10 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  isFavoritesActive
                    ? 'text-foreground'
                    : 'text-foreground hover:bg-border/45'
                }`}
              >
                <Heart
                  className={`w-[19px] h-[19px] stroke-[1.6] ${
                    isFavoritesActive ? 'fill-foreground/15' : ''
                  }`}
                />
                {favCount > 0 && (
                  <span className="absolute top-1 right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-primary text-white font-mono text-[10px] font-semibold leading-4 text-center tabular-nums">
                    {favCount}
                  </span>
                )}
              </Link>

              <button
                type="button"
                onClick={() => setB2cCartOpen(true)}
                aria-label={`Sepet (${cartCount} ürün)`}
                className="relative inline-flex items-center justify-center w-10 h-10 rounded-full text-foreground hover:bg-border/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
              >
                <ShoppingBag className="w-5 h-5 stroke-[1.6]" />
                {cartCount > 0 && (
                  <span className="absolute top-1 right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-primary text-white font-mono text-[10px] font-semibold leading-[18px] text-center tabular-nums">
                    {cartCount}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Tablet & Desktop Bar (≥ 768px): Brand Left | Primary Nav Center | Minimal Actions Right */}
          <div className="hidden md:grid h-full grid-cols-[1fr_auto_1fr] items-center gap-4">
            {/* Zone 1: TARA DIAMOND Brand Mark */}
            <div className="justify-self-start">
              <Link
                to="/"
                aria-label="TARA DIAMOND Ana Sayfa"
                className="inline-flex items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
              >
                <TaraDiamondLogo size="md" />
              </Link>
            </div>

            {/* Zone 2: Centered Primary Navigation */}
            <nav
              aria-label="Ana navigasyon"
              className="justify-self-center flex items-center gap-6 lg:gap-9 xl:gap-11"
            >
              {PRIMARY_NAV_LINKS.map((item) => {
                const active = isNavItemActive(item);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    aria-current={active ? 'page' : undefined}
                    className={`relative py-2 text-[13px] lg:text-[14px] font-medium tracking-[0.015em] whitespace-nowrap shrink-0 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm ${
                      active
                        ? 'text-foreground after:absolute after:inset-x-0 after:bottom-0 after:h-[1.5px] after:bg-primary'
                        : 'text-muted-foreground hover:text-foreground after:absolute after:inset-x-0 after:bottom-0 after:h-[1.5px] after:bg-transparent hover:after:bg-primary/50 after:transition-colors'
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {/* Zone 3: Minimal Favorites, Account Dropdown & Gold-Count Shopping Bag */}
            <div className="justify-self-end flex items-center gap-1.5 lg:gap-2.5">
              {authenticated ? <StorefrontNotificationBell /> : null}
              {/* Favorites */}
              <Link
                to="/favoriler"
                aria-label={favCount > 0 ? `Favoriler (${favCount} ürün)` : 'Favoriler'}
                aria-current={isFavoritesActive ? 'page' : undefined}
                className={`relative inline-flex items-center justify-center w-10 h-10 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  isFavoritesActive
                    ? 'text-foreground bg-border/45'
                    : 'text-foreground hover:bg-border/45'
                }`}
              >
                <Heart
                  className={`w-[20px] h-[20px] stroke-[1.55] ${
                    isFavoritesActive ? 'fill-foreground/15' : ''
                  }`}
                />
                {favCount > 0 && (
                  <span className="absolute top-1 right-0.5 min-w-[17px] h-[17px] px-1 rounded-full bg-primary text-white font-mono text-[10px] font-semibold leading-[17px] text-center tabular-nums">
                    {favCount}
                  </span>
                )}
              </Link>

              {/* User Account Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    aria-label={
                      authenticated ? `Hesap menüsü: ${user.fullName}` : 'Hesap ve giriş menüsü'
                    }
                    className="inline-flex items-center gap-1.5 h-10 px-2.5 rounded-full text-xs font-medium text-foreground hover:bg-border/45 data-[state=open]:bg-border/55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors whitespace-nowrap shrink-0 cursor-pointer"
                  >
                    <User className="w-[20px] h-[20px] stroke-[1.55] shrink-0" />
                    {authenticated && (
                      <span className="hidden lg:inline max-w-[96px] truncate text-[12px] text-foreground">
                        {firstName}
                      </span>
                    )}
                    <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0 hidden lg:inline" />
                  </button>
                </DropdownMenuTrigger>

                <DropdownMenuContent
                  align="end"
                  sideOffset={8}
                  className="w-56 bg-card border-border shadow-md"
                >
                  {authenticated ? (
                    <>
                      <DropdownMenuLabel className="py-2">
                        <div className="text-xs font-semibold text-foreground truncate">
                          {user.fullName}
                        </div>
                        {user.email && (
                          <div className="text-[11px] font-normal text-muted-foreground truncate mt-0.5">
                            {user.email}
                          </div>
                        )}
                      </DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onSelect={() => navigate('/hesabim')}>
                        <User className="w-3.5 h-3.5 text-muted-foreground" />
                        <span>Hesabım</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => navigate('/hesabim/siparisler')}>
                        <Package className="w-3.5 h-3.5 text-muted-foreground" />
                        <span>Siparişlerim</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => navigate('/hesabim/adresler')}>
                        <MapPin className="w-3.5 h-3.5 text-muted-foreground" />
                        <span>Adreslerim</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => navigate('/favoriler')}>
                        <Heart className="w-3.5 h-3.5 text-muted-foreground" />
                        <span>Favorilerim{favCount > 0 ? ` (${favCount})` : ''}</span>
                      </DropdownMenuItem>
                      {(showB2bPortal || showOpsLink) && (
                        <>
                          <DropdownMenuSeparator />
                          <DropdownMenuLabel className="text-[10px] font-medium tracking-wider uppercase text-muted-foreground">
                            Kurumsal Erişim
                          </DropdownMenuLabel>
                          {showB2bPortal && (
                            <DropdownMenuItem
                              onSelect={() => {
                                window.location.href = b2bPortalHref;
                              }}
                            >
                              <Building2 className="w-3.5 h-3.5 text-muted-foreground" />
                              <span>Bayi Portalı</span>
                            </DropdownMenuItem>
                          )}
                          {showOpsLink && (
                            <DropdownMenuItem
                              onSelect={() => {
                                window.location.href = opsPortalHref;
                              }}
                            >
                              <Settings className="w-3.5 h-3.5 text-muted-foreground" />
                              <span>OPS Yönetim Paneli</span>
                            </DropdownMenuItem>
                          )}
                        </>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem destructive onSelect={() => void handleLogout()}>
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Çıkış Yap</span>
                      </DropdownMenuItem>
                    </>
                  ) : (
                    <>
                      <DropdownMenuLabel className="text-[11px] text-muted-foreground font-medium">
                        Müşteri Hesabı
                      </DropdownMenuLabel>
                      <DropdownMenuItem onSelect={() => navigate('/giris')}>
                        <User className="w-3.5 h-3.5 text-muted-foreground" />
                        <span>Müşteri Girişi</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => navigate('/kayit')}>
                        <Package className="w-3.5 h-3.5 text-muted-foreground" />
                        <span>Hesap Oluştur</span>
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Minimal Shopping Bag Icon + Champagne Gold Counter (No Heavy Filled Button) */}
              <button
                type="button"
                onClick={() => setB2cCartOpen(true)}
                aria-label={`Sepeti aç (${cartCount} ürün)`}
                className="relative inline-flex items-center justify-center w-10 h-10 rounded-full text-foreground hover:bg-border/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
              >
                <ShoppingBag className="w-[20px] h-[20px] stroke-[1.55]" />
                <span className="absolute top-1 right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-primary text-white font-mono text-[10px] font-semibold leading-[18px] text-center tabular-nums">
                  {cartCount}
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <nav
            id="storefront-mobile-menu"
            aria-label="Mobil navigasyon"
            className="md:hidden bg-card border-t border-border max-h-[calc(100dvh-6.25rem)] overflow-y-auto overscroll-contain"
          >
            <div className="px-4 py-4 space-y-5">
              <div className="space-y-0.5">
                {PRIMARY_NAV_LINKS.map((item) => {
                  const active = isNavItemActive(item);
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      aria-current={active ? 'page' : undefined}
                      className={`flex items-center justify-between py-2.5 px-2.5 rounded-md text-sm transition-colors ${
                        active
                          ? 'text-foreground font-semibold bg-muted/70'
                          : 'text-foreground font-medium hover:bg-muted/45'
                      }`}
                    >
                      <span>{item.label}</span>
                    </Link>
                  );
                })}

                <Link
                  to="/favoriler"
                  aria-current={isFavoritesActive ? 'page' : undefined}
                  className={`flex items-center justify-between py-2.5 px-2.5 rounded-md text-sm transition-colors ${
                    isFavoritesActive
                      ? 'text-foreground font-semibold bg-muted/70'
                      : 'text-foreground font-medium hover:bg-muted/45'
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <Heart className="w-4 h-4 text-muted-foreground" />
                    <span>Favoriler</span>
                  </span>
                  {favCount > 0 && (
                    <span className="font-mono text-xs font-semibold tabular-nums text-muted-foreground">
                      {favCount}
                    </span>
                  )}
                </Link>
              </div>

              <div className="pt-4 border-t border-border space-y-1">
                {authenticated ? (
                  <>
                    <div className="px-2.5 pb-2">
                      <div className="text-xs font-semibold text-foreground">{user.fullName}</div>
                      {user.email && (
                        <div className="text-[11px] text-muted-foreground truncate">{user.email}</div>
                      )}
                    </div>
                    <Link
                      to="/hesabim"
                      className="flex items-center gap-2.5 py-2.5 px-2.5 rounded-md text-sm text-foreground hover:bg-muted/45"
                    >
                      <User className="w-4 h-4 text-muted-foreground" />
                      <span>Hesabım</span>
                    </Link>
                    <Link
                      to="/hesabim/siparisler"
                      className="flex items-center gap-2.5 py-2.5 px-2.5 rounded-md text-sm text-foreground hover:bg-muted/45"
                    >
                      <Package className="w-4 h-4 text-muted-foreground" />
                      <span>Siparişlerim</span>
                    </Link>
                    <Link
                      to="/hesabim/adresler"
                      className="flex items-center gap-2.5 py-2.5 px-2.5 rounded-md text-sm text-foreground hover:bg-muted/45"
                    >
                      <MapPin className="w-4 h-4 text-muted-foreground" />
                      <span>Adreslerim</span>
                    </Link>
                    <button
                      type="button"
                      onClick={() => void handleLogout()}
                      className="w-full flex items-center gap-2.5 py-2.5 px-2.5 rounded-md text-sm text-foreground hover:bg-primary/5 text-left cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Çıkış Yap</span>
                    </button>
                  </>
                ) : (
                  <div className="grid grid-cols-2 gap-2 px-1">
                    <Link
                      to="/giris"
                      className="flex items-center justify-center min-h-[42px] rounded-[4px] bg-primary text-primary-foreground text-xs font-medium hover:bg-primary transition-colors"
                    >
                      Giriş Yap
                    </Link>
                    <Link
                      to="/kayit"
                      className="flex items-center justify-center min-h-[42px] rounded-[4px] border border-border text-foreground text-xs font-medium hover:border-ring transition-colors"
                    >
                      Kayıt Ol
                    </Link>
                  </div>
                )}
              </div>

              {(showB2bPortal || showOpsLink) && (
                <div className="pt-4 border-t border-border space-y-1">
                  <div className="px-2.5 pb-1 text-[11px] font-medium text-muted-foreground">
                    Kurumsal Erişim
                  </div>
                  {showB2bPortal && (
                    <a
                      href={b2bPortalHref}
                      className="flex items-center gap-2.5 py-2.5 px-2.5 rounded-md text-sm font-medium text-muted-foreground hover:bg-muted/45"
                    >
                      <Building2 className="w-4 h-4 text-muted-foreground" />
                      <span>Bayi Portalı</span>
                    </a>
                  )}
                  {showOpsLink && (
                    <a
                      href={opsPortalHref}
                      className="flex items-center gap-2.5 py-2.5 px-2.5 rounded-md text-sm font-medium text-muted-foreground hover:bg-muted/45"
                    >
                      <Settings className="w-4 h-4 text-muted-foreground" />
                      <span>OPS Yönetim Paneli</span>
                    </a>
                  )}
                </div>
              )}
            </div>
          </nav>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 min-w-0">
        <Outlet />
      </main>

      {/* 8. Corporate Pearl White Footer (Faithful to TARA DIAMOND Reference) */}
      <footer id="musteri-hizmetleri" className="bg-background text-foreground border-t border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-14">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-8 lg:gap-8">
            {/* Brand Story */}
            <div className="lg:col-span-3 space-y-3.5">
              <Link to="/" aria-label="TARA DIAMOND Ana Sayfa" className="inline-block">
                <TaraDiamondLogo size="md" />
              </Link>
              <p className="text-xs text-muted-foreground leading-relaxed max-w-xs">
                {siteContact.tagline}
              </p>
              <div className="space-y-1.5 pt-1 text-xs text-muted-foreground">
                <div className="flex items-start gap-2">
                  <MapPin className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />
                  {siteContact.mapUrl ? (
                    <a
                      href={siteContact.mapUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-foreground transition-colors"
                    >
                      {siteContact.addressLine}
                    </a>
                  ) : (
                    <span>{siteContact.addressLine}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Phone className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                  <a
                    href={`tel:${siteContact.phone.replace(/[^\d+]/g, '')}`}
                    className="font-mono tabular-nums hover:text-foreground transition-colors"
                  >
                    {siteContact.phone}
                  </a>
                </div>
              </div>
            </div>

            {/* Koleksiyonlar */}
            <div className="lg:col-span-2 space-y-3 text-xs">
              <h3 className="text-[13px] font-semibold text-foreground">Koleksiyonlar</h3>
              <ul className="space-y-2 text-muted-foreground">
                <li>
                  <Link
                    to="/koleksiyon?category=Y%C3%BCz%C3%BCk"
                    className="hover:text-foreground transition-colors"
                  >
                    Yüzük
                  </Link>
                </li>
                <li>
                  <Link
                    to="/koleksiyon?category=Kolye"
                    className="hover:text-foreground transition-colors"
                  >
                    Kolye
                  </Link>
                </li>
                <li>
                  <Link
                    to="/koleksiyon?category=K%C3%BCpe"
                    className="hover:text-foreground transition-colors"
                  >
                    Küpe
                  </Link>
                </li>
                <li>
                  <Link
                    to="/koleksiyon?category=Bileklik"
                    className="hover:text-foreground transition-colors"
                  >
                    Bileklik
                  </Link>
                </li>
              </ul>
            </div>

            {/* Müşteri Hizmetleri */}
            <div className="lg:col-span-2 space-y-3 text-xs">
              <h3 className="text-[13px] font-semibold text-foreground">Müşteri Hizmetleri</h3>
              <ul className="space-y-2 text-muted-foreground">
                <li>
                  <Link to="/hesabim/siparisler" className="hover:text-foreground transition-colors">
                    Sipariş Takibi
                  </Link>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => setLegalModal('returns')}
                    className="hover:text-foreground transition-colors text-left cursor-pointer"
                  >
                    İade ve Değişim
                  </button>
                </li>
                <li>
                  <Link to="/hesabim" className="hover:text-foreground transition-colors">
                    Hesabım
                  </Link>
                </li>
                {showB2bPortal && (
                  <li>
                    <a
                      href={b2bPortalHref}
                      className="hover:text-foreground text-muted-foreground transition-colors"
                    >
                      Bayi Portalı
                    </a>
                  </li>
                )}
                {showOpsLink && (
                  <li>
                    <a href={opsPortalHref} className="hover:text-foreground transition-colors">
                      OPS Girişi
                    </a>
                  </li>
                )}
              </ul>
            </div>

            {/* Bizi Takip Edin */}
            <div className="lg:col-span-2 space-y-3 text-xs">
              <h3 className="text-[13px] font-semibold text-foreground">Bizi Takip Edin</h3>
              <div className="flex items-center gap-2.5 text-foreground">
                {siteContact.instagramUrl ? (
                  <a
                    href={siteContact.instagramUrl}
                    target="_blank"
                    rel="noreferrer"
                    aria-label="TARA DIAMOND Instagram"
                    className="inline-flex items-center justify-center w-9 h-9 rounded-full border border-border hover:border-ring hover:text-foreground transition-colors"
                  >
                    <Instagram className="w-4 h-4" />
                  </a>
                ) : null}
                {siteContact.youtubeUrl ? (
                  <a
                    href={siteContact.youtubeUrl}
                    target="_blank"
                    rel="noreferrer"
                    aria-label="TARA DIAMOND YouTube"
                    className="inline-flex items-center justify-center w-9 h-9 rounded-full border border-border hover:border-ring hover:text-foreground transition-colors"
                  >
                    <Youtube className="w-4 h-4" />
                  </a>
                ) : null}
                {siteContact.tiktokUrl ? (
                  <a
                    href={siteContact.tiktokUrl}
                    target="_blank"
                    rel="noreferrer"
                    aria-label="TARA DIAMOND TikTok"
                    className="inline-flex items-center justify-center w-9 h-9 rounded-full border border-border hover:border-ring hover:text-foreground transition-colors"
                  >
                    <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current" aria-hidden>
                      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 0 0-.79-.05A6.34 6.34 0 0 0 3.15 15.3a6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.34-6.34V8.73a8.2 8.2 0 0 0 4.76 1.52V6.8a4.85 4.85 0 0 1-1-.11z" />
                    </svg>
                  </a>
                ) : null}
                {siteContact.pinterestUrl ? (
                  <a
                    href={siteContact.pinterestUrl}
                    target="_blank"
                    rel="noreferrer"
                    aria-label="TARA DIAMOND Pinterest"
                    className="inline-flex items-center justify-center w-9 h-9 rounded-full border border-border hover:border-ring hover:text-foreground transition-colors"
                  >
                    <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current" aria-hidden>
                      <path d="M12 2C6.48 2 2 6.48 2 12c0 4.24 2.64 7.87 6.38 9.35-.09-.79-.17-2.01.03-2.87.18-.78 1.17-4.97 1.17-4.97s-.3-.6-.3-1.48c0-1.39.81-2.43 1.81-2.43.85 0 1.26.64 1.26 1.41 0 .86-.55 2.14-.83 3.33-.24.99.5 1.8 1.48 1.8 1.77 0 3.13-1.87 3.13-4.56 0-2.38-1.71-4.05-4.16-4.05-2.83 0-4.49 2.12-4.49 4.31 0 .85.33 1.77.74 2.27.08.1.09.18.07.28l-.27 1.12c-.04.18-.14.22-.33.13-1.25-.58-2.03-2.4-2.03-3.87 0-3.15 2.29-6.05 6.6-6.05 3.46 0 6.16 2.47 6.16 5.77 0 3.44-2.17 6.21-5.18 6.21-1.01 0-1.96-.53-2.29-1.15l-.62 2.37c-.23.86-.84 1.94-1.25 2.6A10 10 0 0 0 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2z" />
                    </svg>
                  </a>
                ) : null}
                {siteContact.email ? (
                  <a
                    href={`mailto:${siteContact.email}`}
                    aria-label="TARA DIAMOND E-posta"
                    className="inline-flex items-center justify-center w-9 h-9 rounded-full border border-border hover:border-ring hover:text-foreground transition-colors"
                  >
                    <Mail className="w-4 h-4" />
                  </a>
                ) : null}
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {siteContact.email}
                {siteContact.workingHours ? (
                  <>
                    <br />
                    {siteContact.workingHours}
                  </>
                ) : null}
              </p>
            </div>

            {/* Newsletter */}
            <div className="sm:col-span-2 lg:col-span-3 space-y-3 text-xs">
              <h3 className="text-[13px] font-semibold text-foreground">Bültenimize Abone Olun</h3>
              <p className="text-muted-foreground leading-relaxed">
                En yeni koleksiyonlardan ve özel davetlerden haberdar olun.
              </p>
              <form
                onSubmit={handleNewsletterSubmit}
                noValidate
                className="flex flex-col min-[380px]:flex-row gap-2"
              >
                <label htmlFor="tara-newsletter-email" className="sr-only">
                  E-posta adresiniz
                </label>
                <input
                  id="tara-newsletter-email"
                  type="email"
                  inputMode="email"
                  value={newsletterEmail}
                  onChange={(e) => {
                    setNewsletterEmail(e.target.value);
                    if (newsletterStatus !== 'idle') setNewsletterStatus('idle');
                  }}
                  placeholder="E-posta adresiniz"
                  className="flex-1 min-w-0 h-10 px-3 rounded-[4px] border border-border bg-white text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring"
                />
                <button
                  type="submit"
                  className="h-10 px-4 rounded-[4px] bg-primary text-primary-foreground text-xs font-medium hover:bg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors whitespace-nowrap shrink-0 cursor-pointer"
                >
                  Abone Ol
                </button>
              </form>
              {newsletterStatus === 'subscribed' && (
                <p className="inline-flex items-center gap-1.5 text-[11px] text-success font-medium">
                  <Check className="w-3.5 h-3.5" />
                  Bülten kaydınız alındı.
                </p>
              )}
              {newsletterStatus === 'error' && (
                <p className="text-[11px] text-foreground font-medium">
                  Lütfen geçerli bir e-posta adresi girin.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Copyright & Legal Bar */}
        <div className="border-t border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-muted-foreground">
            <span>© {new Date().getFullYear()} TARA DIAMOND. Tüm hakları saklıdır.</span>

            <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5">
              {(
                [
                  ['kvkk', 'KVKK Aydınlatma'],
                  ['privacy', 'Gizlilik İlkeleri'],
                  ['cookie', 'Çerez Politikası'],
                  ['distance', 'Mesafeli Satış Sözleşmesi'],
                  ['preinfo', 'Ön Bilgilendirme'],
                  ['membership', 'Üyelik Sözleşmesi'],
                ] as const
              ).map(([key, label], idx) => (
                <span key={key} className="inline-flex items-center gap-3">
                  {idx > 0 && (
                    <span className="text-border" aria-hidden="true">
                      |
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setLegalModal(key)}
                    className="hover:text-foreground transition-colors cursor-pointer"
                  >
                    {label}
                  </button>
                </span>
              ))}
              <button
                type="button"
                onClick={scrollToTop}
                aria-label="Sayfa başına dön"
                className="ml-1 inline-flex items-center justify-center w-8 h-8 rounded-full border border-border bg-card text-foreground hover:border-ring hover:text-foreground transition-colors cursor-pointer"
              >
                <ArrowUp className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </footer>

      {/* Legal Information Modal */}
      <Dialog open={legalModal !== null} onOpenChange={(open) => !open && setLegalModal(null)}>
        <DialogContent showGlow={false} className="max-w-lg">
          {legalModal && (
            <>
              <DialogHeader>
                <DialogTitle className="font-serif text-xl text-foreground">
                  {legalContent?.title || LEGAL_FALLBACK[legalModal].title}
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground">
                  TARA DIAMOND Mücevherat Bilgilendirme
                </DialogDescription>
              </DialogHeader>
              <p className="text-sm text-muted-foreground leading-relaxed mt-3">
                {legalLoading
                  ? 'Yükleniyor…'
                  : legalContent?.body || LEGAL_FALLBACK[legalModal].body}
              </p>
            </>
          )}
        </DialogContent>
      </Dialog>

      <B2cCartModal />
    </div>
  );
}

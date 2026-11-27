import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Heart,
  LogOut,
  MapPin,
  Package,
  ShoppingBag,
  Truck,
  User,
} from 'lucide-react';
import { useAuth } from '@taragold/shared/providers/AuthProvider';
import {
  useB2cCartQuery,
  useB2cOrdersQuery,
  useCommerceUI,
  useFavoritesQuery,
} from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';
import { hasB2bAccess, hasOpsAccess } from '@taragold/shared/components/PortalRouteGuard';
import { isB2bPortalEnabled } from '@taragold/shared/config/commercialModules';
import { getB2bPanelUrl, getOpsPanelUrl } from '@taragold/shared/lib/portalUrls';
import type { B2cOrderRecord } from '@taragold/shared/features/commerce/types';
import {
  StorefrontEmptyState,
  StorefrontPageHeader,
  TARA_PRIMARY_BTN_CLASS,
  TARA_SECONDARY_BTN_CLASS,
} from '@taragold/shared/features/storefront/components/StorefrontUI';
import { apiFetch } from '@taragold/shared/lib/api/client';

const B2C_STATUS_LABELS: Record<B2cOrderRecord['status'], string> = {
  ODEME_BEKLIYOR: 'Ödeme Bekleniyor',
  ONAYLANDI: 'Sipariş Onaylandı',
  ATOLYE_URETIMDE: 'Atölye & Sertifika Kontrol',
  SIGORTALI_KARGODA: 'Sigortalı Değerli Kargoda',
  IPTAL_EDILDI: 'İptal Edildi',
  IADE_EDILDI: 'İade Edildi',
};

function getOrderStatusColor(status: B2cOrderRecord['status']): string {
  if (status === 'IPTAL_EDILDI' || status === 'IADE_EDILDI') return 'text-foreground';
  if (status === 'ODEME_BEKLIYOR') return 'text-muted-foreground';
  if (status === 'ATOLYE_URETIMDE') return 'text-muted-foreground';
  return 'text-success';
}

function B2cAccountShell({
  activeTab,
  title,
  subtitle,
  breadcrumbLabel,
  children,
}: {
  activeTab: 'overview' | 'orders' | 'addresses';
  title: string;
  subtitle: string;
  breadcrumbLabel?: string;
  children: React.ReactNode;
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = [
    { id: 'overview', to: '/hesabim', label: 'Hesap Özeti', icon: User },
    { id: 'orders', to: '/hesabim/siparisler', label: 'Siparişlerim', icon: Package },
    { id: 'addresses', to: '/hesabim/adresler', label: 'Adreslerim', icon: MapPin },
    { id: 'favorites', to: '/favoriler', label: 'Favorilerim', icon: Heart },
  ] as const;

  const breadcrumb =
    activeTab === 'overview'
      ? [{ label: 'Ana Sayfa', to: '/' }, { label: 'Hesabım' }]
      : [
          { label: 'Ana Sayfa', to: '/' },
          { label: 'Hesabım', to: '/hesabim' },
          { label: breadcrumbLabel ?? title },
        ];

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-12 py-8 sm:py-10 space-y-8">
      <StorefrontPageHeader
        eyebrow="Müşteri Hesabı"
        title={title}
        subtitle={subtitle}
        breadcrumb={breadcrumb}
        actions={
          <>
            {isB2bPortalEnabled() && hasB2bAccess(user) && (
              <a href={getB2bPanelUrl()} className={TARA_SECONDARY_BTN_CLASS}>
                B2B Bayi Portalı
              </a>
            )}
            {hasOpsAccess(user) && (
              <a href={getOpsPanelUrl()} className={TARA_SECONDARY_BTN_CLASS}>
                OPS Paneli
              </a>
            )}
            <button
              type="button"
              onClick={async () => {
                await logout();
                navigate('/');
              }}
              className={TARA_SECONDARY_BTN_CLASS}
            >
              <LogOut className="w-3.5 h-3.5 text-muted-foreground" />
              <span>Çıkış Yap</span>
            </button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
        {/* Responsive Account Navigation (Horizontal scrollable tabs on mobile, vertical rail on desktop) */}
        <aside className="lg:col-span-3">
          <nav
            aria-label="Hesap menüsü"
            className="bg-card border border-border rounded-[6px] p-2 flex lg:flex-col gap-1 overflow-x-auto no-scrollbar"
          >
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = item.id === activeTab;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-[4px] text-xs font-medium transition-colors whitespace-nowrap shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    active
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 shrink-0 ${active ? 'text-muted-foreground' : 'text-muted-foreground'}`}
                  />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        <div className="lg:col-span-9 space-y-6 min-w-0">{children}</div>
      </div>
    </div>
  );
}

function B2cProfileCard({ user }: { user: { fullName: string; email: string; roleKey: string } }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [profile, setProfile] = useState({
    fullName: user.fullName,
    phone: '',
    city: '',
    address: '',
    identityOrTaxNo: '',
  });

  useEffect(() => {
    let active = true;
    apiFetch<{
      fullName?: string;
      phone?: string;
      city?: string;
      address?: string;
      identityOrTaxNo?: string;
    }>('/api/v1/storefront/profile')
      .then((res) => {
        if (!active || !res.data) return;
        setProfile({
          fullName: res.data.fullName || user.fullName,
          phone: res.data.phone || '',
          city: res.data.city || '',
          address: res.data.address || '',
          identityOrTaxNo: res.data.identityOrTaxNo || '',
        });
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [user.fullName]);

  async function saveProfile() {
    setSaving(true);
    setMsg(null);
    try {
      await apiFetch('/api/v1/storefront/profile', {
        method: 'PATCH',
        body: profile,
      });
      setEditing(false);
      setMsg('Profil bilgileri güncellendi.');
    } catch {
      setMsg('Profil güncellenemedi.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-card border border-border rounded-[6px] p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <h2 className="font-serif text-xl font-normal text-foreground">Hesap Bilgileri</h2>
        <button
          type="button"
          onClick={() => setEditing((v) => !v)}
          className="text-xs font-medium text-muted-foreground hover:text-foreground underline underline-offset-4 cursor-pointer"
        >
          {editing ? 'Vazgeç' : 'Düzenle'}
        </button>
      </div>
      {msg && <p className="text-xs text-muted-foreground">{msg}</p>}
      {editing ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <input
            className="border border-border rounded-md px-3 py-2 bg-background"
            placeholder="Ad Soyad"
            value={profile.fullName}
            onChange={(e) => setProfile((p) => ({ ...p, fullName: e.target.value }))}
          />
          <input
            className="border border-border rounded-md px-3 py-2 bg-background"
            placeholder="Telefon"
            value={profile.phone}
            onChange={(e) => setProfile((p) => ({ ...p, phone: e.target.value }))}
          />
          <input
            className="border border-border rounded-md px-3 py-2 bg-background"
            placeholder="Şehir"
            value={profile.city}
            onChange={(e) => setProfile((p) => ({ ...p, city: e.target.value }))}
          />
          <input
            className="border border-border rounded-md px-3 py-2 bg-background"
            placeholder="TCKN / VKN (opsiyonel)"
            value={profile.identityOrTaxNo}
            onChange={(e) => setProfile((p) => ({ ...p, identityOrTaxNo: e.target.value }))}
          />
          <input
            className="border border-border rounded-md px-3 py-2 bg-background sm:col-span-2"
            placeholder="Adres"
            value={profile.address}
            onChange={(e) => setProfile((p) => ({ ...p, address: e.target.value }))}
          />
          <div className="sm:col-span-2 flex justify-end">
            <button
              type="button"
              disabled={saving}
              onClick={() => void saveProfile()}
              className={TARA_PRIMARY_BTN_CLASS}
            >
              {saving ? 'Kaydediliyor…' : 'Kaydet'}
            </button>
          </div>
        </div>
      ) : (
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-5 text-xs">
          <div>
            <dt className="text-muted-foreground">Ad Soyad</dt>
            <dd className="font-medium text-foreground mt-1">{profile.fullName}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">E-posta</dt>
            <dd className="font-medium text-foreground mt-1 break-all">{user.email}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Telefon</dt>
            <dd className="font-medium text-foreground mt-1">{profile.phone || '—'}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Şehir</dt>
            <dd className="font-medium text-foreground mt-1">{profile.city || '—'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">Hesap Tipi</dt>
            <dd className="font-mono text-foreground mt-1">{user.roleKey}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

export function B2cAccountOverviewPage() {
  const { user } = useAuth();
  const ordersQuery = useB2cOrdersQuery();
  const favoritesQuery = useFavoritesQuery();
  const cartQuery = useB2cCartQuery();
  const { setB2cCartOpen } = useCommerceUI();

  const orders = ordersQuery.data ?? [];
  const favCount = (favoritesQuery.data ?? []).length;
  const cartQty = (cartQuery.data?.items ?? []).reduce((s, i) => s + i.qty, 0);

  return (
    <B2cAccountShell
      activeTab="overview"
      title={`Hoş Geldiniz, ${user.fullName}`}
      subtitle="Sipariş geçmişinizi, favori seçkinizi ve teslimat bilgilerinizi buradan yönetebilirsiniz."
    >
      {/* Account Metrics Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-[6px] p-5 space-y-1.5">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Toplam Sipariş
          </div>
          <div className="font-mono text-2xl font-semibold text-foreground tabular-nums">
            {orders.length}
          </div>
          <Link
            to="/hesabim/siparisler"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground pt-1 transition-colors"
          >
            <span>Siparişleri Gör</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="bg-card border border-border rounded-[6px] p-5 space-y-1.5">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Favori Tasarımlar
          </div>
          <div className="font-mono text-2xl font-semibold text-foreground tabular-nums">
            {favCount}
          </div>
          <Link
            to="/favoriler"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground pt-1 transition-colors"
          >
            <span>Favorilere Git</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="bg-card border border-border rounded-[6px] p-5 space-y-1.5">
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Sepetteki Ürün
          </div>
          <div className="font-mono text-2xl font-semibold text-foreground tabular-nums">
            {cartQty}
          </div>
          <button
            type="button"
            onClick={() => setB2cCartOpen(true)}
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground pt-1 transition-colors cursor-pointer"
          >
            <span>Sepeti Aç</span>
            <ShoppingBag className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <B2cProfileCard user={user} />

      {/* Recent Orders */}
      {orders.length > 0 && (
        <div className="bg-card border border-border rounded-[6px] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <h2 className="font-serif text-xl font-normal text-foreground">Son Siparişleriniz</h2>
            <Link
              to="/hesabim/siparisler"
              className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Tümünü Gör →
            </Link>
          </div>
          <div className="divide-y divide-border">
            {orders.slice(0, 3).map((order) => (
              <Link
                key={order.orderNo}
                to={`/hesabim/siparisler/${encodeURIComponent(order.orderNo)}`}
                className="py-3.5 flex flex-wrap items-center justify-between gap-3 hover:bg-muted px-2.5 -mx-2.5 rounded-[4px] transition-colors text-xs"
              >
                <div>
                  <div className="font-mono font-semibold text-foreground">{order.orderNo}</div>
                  <div className="text-muted-foreground mt-0.5">
                    {new Date(order.createdAt).toLocaleDateString('tr-TR')} · {order.items.length}{' '}
                    kalem
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className={`font-medium ${getOrderStatusColor(order.status)}`}>
                    {B2C_STATUS_LABELS[order.status]}
                  </span>
                  <span className="font-mono font-semibold text-foreground tabular-nums">
                    {formatTrNumber(order.grandTotalTry, 2)} TL
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </B2cAccountShell>
  );
}

type StorefrontAddress = {
  id: string;
  title: string;
  city: string;
  line: string;
  contactName: string;
  phone: string;
  addressType: string;
  isDefault: boolean;
};

export function B2cAddressesPage() {
  const [addresses, setAddresses] = useState<StorefrontAddress[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ title: '', city: '', line: '', phone: '' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<StorefrontAddress[]>('/api/v1/storefront/addresses');
      setAddresses(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError('Adresler yüklenemedi.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addAddress() {
    if (!form.title.trim() || !form.line.trim()) return;
    setSaving(true);
    try {
      await apiFetch('/api/v1/storefront/addresses', {
        method: 'POST',
        body: {
          title: form.title.trim(),
          city: form.city.trim(),
          line: form.line.trim(),
          phone: form.phone.trim(),
          addressType: 'SHIPPING',
          isDefault: addresses.length === 0,
        },
      });
      setForm({ title: '', city: '', line: '', phone: '' });
      await load();
    } catch {
      setError('Adres eklenemedi.');
    } finally {
      setSaving(false);
    }
  }

  async function setDefaultAddress(id: string) {
    try {
      await apiFetch(`/api/v1/storefront/addresses/${id}`, {
        method: 'PATCH',
        body: { isDefault: true },
      });
      await load();
    } catch {
      setError('Varsayılan adres güncellenemedi.');
    }
  }

  async function removeAddress(id: string) {
    try {
      await apiFetch(`/api/v1/storefront/addresses/${id}`, { method: 'DELETE' });
      await load();
    } catch {
      setError('Adres silinemedi.');
    }
  }

  return (
    <B2cAccountShell
      activeTab="addresses"
      title="Adreslerim"
      breadcrumbLabel="Adreslerim"
      subtitle="Sigortalı değerli kargo teslimat adresleriniz."
    >
      <div className="bg-card border border-border rounded-[6px] p-4 grid gap-2 md:grid-cols-2 mb-4">
        <input
          className="border border-border rounded-md px-3 py-2 text-xs bg-background"
          placeholder="Başlık (Ev / İş)"
          value={form.title}
          onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
        />
        <input
          className="border border-border rounded-md px-3 py-2 text-xs bg-background"
          placeholder="Şehir"
          value={form.city}
          onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
        />
        <input
          className="border border-border rounded-md px-3 py-2 text-xs bg-background md:col-span-2"
          placeholder="Adres satırı"
          value={form.line}
          onChange={(e) => setForm((p) => ({ ...p, line: e.target.value }))}
        />
        <input
          className="border border-border rounded-md px-3 py-2 text-xs bg-background"
          placeholder="Telefon"
          value={form.phone}
          onChange={(e) => setForm((p) => ({ ...p, phone: e.target.value }))}
        />
        <button
          type="button"
          className={TARA_PRIMARY_BTN_CLASS}
          disabled={saving}
          onClick={() => void addAddress()}
        >
          Adres Ekle
        </button>
      </div>

      {error && <p className="text-xs text-destructive mb-3">{error}</p>}
      {loading ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : addresses.length === 0 ? (
        <StorefrontEmptyState
          icon={<MapPin className="w-8 h-8" />}
          title="Kayıtlı teslimat adresi bulunmuyor"
          description="Yeni adres ekleyebilir veya ödeme adımında girdiğiniz adresi kaydedebilirsiniz."
          action={
            <Link to="/koleksiyon" className={TARA_PRIMARY_BTN_CLASS}>
              <span>Koleksiyonu Keşfet</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {addresses.map((addr) => (
            <div
              key={addr.id}
              className="bg-card border border-border rounded-[6px] p-5 space-y-2.5 text-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-serif text-base font-medium text-foreground">{addr.title}</span>
                <span className="font-mono text-[11px] text-muted-foreground">{addr.city}</span>
              </div>
              <p className="text-muted-foreground leading-relaxed">{addr.line}</p>
              <div className="pt-2.5 border-t border-border flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
                <span>{addr.phone || addr.contactName || '—'}</span>
                <div className="flex items-center gap-3">
                  {addr.isDefault ? (
                    <span className="font-medium text-foreground">Varsayılan</span>
                  ) : (
                    <button
                      type="button"
                      className="underline cursor-pointer"
                      onClick={() => void setDefaultAddress(addr.id)}
                    >
                      Varsayılan Yap
                    </button>
                  )}
                  <button
                    type="button"
                    className="underline cursor-pointer"
                    onClick={() => void removeAddress(addr.id)}
                  >
                    Sil
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </B2cAccountShell>
  );
}

export function B2cOrdersListPage() {
  const ordersQuery = useB2cOrdersQuery();
  const orders = ordersQuery.data ?? [];

  return (
    <B2cAccountShell
      activeTab="orders"
      title="Siparişlerim"
      breadcrumbLabel="Siparişlerim"
      subtitle="Tamamlanan perakende siparişleriniz, atölye durumu ve sigortalı kargo takibi."
    >
      {orders.length === 0 ? (
        <StorefrontEmptyState
          icon={<Package className="w-8 h-8" />}
          title="Henüz tamamlanmış siparişiniz bulunmuyor"
          description="Koleksiyonumuzdan beğendiğiniz tasarımları sepetinize ekleyip 15 dakikalık canlı altın fiyat kilidiyle sipariş oluşturabilirsiniz."
          action={
            <Link to="/koleksiyon" className={TARA_PRIMARY_BTN_CLASS}>
              <span>Koleksiyonu Keşfet</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <article
              key={order.orderNo}
              className="bg-card border border-border rounded-[6px] p-5 sm:p-6 space-y-4 hover:border-ring transition-colors"
            >
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="font-mono text-sm font-semibold text-foreground">
                      {order.orderNo}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(order.createdAt).toLocaleString('tr-TR')}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {order.shippingCity} ·{' '}
                    {order.paymentMethod === 'BANK_TRANSFER'
                      ? 'Havale / EFT (%3 İndirimli)'
                      : 'Kredi Kartı (3D Secure)'}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 sm:gap-4">
                  <span
                    className={`text-xs font-medium inline-flex items-center gap-1.5 ${getOrderStatusColor(order.status)}`}
                  >
                    <Truck className="w-3.5 h-3.5" />
                    <span>{B2C_STATUS_LABELS[order.status]}</span>
                  </span>
                  <span className="font-mono text-base font-semibold text-foreground tabular-nums">
                    {formatTrNumber(order.grandTotalTry, 2)} TL
                  </span>
                  <Link
                    to={`/hesabim/siparisler/${encodeURIComponent(order.orderNo)}`}
                    className={`${TARA_SECONDARY_BTN_CLASS} min-h-[36px] px-3.5`}
                  >
                    Detay
                  </Link>
                </div>
              </div>

              <div className="space-y-2 text-xs">
                {order.items.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-baseline justify-between gap-2 text-muted-foreground"
                  >
                    <span>
                      <strong className="text-foreground">{item.qty}×</strong> {item.title} (
                      {item.purityCode} {item.metalColor} · {item.sizeUnitLabel} {item.size})
                    </span>
                    <span className="font-mono tabular-nums text-foreground">
                      {formatTrNumber(item.unitFinalPriceTry * item.qty, 2)} TL
                    </span>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </B2cAccountShell>
  );
}

type PaymentSummary = {
  orderNo: string;
  orderStatus: string;
  paymentMethod?: string;
  bankAccounts?: Array<{
    id: string;
    bankName: string;
    accountHolder: string;
    iban: string;
  }>;
  transactions: Array<{
    id: string;
    provider?: string;
    status: string;
    paidPrice: string;
    basePrice?: string;
    refundedAmount: string;
    currency: string;
    lastFourDigits: string;
    cardFamily?: string;
    paymentId: string;
    installment: number;
    transferReference?: string;
    bankName?: string;
    iban?: string;
    accountHolder?: string;
    receiptStatus?: string;
    createdAt: string;
  }>;
  refundRequests: Array<{
    id: string;
    kind: string;
    status: string;
    requestedAmount: string | null;
    reason: string;
    createdAt: string;
    reviewedAt: string | null;
  }>;
};

const REFUND_STATUS_STEPS = ['PENDING', 'APPROVED', 'COMPLETED'] as const;
const REFUND_STATUS_TR: Record<string, string> = {
  PENDING: 'İnceleniyor',
  APPROVED: 'Onaylandı',
  REJECTED: 'Reddedildi',
  COMPLETED: 'İade Edildi',
};

export function B2cOrderDetailPage() {
  const { orderNo } = useParams<{ orderNo: string }>();
  const ordersQuery = useB2cOrdersQuery();
  const order = (ordersQuery.data ?? []).find((o) => o.orderNo === orderNo);
  const [paymentSummary, setPaymentSummary] = useState<PaymentSummary | null>(null);
  const [refundReason, setRefundReason] = useState('');
  const [refundKind, setRefundKind] = useState<'REFUND' | 'CANCEL'>('REFUND');
  const [refundIban, setRefundIban] = useState('');
  const [refundHolder, setRefundHolder] = useState('');
  const [payError, setPayError] = useState<string | null>(null);
  const [payOk, setPayOk] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadPayments = useCallback(async () => {
    if (!orderNo) return;
    try {
      const res = await apiFetch<PaymentSummary>(
        `/api/v1/storefront/orders/${encodeURIComponent(orderNo)}/payments`
      );
      setPaymentSummary(res.data ?? null);
    } catch {
      setPaymentSummary(null);
    }
  }, [orderNo]);

  useEffect(() => {
    void loadPayments();
  }, [loadPayments]);

  const submitRefundRequest = async () => {
    if (!orderNo) return;
    setPayError(null);
    setPayOk(null);
    try {
      await apiFetch(`/api/v1/storefront/orders/${encodeURIComponent(orderNo)}/refund-requests`, {
        method: 'POST',
        body: {
          kind: refundKind,
          reason: refundReason,
          refundIban: refundIban || undefined,
          refundAccountHolder: refundHolder || undefined,
        },
      });
      setPayOk('Talebiniz alındı. Durumu bu ekrandan takip edebilirsiniz.');
      setRefundReason('');
      setRefundIban('');
      setRefundHolder('');
      await loadPayments();
    } catch (e) {
      setPayError(e instanceof Error ? e.message : 'Talep oluşturulamadı');
    }
  };

  const uploadReceipt = async (file: File) => {
    if (!orderNo) return;
    setUploading(true);
    setPayError(null);
    setPayOk(null);
    try {
      const form = new FormData();
      form.append('file', file);
      await apiFetch(`/api/v1/storefront/orders/${encodeURIComponent(orderNo)}/receipt`, {
        method: 'POST',
        body: form,
      });
      setPayOk('Dekont yüklendi. Onay bekleniyor.');
      await loadPayments();
    } catch (e) {
      setPayError(e instanceof Error ? e.message : 'Dekont yüklenemedi');
    } finally {
      setUploading(false);
    }
  };

  const latestTx = paymentSummary?.transactions?.[0];
  const latestReq = paymentSummary?.refundRequests?.[0];
  const canRequestRefund =
    !!order &&
    !['IPTAL_EDILDI', 'IADE_EDILDI', 'ODEME_BEKLIYOR'].includes(order.status) &&
    latestTx?.status === 'SUCCESS' &&
    (!latestReq || latestReq.status === 'REJECTED');

  return (
    <B2cAccountShell
      activeTab="orders"
      title={order ? `Sipariş ${order.orderNo}` : 'Sipariş Detayı'}
      breadcrumbLabel={order ? order.orderNo : 'Sipariş Detayı'}
      subtitle="Sabitlenen kur snapshot bilgisi, ürün detayları ve sigortalı teslimat özeti."
    >
      <Link
        to="/hesabim/siparisler"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Tüm Siparişlerime Dön</span>
      </Link>

      {!order ? (
        <StorefrontEmptyState
          icon={<Package className="w-8 h-8" />}
          title="Sipariş bulunamadı"
          description="Belirtilen sipariş numarası hesabınızda bulunamadı."
          action={
            <Link to="/hesabim/siparisler" className={TARA_SECONDARY_BTN_CLASS}>
              Siparişlerime Dön
            </Link>
          }
        />
      ) : (
        <div className="space-y-6">
          {/* Top Metadata Summary */}
          <div className="bg-card border border-border rounded-[6px] p-5 sm:p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 text-xs">
            <div>
              <div className="text-muted-foreground">Sipariş Durumu</div>
              <div className={`font-semibold mt-1 ${getOrderStatusColor(order.status)}`}>
                {B2C_STATUS_LABELS[order.status]}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Sipariş Tarihi</div>
              <div className="font-medium text-foreground mt-1">
                {new Date(order.createdAt).toLocaleString('tr-TR')}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Sabitlenen Kur Snapshot</div>
              <div className="font-mono text-foreground mt-1">{order.snapshotId}</div>
              <div className="font-mono text-[11px] text-muted-foreground tabular-nums mt-0.5">
                Has: {formatTrNumber(order.goldRateTryPerGram, 2)} TL/gr
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Ödeme Yöntemi</div>
              <div className="font-medium text-foreground mt-1">
                {order.paymentMethod === 'BANK_TRANSFER'
                  ? 'Havale / EFT (%3 İndirimli)'
                  : 'Kredi Kartı (3D Secure)'}
              </div>
            </div>
          </div>

          {/* Line Items */}
          <div className="bg-card border border-border rounded-[6px] overflow-hidden">
            <div className="px-5 sm:px-6 py-4 border-b border-border flex items-center justify-between">
              <h2 className="font-serif text-xl font-normal text-foreground">
                Sipariş Kalemleri ({order.items.length})
              </h2>
            </div>
            <div className="divide-y divide-border">
              {order.items.map((item) => (
                <div
                  key={item.id}
                  className="px-5 sm:px-6 py-4 flex flex-wrap items-start justify-between gap-4 text-xs"
                >
                  <div className="space-y-1">
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {item.sku} · {item.certificateLabel}
                    </div>
                    <div className="font-serif text-base font-medium text-foreground">
                      {item.qty}× {item.title}
                    </div>
                    <div className="text-muted-foreground tabular-nums">
                      {item.purityCode} {item.metalColor} Altın · {item.sizeUnitLabel} {item.size} ·{' '}
                      {formatTrNumber(item.grossWeightGram, 2)} gr
                    </div>
                    {item.engravingText && (
                      <div className="text-muted-foreground font-medium">
                        Lazer İç Yazı: “{item.engravingText}”
                      </div>
                    )}
                    {item.giftWrap && (
                      <div className="text-muted-foreground">
                        Kadife Hediye Kutusu {item.giftNote ? `· Not: “${item.giftNote}”` : ''}
                      </div>
                    )}
                  </div>
                  <div className="text-right font-mono tabular-nums">
                    <div className="font-semibold text-foreground text-sm">
                      {formatTrNumber(item.unitFinalPriceTry * item.qty, 2)} TL
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      Birim: {formatTrNumber(item.unitFinalPriceTry, 2)} TL
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Delivery & Payment Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-card border border-border rounded-[6px] p-5 sm:p-6 space-y-2 text-xs">
              <h3 className="font-serif text-lg font-normal text-foreground pb-2 border-b border-border">
                Teslimat Bilgileri
              </h3>
              <div className="font-medium text-foreground pt-1">{order.customerName}</div>
              <div className="text-muted-foreground leading-relaxed">{order.shippingAddress}</div>
              <div className="text-muted-foreground">{order.shippingCity}</div>
              <div className="text-muted-foreground pt-1">
                {order.customerPhone} · {order.customerEmail}
              </div>
            </div>

            <div className="bg-card border border-border rounded-[6px] p-5 sm:p-6 space-y-2.5 text-xs">
              <h3 className="font-serif text-lg font-normal text-foreground pb-2 border-b border-border">
                Ödeme Özeti
              </h3>
              <div className="flex justify-between pt-1">
                <span className="text-muted-foreground">Liste Toplamı</span>
                <span className="font-mono tabular-nums text-foreground">
                  {formatTrNumber(order.subtotalListTry, 2)} TL
                </span>
              </div>
              {order.campaignDiscountTry > 0 && (
                <div className="flex justify-between text-foreground">
                  <span>Kampanya İndirimi</span>
                  <span className="font-mono tabular-nums">
                    -{formatTrNumber(order.campaignDiscountTry, 2)} TL
                  </span>
                </div>
              )}
              {order.transferDiscountTry > 0 && (
                <div className="flex justify-between text-success">
                  <span>Havale / EFT İndirimi</span>
                  <span className="font-mono tabular-nums">
                    -{formatTrNumber(order.transferDiscountTry, 2)} TL
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Sigortalı Kargo</span>
                <span className="font-mono tabular-nums text-foreground">
                  {order.insuredShippingTry === 0
                    ? 'Ücretsiz'
                    : `${formatTrNumber(order.insuredShippingTry, 2)} TL`}
                </span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Dahil KDV (%20)</span>
                <span className="font-mono tabular-nums">
                  {formatTrNumber(order.vatIncludedTry, 2)} TL
                </span>
              </div>
              <div className="pt-3 border-t border-border flex justify-between items-baseline">
                <span className="font-semibold text-sm text-foreground">Genel Toplam</span>
                <span className="font-mono text-base font-semibold text-foreground tabular-nums">
                  {formatTrNumber(order.grandTotalTry, 2)} TL
                </span>
              </div>
            </div>
          </div>

          {/* Payment & refund request */}
          <div className="bg-card border border-border rounded-[6px] p-5 sm:p-6 space-y-4 text-xs">
            <h3 className="font-serif text-lg font-normal text-foreground">Ödeme &amp; İade Durumu</h3>
            {latestTx ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <div className="text-muted-foreground">İşlem Durumu</div>
                    <div className="font-medium text-foreground mt-1">{latestTx.status}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Ödenen / İade</div>
                    <div className="font-mono mt-1">
                      {latestTx.paidPrice} {latestTx.currency}
                      {Number(latestTx.refundedAmount) > 0
                        ? ` · iade ${latestTx.refundedAmount}`
                        : ''}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">
                      {latestTx.provider === 'BANK_TRANSFER' ? 'Havale Referansı' : 'Kart / Taksit'}
                    </div>
                    <div className="font-mono mt-1">
                      {latestTx.provider === 'BANK_TRANSFER'
                        ? latestTx.transferReference || '—'
                        : `${latestTx.lastFourDigits ? `****${latestTx.lastFourDigits}` : '—'}${
                            latestTx.installment > 1 ? ` · ${latestTx.installment}T` : ''
                          }${latestTx.cardFamily ? ` · ${latestTx.cardFamily}` : ''}`}
                    </div>
                  </div>
                </div>

                {latestTx.provider === 'BANK_TRANSFER' && (
                  <div className="rounded-[4px] border border-border bg-white p-3 space-y-2">
                    <div className="font-medium text-foreground">Havale Hesabı</div>
                    <div>{latestTx.bankName}</div>
                    <div>{latestTx.accountHolder}</div>
                    <div className="font-mono text-[11px]">{latestTx.iban}</div>
                    {(paymentSummary?.bankAccounts ?? []).length > 1 && (
                      <div className="pt-2 border-t border-border space-y-1">
                        <div className="text-muted-foreground">Diğer hesaplar</div>
                        {paymentSummary?.bankAccounts?.map((b) => (
                          <div key={b.id} className="font-mono text-[11px]">
                            {b.bankName}: {b.iban}
                          </div>
                        ))}
                      </div>
                    )}
                    {order.status === 'ODEME_BEKLIYOR' && (
                      <label className={`${TARA_SECONDARY_BTN_CLASS} cursor-pointer inline-flex`}>
                        {uploading ? 'Yükleniyor…' : 'Dekont Yükle (PDF/JPG/PNG)'}
                        <input
                          type="file"
                          accept=".pdf,.jpg,.jpeg,.png"
                          className="hidden"
                          disabled={uploading}
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) void uploadReceipt(f);
                          }}
                        />
                      </label>
                    )}
                    {latestTx.receiptStatus && latestTx.receiptStatus !== 'NONE' && (
                      <div className="text-[11px] text-success">
                        Dekont durumu: {latestTx.receiptStatus}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">Ödeme kaydı bulunamadı.</p>
            )}

            {latestReq && (
              <div className="space-y-3 pt-2 border-t border-border">
                <div className="font-medium text-foreground">
                  Talep: {latestReq.kind} · {REFUND_STATUS_TR[latestReq.status] ?? latestReq.status}
                </div>
                <div className="flex items-center gap-2">
                  {REFUND_STATUS_STEPS.map((step, idx) => {
                    const activeIdx = REFUND_STATUS_STEPS.indexOf(
                      (latestReq.status === 'REJECTED' ? 'PENDING' : latestReq.status) as
                        | 'PENDING'
                        | 'APPROVED'
                        | 'COMPLETED'
                    );
                    const done = activeIdx >= idx || latestReq.status === 'COMPLETED';
                    return (
                      <div key={step} className="flex items-center gap-2 flex-1">
                        <div
                          className={`h-2 flex-1 rounded-full ${
                            done || latestReq.status === step ? 'bg-success' : 'bg-border'
                          }`}
                        />
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                          {REFUND_STATUS_TR[step]}
                        </span>
                      </div>
                    );
                  })}
                </div>
                {latestReq.status === 'REJECTED' && (
                  <p className="text-foreground">Talep reddedildi. Yeni talep oluşturabilirsiniz.</p>
                )}
              </div>
            )}

            {payError && <p className="text-foreground">{payError}</p>}
            {payOk && <p className="text-success">{payOk}</p>}

            {canRequestRefund && (
              <div className="space-y-3 pt-2 border-t border-border">
                <div className="flex flex-wrap gap-3">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="radio"
                      checked={refundKind === 'REFUND'}
                      onChange={() => setRefundKind('REFUND')}
                    />
                    İade Talebi
                  </label>
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="radio"
                      checked={refundKind === 'CANCEL'}
                      onChange={() => setRefundKind('CANCEL')}
                    />
                    İptal Talebi
                  </label>
                </div>
                {order.paymentMethod === 'BANK_TRANSFER' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <input
                      className="rounded-[4px] border border-border bg-white px-3 py-2 text-xs font-mono"
                      placeholder="İade IBAN (zorunlu)"
                      value={refundIban}
                      onChange={(e) => setRefundIban(e.target.value)}
                    />
                    <input
                      className="rounded-[4px] border border-border bg-white px-3 py-2 text-xs"
                      placeholder="Hesap sahibi (zorunlu)"
                      value={refundHolder}
                      onChange={(e) => setRefundHolder(e.target.value)}
                    />
                  </div>
                )}
                <textarea
                  className="w-full min-h-[80px] rounded-[4px] border border-border bg-white px-3 py-2 text-xs"
                  placeholder="Talep gerekçeniz…"
                  value={refundReason}
                  onChange={(e) => setRefundReason(e.target.value)}
                />
                <button
                  type="button"
                  className={TARA_PRIMARY_BTN_CLASS}
                  onClick={() => void submitRefundRequest()}
                >
                  İptal / İade Talebi Oluştur
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </B2cAccountShell>
  );
}

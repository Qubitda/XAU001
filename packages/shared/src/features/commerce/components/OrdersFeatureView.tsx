import { useEffect, useState } from 'react';
import {
  Building2,
  Check,
  ClipboardList,
  Copy,
  PackageCheck,
  RotateCcw,
  Search,
  ShoppingBag,
  Truck,
} from 'lucide-react';
import { PortalDataCard, PortalPageHeader, PortalStat } from '../../../components/portal';
import { Badge, Button, Input, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui';
import { useAuth } from '../../../providers/AuthProvider';
import { useActiveProductMetrics } from '../../catalog/hooks/useCatalogQueries';
import { formatCurrencyValue, formatTrNumber } from '../../../utils/pricingEngine';
import {
  useB2bDraftQuery,
  useB2bOrdersQuery,
  useB2cCartQuery,
  useB2cOrdersQuery,
  useCommerceUI,
  useReorderB2bOrderMutation,
  useUpdateB2bOrderStatusMutation,
  useUpdateB2cOrderStatusMutation,
} from '../hooks/useCommerceQueries';
import { useOpsB2bOrdersQuery, useOpsB2cOrdersQuery } from '../../ops/hooks/useOpsQueries';
import type { B2bOrderRecord, B2cOrderRecord } from '../types';

const B2C_STATUS_LABELS: Record<B2cOrderRecord['status'], string> = {
  ODEME_BEKLIYOR: 'Ödeme Bekleniyor',
  ONAYLANDI: 'Sipariş Onaylandı',
  ATOLYE_URETIMDE: 'Atölye & Kalite Kontrol',
  SIGORTALI_KARGODA: 'Sigortalı Kurye Yolda',
  IPTAL_EDILDI: 'İptal Edildi',
  IADE_EDILDI: 'İade Edildi',
};

const B2B_STATUS_LABELS: Record<B2bOrderRecord['status'], string> = {
  PROFORMA_ONAYLANDI: 'Proforma Onaylandı',
  ATOLYE_PLANLANDI: 'Atölye Üretim Planlandı',
  SEVK_HAZIR: 'Sevke Hazır (Tartım Tamam)',
  IPTAL_EDILDI: 'İptal Edildi',
  IADE_EDILDI: 'İade Edildi',
};

const SETTLEMENT_NAMES: Record<B2bOrderRecord['settlementMethod'], string> = {
  HAS_PLUS_CURRENCY: 'Has Altın + İşçilik/Taş Dövizi',
  FX_CASH: 'Döviz Nakit / Havale',
  CONSIGNMENT: 'Konsinye / Emanet',
  OPEN_ACCOUNT: 'Cari Hesap / Vadeli',
};

function buildB2bProformaText(order: B2bOrderRecord): string {
  const hasInternal =
    order.totalHasGoldGram != null && order.totalLaborAndStoneUsd != null;
  return [
    `PROFORMA / SİPARİŞ FİŞİ — ${order.orderNo}`,
    `Firma: ${order.dealerName} (${order.dealerCode}) · Şube: ${order.branchName}`,
    `Oluşturan: ${order.createdByUserName} · Yetkili: ${order.contactPerson}`,
    `Hesaplaşma: ${SETTLEMENT_NAMES[order.settlementMethod]}`,
    `Toplam: ${order.totalPieces} adet · ${formatTrNumber(order.totalGrossGram, 2)} gr brüt`,
    hasInternal && order.settlementMethod === 'HAS_PLUS_CURRENCY'
      ? `Tahsilat (OPS): ${formatTrNumber(order.totalHasGoldGram!, 4)} gr Has + $${formatTrNumber(order.totalLaborAndStoneUsd!, 2)}`
      : `Tahsilat: $${formatTrNumber(order.totalWholesaleUsd, 2)} (${formatTrNumber(order.totalWholesaleTry, 0)} TL)`,
  ].join('\n');
}

interface OrdersFeatureViewProps {
  portalMode?: 'b2c' | 'b2b' | 'ops';
}

const TAB_ACTIVE = 'bg-foreground text-background';

export function OrdersFeatureView({ portalMode }: OrdersFeatureViewProps = {}) {
  const { role } = useAuth();
  const isOpsDesk = portalMode === 'ops';
  const isOrdersAdmin = isOpsDesk || role === 'erp';
  const isZincPortal =
    portalMode === 'ops' ||
    portalMode === 'b2b' ||
    role === 'erp' ||
    (role === 'b2b' && portalMode !== 'b2c');
  const isBrandB2c = !isZincPortal && (portalMode === 'b2c' || role === 'b2c');
  const tabActiveClass = TAB_ACTIVE;
  const progressBarActive = 'bg-foreground';
  const hasGoldAccent = 'text-muted-foreground';
  const { rates } = useActiveProductMetrics();
  const { setB2cCartOpen, setB2bOrderOpen } = useCommerceUI();

  const b2cCart = useB2cCartQuery();
  const b2cOrdersQuery = useB2cOrdersQuery();
  const b2bDraft = useB2bDraftQuery();
  const b2bOrdersQuery = useB2bOrdersQuery();
  const updateB2cStatus = useUpdateB2cOrderStatusMutation();
  const updateB2bStatus = useUpdateB2bOrderStatusMutation();
  const reorderB2b = useReorderB2bOrderMutation();

  const [erpChannelTab, setErpChannelTab] = useState<'b2b' | 'b2c'>('b2b');
  const [opsOrderQ, setOpsOrderQ] = useState('');
  const [debouncedOpsQ, setDebouncedOpsQ] = useState('');
  const [opsOrderStatus, setOpsOrderStatus] = useState<string>('all');
  const [copiedOrderNo, setCopiedOrderNo] = useState<string | null>(null);
  const [reorderedNo, setReorderedNo] = useState<string | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedOpsQ(opsOrderQ.trim()), 300);
    return () => window.clearTimeout(t);
  }, [opsOrderQ]);

  const opsOrderFilters = {
    q: debouncedOpsQ || undefined,
    status: opsOrderStatus === 'all' ? undefined : opsOrderStatus,
    pageSize: 100,
  };

  const opsB2cOrdersQuery = useOpsB2cOrdersQuery(opsOrderFilters, isOpsDesk);
  const opsB2bOrdersQuery = useOpsB2bOrdersQuery(opsOrderFilters, isOpsDesk);

  const b2cOrders = isOpsDesk
    ? (opsB2cOrdersQuery.data?.items ?? [])
    : (b2cOrdersQuery.data ?? []);
  const b2bOrders = isOpsDesk
    ? (opsB2bOrdersQuery.data?.items ?? [])
    : (b2bOrdersQuery.data ?? []);
  const dealer = b2bDraft.data?.dealer;
  const b2cCartCount = (b2cCart.data?.items ?? []).reduce((s, i) => s + i.qty, 0);
  const b2bDraftPieces = (b2bDraft.data?.lines ?? []).reduce((s, l) => s + l.qty, 0);

  const handleCopyProforma = (order: B2bOrderRecord) => {
    navigator.clipboard?.writeText(buildB2bProformaText(order)).catch(() => {});
    setCopiedOrderNo(order.orderNo);
    window.setTimeout(() => setCopiedOrderNo(null), 1800);
  };

  const handleReorder = async (orderNo: string) => {
    await reorderB2b.mutateAsync(orderNo);
    setReorderedNo(orderNo);
    window.setTimeout(() => setReorderedNo(null), 1800);
    setB2bOrderOpen(true);
  };

  const activeView = isOrdersAdmin ? erpChannelTab : role;

  const headerEyebrow =
    role === 'b2c'
      ? 'Hesabım · Sigortalı Teslimat ve Sertifika Takibi'
      : role === 'b2b'
        ? 'Bayi Portalı · Cari Hesap, Has Bakiye ve Toptan Proformalar'
        : 'Sipariş Operasyon Masası · B2B Toptan ve B2C Perakende Takip';

  const headerTitle =
    role === 'b2c'
      ? 'Siparişlerim'
      : role === 'b2b'
        ? 'Bayi Siparişleri & Cari Hesap'
        : 'Sipariş Yönetimi';

  const headerActions = (
    <>
      {isOrdersAdmin && (
        <div
          className={`inline-flex rounded-md border p-0.5 text-xs ${
            isZincPortal ? 'border-border bg-muted/40' : 'border-zinc-200 bg-zinc-100'
          }`}
        >
          <button
            type="button"
            onClick={() => setErpChannelTab('b2b')}
            className={`px-3 py-1.5 rounded-[5px] font-medium transition-colors cursor-pointer ${
              erpChannelTab === 'b2b'
                ? tabActiveClass
                : isZincPortal
                  ? 'text-muted-foreground hover:text-foreground'
                  : 'text-zinc-600 hover:text-foreground'
            }`}
          >
            B2B Toptan ({b2bOrders.length})
          </button>
          <button
            type="button"
            onClick={() => setErpChannelTab('b2c')}
            className={`px-3 py-1.5 rounded-[5px] font-medium transition-colors cursor-pointer ${
              erpChannelTab === 'b2c'
                ? tabActiveClass
                : isZincPortal
                  ? 'text-muted-foreground hover:text-foreground'
                  : 'text-zinc-600 hover:text-foreground'
            }`}
          >
            B2C Perakende ({b2cOrders.length})
          </button>
        </div>
      )}

      {isOpsDesk ? (
        <>
          <Select value={opsOrderStatus} onValueChange={setOpsOrderStatus}>
            <SelectTrigger className="h-9 w-44 text-xs">
              <SelectValue placeholder="Durum" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tüm durumlar</SelectItem>
              {erpChannelTab === 'b2c'
                ? Object.entries(B2C_STATUS_LABELS).map(([val, label]) => (
                    <SelectItem key={val} value={val}>
                      {label}
                    </SelectItem>
                  ))
                : Object.entries(B2B_STATUS_LABELS).map(([val, label]) => (
                    <SelectItem key={val} value={val}>
                      {label}
                    </SelectItem>
                  ))}
            </SelectContent>
          </Select>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
            <Input
              value={opsOrderQ}
              onChange={(e) => setOpsOrderQ(e.target.value)}
              placeholder="Sipariş ara..."
              className="h-9 pl-8 w-48 text-xs"
            />
          </div>
        </>
      ) : activeView === 'b2c' ? (
        <Button size="sm" onClick={() => setB2cCartOpen(true)}>
          <ShoppingBag className="w-3.5 h-3.5" />
          Aktif Sepet ({b2cCartCount})
        </Button>
      ) : (
        <Button size="sm" onClick={() => setB2bOrderOpen(true)}>
          <ClipboardList className="w-3.5 h-3.5" />
          Aktif Sipariş Fişi ({b2bDraftPieces} adet)
        </Button>
      )}
    </>
  );

  return (
    <div className={isZincPortal ? 'space-y-6' : 'space-y-8'}>
      {isZincPortal ? (
        <PortalPageHeader eyebrow={headerEyebrow} title={headerTitle} actions={headerActions} />
      ) : (
        <section className="border-b border-zinc-200 pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-1.5">
            <p className="text-xs text-zinc-500">{headerEyebrow}</p>
            <h1 className="font-serif text-3xl md:text-4xl font-semibold text-foreground">
              {headerTitle}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">{headerActions}</div>
        </section>
      )}

      {activeView === 'b2b' && dealer && !isOpsDesk && (
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {isZincPortal ? (
            <>
              <PortalStat
                label="Bayi Hesabı"
                icon={<Building2 className="w-3.5 h-3.5 text-muted-foreground" />}
                value={
                  <span className="text-base font-sans font-medium truncate">
                    {dealer.companyName}
                  </span>
                }
                hint={
                  <span className="font-mono">
                    {dealer.dealerCode} · {dealer.city}
                  </span>
                }
              />
              <PortalStat
                label="Kullanılabilir Cari Limit"
                value={`$${formatTrNumber(Math.max(0, dealer.creditLimitUsd - dealer.usedCreditUsd), 0)}`}
                hint={`Kullanılan: $${formatTrNumber(dealer.usedCreditUsd, 0)} / $${formatTrNumber(dealer.creditLimitUsd, 0)}`}
              />
              <PortalStat
                label="Kullanılabilir Has Altın Limiti"
                value={`${formatTrNumber(Math.max(0, dealer.hasLimitGram - dealer.usedHasGram), 2)} gr`}
                hint={`Açık Has: ${formatTrNumber(dealer.usedHasGram, 2)} gr / ${dealer.hasLimitGram} gr`}
                valueClassName="text-muted-foreground"
              />
              <PortalStat
                label="Canlı Referans Kur"
                value={`${formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr`}
                hint={`USD: ${formatTrNumber(rates.liveUsdSell, 2)} TL · EUR: ${formatTrNumber(rates.liveEurSell, 2)} TL`}
              />
            </>
          ) : (
            <>
              <div className="bg-white border border-zinc-200 rounded-lg p-5">
                <div className="text-xs text-zinc-500 flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-muted-foreground" />
                  Bayi Hesabı
                </div>
                <div className="font-medium text-sm text-foreground mt-1.5 truncate">
                  {dealer.companyName}
                </div>
                <div className="font-mono text-xs text-zinc-500 mt-0.5">
                  {dealer.dealerCode} · {dealer.city}
                </div>
              </div>
              <div className="bg-white border border-zinc-200 rounded-lg p-5">
                <div className="text-xs text-zinc-500">Kullanılabilir Cari Limit</div>
                <div className="font-mono text-xl font-semibold text-foreground tabular-nums mt-1.5">
                  ${formatTrNumber(Math.max(0, dealer.creditLimitUsd - dealer.usedCreditUsd), 0)}
                </div>
                <div className="font-mono text-[11px] text-zinc-500 tabular-nums mt-0.5">
                  Kullanılan: ${formatTrNumber(dealer.usedCreditUsd, 0)} / $
                  {formatTrNumber(dealer.creditLimitUsd, 0)}
                </div>
              </div>
              <div className="bg-white border border-zinc-200 rounded-lg p-5">
                <div className="text-xs text-zinc-500">Kullanılabilir Has Altın Limiti</div>
                <div className={`font-mono text-xl font-semibold tabular-nums mt-1.5 ${hasGoldAccent}`}>
                  {formatTrNumber(Math.max(0, dealer.hasLimitGram - dealer.usedHasGram), 2)} gr
                </div>
                <div className="font-mono text-[11px] text-zinc-500 tabular-nums mt-0.5">
                  Açık Has Bakiye: {formatTrNumber(dealer.usedHasGram, 2)} gr / {dealer.hasLimitGram}{' '}
                  gr
                </div>
              </div>
              <div className="bg-white border border-zinc-200 rounded-lg p-5">
                <div className="text-xs text-zinc-500">Canlı Referans Kur</div>
                <div className="font-mono text-xl font-semibold text-foreground tabular-nums mt-1.5">
                  {formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr
                </div>
                <div className="font-mono text-[11px] text-zinc-500 tabular-nums mt-0.5">
                  USD: {formatTrNumber(rates.liveUsdSell, 2)} TL · EUR:{' '}
                  {formatTrNumber(rates.liveEurSell, 2)} TL
                </div>
              </div>
            </>
          )}
        </section>
      )}

      {activeView === 'b2c' && (
        <section className="space-y-4">
          {b2cOrders.length === 0 ? (
            isZincPortal ? (
              <PortalDataCard contentClassName="py-16 px-6 text-center space-y-2">
                <PackageCheck className="w-9 h-9 text-muted-foreground/40 mx-auto" />
                <div className="text-base font-semibold text-foreground">
                  Henüz perakende sipariş kaydı yok
                </div>
                <p className="text-xs text-muted-foreground">
                  Onaylanan B2C siparişlerin teslimat ve durum güncellemeleri bu listede görünür.
                </p>
              </PortalDataCard>
            ) : (
              <div className="bg-white border border-zinc-200 rounded-lg py-16 px-6 text-center space-y-2">
                <PackageCheck className="w-9 h-9 text-zinc-300 mx-auto" />
                <div className="font-serif text-xl font-semibold text-foreground">
                  Henüz perakende siparişiniz yok
                </div>
                <p className="text-xs text-zinc-500">
                  Sepetinize eklediğiniz tasarımları onayladığınızda sigortalı teslimat sürecini
                  buradan canlı takip edebilirsiniz.
                </p>
              </div>
            )
          ) : (
            b2cOrders.map((order) => {
              const stepIdx =
                order.status === 'ONAYLANDI'
                  ? 0
                  : order.status === 'ATOLYE_URETIMDE'
                    ? 1
                    : 2;
              const cardBody = (
                <>
                  <div
                    className={`flex flex-wrap items-start justify-between gap-4 border-b pb-4 ${
                      isZincPortal ? 'border-border' : 'border-zinc-100'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span
                          className={`font-mono text-sm font-semibold ${
                            isZincPortal ? 'text-foreground' : 'text-foreground'
                          }`}
                        >
                          {order.orderNo}
                        </span>
                        <span
                          className={`text-xs ${isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}`}
                        >
                          {new Date(order.createdAt).toLocaleString('tr-TR')}
                        </span>
                      </div>
                      <div
                        className={`text-xs ${isZincPortal ? 'text-muted-foreground' : 'text-zinc-600'}`}
                      >
                        {order.customerName} · {order.shippingCity} ·{' '}
                        {order.paymentMethod === 'BANK_TRANSFER'
                          ? 'Havale / EFT (%3 İndirimli)'
                          : 'Kredi Kartı (3D Secure)'}
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      {isOrdersAdmin ? (
                        <select
                          aria-label={`${order.orderNo} sipariş durumu`}
                          value={order.status}
                          onChange={(e) =>
                            updateB2cStatus.mutate({
                              orderNo: order.orderNo,
                              status: e.target.value as B2cOrderRecord['status'],
                            })
                          }
                          className={`h-8 px-2.5 text-xs rounded-md border ${
                            isZincPortal
                              ? 'border-border bg-background text-foreground'
                              : 'border-zinc-300 bg-white text-foreground'
                          }`}
                        >
                          <option value="ODEME_BEKLIYOR">Ödeme Bekleniyor</option>
                          <option value="ONAYLANDI">Sipariş Onaylandı</option>
                          <option value="ATOLYE_URETIMDE">Atölye & Kalite Kontrol</option>
                          <option value="SIGORTALI_KARGODA">Sigortalı Kurye Yolda</option>
                          <option value="IPTAL_EDILDI">İptal Edildi</option>
                          <option value="IADE_EDILDI">İade Edildi</option>
                        </select>
                      ) : isZincPortal ? (
                        <Badge
                          variant={
                            order.status === 'IPTAL_EDILDI' || order.status === 'IADE_EDILDI'
                              ? 'destructive'
                              : 'outline'
                          }
                          className={
                            order.status === 'IPTAL_EDILDI' || order.status === 'IADE_EDILDI'
                              ? undefined
                              : 'text-success border-success/30 gap-1'
                          }
                        >
                          <Truck className="w-3 h-3" />
                          {B2C_STATUS_LABELS[order.status]}
                        </Badge>
                      ) : (
                        <span className="text-xs font-medium text-success inline-flex items-center gap-1.5">
                          <Truck className="w-3.5 h-3.5" />
                          {B2C_STATUS_LABELS[order.status]}
                        </span>
                      )}
                      <span
                        className={`font-mono text-base font-semibold tabular-nums ${
                          isZincPortal ? 'text-foreground' : 'text-foreground'
                        }`}
                      >
                        {formatTrNumber(order.grandTotalTry, 2)} TL
                      </span>
                    </div>
                  </div>

                  {/* 3-Step Jewelry Fulfillment Progress */}
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    {(['Sipariş Onaylandı', 'Atölye & Sertifika Kontrol', 'Sigortalı Değerli Kargo'] as const).map(
                      (label, idx) => (
                        <div key={label} className="space-y-1.5">
                          <div
                            className={`h-1.5 rounded-full ${
                              idx <= stepIdx
                                ? progressBarActive
                                : isZincPortal
                                  ? 'bg-muted'
                                  : 'bg-zinc-200'
                            }`}
                          />
                          <div
                            className={
                              idx <= stepIdx
                                ? isZincPortal
                                  ? 'font-medium text-foreground'
                                  : 'font-medium text-foreground'
                                : isZincPortal
                                  ? 'text-muted-foreground'
                                  : 'text-zinc-400'
                            }
                          >
                            {label}
                          </div>
                        </div>
                      )
                    )}
                  </div>

                  {/* Line Items */}
                  <div
                    className={`divide-y text-xs ${
                      isZincPortal ? 'divide-border' : 'divide-zinc-100'
                    }`}
                  >
                    {order.items.map((item) => (
                      <div
                        key={item.id}
                        className="py-2.5 flex flex-wrap items-center justify-between gap-3"
                      >
                        <div className="space-y-0.5">
                          <div
                            className={`font-medium ${isZincPortal ? 'text-foreground' : 'text-foreground'}`}
                          >
                            {item.qty}× {item.title}
                          </div>
                          <div className={isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}>
                            {item.purityCode} {item.metalColor} Altın · {item.sizeUnitLabel}{' '}
                            {item.size} · {item.certificateLabel}
                            {item.engravingText && (
                              <span
                                className={`font-medium ${isBrandB2c ? 'text-muted-foreground' : 'text-foreground'}`}
                              >
                                {' '}
                                · İç Yazı: “{item.engravingText}”
                              </span>
                            )}
                            {item.giftWrap && ' · Kadife Hediye Kutusu'}
                          </div>
                        </div>
                        <span
                          className={`font-mono font-medium tabular-nums ${
                            isZincPortal ? 'text-foreground' : 'text-foreground'
                          }`}
                        >
                          {formatTrNumber(item.unitFinalPriceTry * item.qty, 2)} TL
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              );
              return isZincPortal ? (
                <PortalDataCard key={order.orderNo} contentClassName="p-6 space-y-5">
                  {cardBody}
                </PortalDataCard>
              ) : (
                <article
                  key={order.orderNo}
                  className="bg-white border border-zinc-200 rounded-lg p-6 space-y-5"
                >
                  {cardBody}
                </article>
              );
            })
          )}
        </section>
      )}

      {activeView === 'b2b' && (
        <section className="space-y-4">
          {b2bOrders.map((order) => {
            const b2bCard = (
              <>
              <div
                className={`flex flex-wrap items-start justify-between gap-4 border-b pb-4 ${
                  isZincPortal ? 'border-border' : 'border-zinc-100'
                }`}
              >
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span
                      className={`font-mono text-sm font-semibold ${
                        isZincPortal ? 'text-foreground' : 'text-foreground'
                      }`}
                    >
                      {order.orderNo}
                    </span>
                    <span
                      className={`text-xs ${isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}`}
                    >
                      {new Date(order.createdAt).toLocaleString('tr-TR')}
                    </span>
                    {isZincPortal && role !== 'erp' && (
                      <Badge
                        variant={
                          order.status === 'IPTAL_EDILDI' || order.status === 'IADE_EDILDI'
                            ? 'destructive'
                            : 'outline'
                        }
                        className={
                          order.status === 'IPTAL_EDILDI' || order.status === 'IADE_EDILDI'
                            ? undefined
                            : 'text-success border-success/30'
                        }
                      >
                        {B2B_STATUS_LABELS[order.status]}
                      </Badge>
                    )}
                  </div>
                  <div
                    className={`text-xs ${isZincPortal ? 'text-muted-foreground' : 'text-zinc-600'}`}
                  >
                    {order.dealerName} ·{' '}
                    <span className={isZincPortal ? 'font-medium text-foreground' : 'font-medium text-foreground'}>
                      {order.branchName}
                    </span>{' '}
                    · {SETTLEMENT_NAMES[order.settlementMethod]} ·{' '}
                    {order.rateLockMode === 'LOCK_ON_ORDER'
                      ? 'Sipariş Anı Kur Sabit'
                      : 'Teslimat Günü Kur Kesinleştirme'}
                  </div>
                  <div
                    className={`text-[11px] ${isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}`}
                  >
                    Oluşturan:{' '}
                    <span className={isZincPortal ? 'text-foreground font-medium' : 'text-zinc-700 font-medium'}>
                      {order.createdByUserName}
                    </span>{' '}
                    · Yetkili: {order.contactPerson}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2.5">
                  {isOrdersAdmin ? (
                    <select
                      aria-label={`${order.orderNo} bayi sipariş durumu`}
                      value={order.status}
                      onChange={(e) =>
                        updateB2bStatus.mutate({
                          orderNo: order.orderNo,
                          status: e.target.value as B2bOrderRecord['status'],
                        })
                      }
                      className={`h-8 px-2.5 text-xs rounded-md border ${
                        isZincPortal
                          ? 'border-border bg-background text-foreground'
                          : 'border-zinc-300 bg-white text-foreground'
                      }`}
                    >
                      <option value="PROFORMA_ONAYLANDI">Proforma Onaylandı</option>
                      <option value="ATOLYE_PLANLANDI">Atölye Üretim Planlandı</option>
                      <option value="SEVK_HAZIR">Sevke Hazır (Tartım Tamam)</option>
                      <option value="IPTAL_EDILDI">İptal Edildi</option>
                      <option value="IADE_EDILDI">İade Edildi</option>
                    </select>
                  ) : !isZincPortal ? (
                    <span className="text-xs font-medium text-success">
                      {B2B_STATUS_LABELS[order.status]}
                    </span>
                  ) : null}

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleCopyProforma(order)}
                  >
                    {copiedOrderNo === order.orderNo ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-success" />
                        Kopyalandı
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        Proforma
                      </>
                    )}
                  </Button>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void handleReorder(order.orderNo)}
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    {reorderedNo === order.orderNo ? 'Fişe Aktarıldı' : 'Tekrar Sipariş'}
                  </Button>
                </div>
              </div>

              <div
                className={`grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-md p-3.5 text-xs ${
                  isZincPortal ? 'bg-muted/40' : 'bg-zinc-50'
                }`}
              >
                <div>
                  <div className={isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}>
                    Toplam Adet / Brüt
                  </div>
                  <div
                    className={`font-mono font-semibold tabular-nums mt-0.5 ${
                      isZincPortal ? 'text-foreground' : 'text-foreground'
                    }`}
                  >
                    {order.totalPieces} adet · {formatTrNumber(order.totalGrossGram, 2)} gr
                  </div>
                </div>
                {order.totalHasGoldGram != null && order.totalLaborAndStoneUsd != null ? (
                  <>
                    <div>
                      <div className={isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}>
                        Fire Dahil Has Altın (OPS)
                      </div>
                      <div className={`font-mono font-semibold tabular-nums mt-0.5 ${hasGoldAccent}`}>
                        {formatTrNumber(order.totalHasGoldGram, 4)} gr Has
                      </div>
                    </div>
                    <div>
                      <div className={isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}>
                        İşçilik + Taş (OPS)
                      </div>
                      <div
                        className={`font-mono font-semibold tabular-nums mt-0.5 ${
                          isZincPortal ? 'text-foreground' : 'text-foreground'
                        }`}
                      >
                        ${formatTrNumber(order.totalLaborAndStoneUsd, 2)}
                      </div>
                    </div>
                  </>
                ) : null}
                <div>
                  <div className={isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}>
                    Toplam Toptan Değer
                  </div>
                  <div
                    className={`font-mono font-semibold tabular-nums mt-0.5 ${
                      isZincPortal ? 'text-foreground' : 'text-foreground'
                    }`}
                  >
                    ${formatTrNumber(order.totalWholesaleUsd, 2)} ·{' '}
                    {formatTrNumber(order.totalWholesaleTry, 0)} TL
                  </div>
                </div>
              </div>

              <div
                className={`divide-y text-xs ${
                  isZincPortal ? 'divide-border' : 'divide-zinc-100'
                }`}
              >
                {order.lines.map((line) => (
                  <div
                    key={line.id}
                    className="py-2 flex flex-wrap items-center justify-between gap-2"
                  >
                    <span className={isZincPortal ? 'text-muted-foreground' : 'text-zinc-700'}>
                      <strong className={isZincPortal ? 'text-foreground' : 'text-foreground'}>
                        {line.qty}×
                      </strong>{' '}
                      <span
                        className={`font-mono ${isZincPortal ? 'text-muted-foreground' : 'text-zinc-500'}`}
                      >
                        {line.sku}
                      </span>{' '}
                      · {line.title} ({line.sizeUnitLabel} {line.size}) ·{' '}
                      {line.supplyType === 'STOCK' ? 'Hazır Stok' : 'Atölye Üretim'}
                      {line.dealerStampNote && ` · Damga: ${line.dealerStampNote}`}
                    </span>
                    <span
                      className={`font-mono tabular-nums ${
                        isZincPortal ? 'text-foreground' : 'text-foreground'
                      }`}
                    >
                      ${formatTrNumber(line.unitWholesaleUsd * line.qty, 2)} ·{' '}
                      {formatCurrencyValue(line.unitWholesaleTry * line.qty, 'TRY')}
                    </span>
                  </div>
                ))}
              </div>
              </>
            );
            return isZincPortal ? (
              <PortalDataCard key={order.orderNo} contentClassName="p-6 space-y-4">
                {b2bCard}
              </PortalDataCard>
            ) : (
              <article
                key={order.orderNo}
                className="bg-white border border-zinc-200 rounded-lg p-6 space-y-4"
              >
                {b2bCard}
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}

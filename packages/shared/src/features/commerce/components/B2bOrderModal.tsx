import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Building2,
  Check,
  ClipboardList,
  Copy,
  FileCheck2,
  Minus,
  Plus,
  Scale,
  Trash2,
} from 'lucide-react';
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Input,
  Separator,
} from '../../../components/ui';
import { PortalStat } from '../../../components/portal';
import { ConfirmDialog } from '../../../components/crud/ConfirmDialog';
import { useAuth } from '../../../providers/AuthProvider';
import { useActiveProductMetrics } from '../../catalog/hooks/useCatalogQueries';
import { formatTrNumber } from '../../../utils/pricingEngine';
import { b2bOrderSchema } from '../schemas/commerceSchema';
import {
  useB2bDraftQuery,
  useB2bOrdersQuery,
  useClearB2bDraftMutation,
  useCommerceUI,
  useRemoveB2bDraftLineMutation,
  useSubmitB2bOrderMutation,
  useUpdateB2bDraftLineMutation,
} from '../hooks/useCommerceQueries';
import type {
  B2bOrderRecord,
  B2bRateLockMode,
  B2bSettlementMethod,
} from '../types';

const SETTLEMENT_OPTIONS: Array<{
  value: B2bSettlementMethod;
  title: string;
  desc: string;
}> = [
  {
    value: 'HAS_PLUS_CURRENCY',
    title: 'Has Altın + İşçilik/Taş Dövizi',
    desc: 'Maden has gram (995/999) + işçilik/taş USD ayrı tahsil',
  },
  {
    value: 'FX_CASH',
    title: 'Döviz Nakit / Havale (USD)',
    desc: 'Maden + işçilik + taş tek kalem USD toptan bedel',
  },
  {
    value: 'CONSIGNMENT',
    title: 'Konsinye / Emanet',
    desc: 'Vade sonunda satılan faturalanır, kalan iade edilir',
  },
  {
    value: 'OPEN_ACCOUNT',
    title: 'Cari Hesap / Vadeli',
    desc: 'Bayinin tanımlı açık cari kredi limitinden düşülür',
  },
];

function settlementLabel(method: B2bSettlementMethod): string {
  return SETTLEMENT_OPTIONS.find((o) => o.value === method)?.title ?? method;
}

function buildProformaClipboardText(order: B2bOrderRecord): string {
  const linesText = order.lines
    .map(
      (l, i) =>
        `${i + 1}. ${l.sku} | ${l.title} (${l.purityCode} ${l.metalColor}, ${l.sizeUnitLabel} ${l.size}) | ${l.qty} adet | ${
          l.supplyType === 'STOCK' ? 'Stoktan' : 'Atölye Üretim'
        } | Toptan: $${formatTrNumber(l.unitWholesaleUsd * l.qty, 2)} / ${formatTrNumber(
          l.unitWholesaleTry * l.qty,
          2
        )}`
    )
    .join('\n');

  const settlementLine = `Hesaplaşma (${settlementLabel(order.settlementMethod)}): $${formatTrNumber(
    order.totalWholesaleUsd,
    2
  )} (${formatTrNumber(order.totalWholesaleTry, 0)} TL)`;

  return [
    `KUYUMPIM B2B PROFORMA / SİPARİŞ FİŞİ`,
    `Fiş No: ${order.orderNo}`,
    `Bayi: ${order.dealerName} (${order.dealerCode}) · Şube: ${order.branchName} · ${order.taxOfficeAndNo}`,
    `Yetkili: ${order.contactPerson} · Oluşturan: ${order.createdByUserName}`,
    `Kur Snapshot: ${order.snapshotId} (Has: ${formatTrNumber(order.goldRateTryPerGram, 2)} TL/gr, USD: ${formatTrNumber(order.usdTryRate, 2)} TL)`,
    `Kur Politikası: ${
      order.rateLockMode === 'LOCK_ON_ORDER'
        ? 'Sipariş anında sabitlendi'
        : 'Teslimat günü güncel kur/has ile kesinleşir'
    }`,
    `--------------------------------------------------`,
    linesText,
    `--------------------------------------------------`,
    `Toplam: ${order.totalPieces} adet · Brüt: ${formatTrNumber(order.totalGrossGram, 2)} gr · Toptan: $${formatTrNumber(order.totalWholesaleUsd, 2)}`,
    settlementLine,
    `Not: El işçiliği ve döküm kaynaklı ±%5 terazi gramaj farkı teslimat tartımında kesinleşir.`,
  ].join('\n');
}

export function B2bOrderModal() {
  const { user } = useAuth();
  const { b2bOrderOpen, setB2bOrderOpen } = useCommerceUI();
  const { rates } = useActiveProductMetrics();

  const draftQuery = useB2bDraftQuery();
  const ordersQuery = useB2bOrdersQuery();
  const updateLineMutation = useUpdateB2bDraftLineMutation();
  const removeLineMutation = useRemoveB2bDraftLineMutation();
  const clearDraftMutation = useClearB2bDraftMutation();
  const submitOrderMutation = useSubmitB2bOrderMutation();

  const [activeTab, setActiveTab] = useState<'draft' | 'history'>('draft');
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [confirmedOrder, setConfirmedOrder] = useState<B2bOrderRecord | null>(null);
  const [copiedProforma, setCopiedProforma] = useState(false);

  const dealer = draftQuery.data?.dealer;
  const lines = draftQuery.data?.lines ?? [];
  const orders = ordersQuery.data ?? [];

  const [dealerName, setDealerName] = useState(dealer?.companyName ?? '');
  const [taxOfficeAndNo, setTaxOfficeAndNo] = useState(dealer?.taxOfficeAndNo ?? '');
  const [contactPerson, setContactPerson] = useState(dealer?.contactName ?? '');
  const [settlementMethod, setSettlementMethod] =
    useState<B2bSettlementMethod>('HAS_PLUS_CURRENCY');
  const [rateLockMode, setRateLockMode] = useState<B2bRateLockMode>('LOCK_ON_ORDER');
  const [consignmentDays, setConsignmentDays] = useState(45);
  const [deliveryMethod, setDeliveryMethod] = useState<
    'BRINKS_INSURED' | 'KAPALICARSI_HANDOVER' | 'FACTORY_PICKUP'
  >('KAPALICARSI_HANDOVER');
  const [orderNote, setOrderNote] = useState('');
  const [acceptedWeightTolerance, setAcceptedWeightTolerance] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!dealer) return;
    setDealerName(dealer.companyName);
    setTaxOfficeAndNo(dealer.taxOfficeAndNo);
    setContactPerson(dealer.contactName);
    setConsignmentDays(dealer.defaultConsignmentDays);
  }, [dealer?.organizationId, dealer?.branchId]);

  const summary = useMemo(() => {
    const totalPieces = lines.reduce((s, l) => s + l.qty, 0);
    const stockPieces = lines
      .filter((l) => l.supplyType === 'STOCK')
      .reduce((s, l) => s + l.qty, 0);
    const productionPieces = totalPieces - stockPieces;
    const totalGrossGram = lines.reduce((s, l) => s + l.unitGrossGram * l.qty, 0);
    // Blind-pool: dealer API no longer returns fire/labor components.
    const totalHasGoldGram = lines.reduce(
      (s, l) => s + (l.unitFireIncludedFineGram ?? 0) * l.qty,
      0
    );
    const totalLaborAndStoneUsd = lines.reduce(
      (s, l) => s + (l.unitLaborAndStoneUsd ?? 0) * l.qty,
      0
    );
    const hasInternalBreakdown = lines.some((l) => l.unitFireIncludedFineGram != null);
    const totalWholesaleUsd = lines.reduce((s, l) => s + l.unitWholesaleUsd * l.qty, 0);
    const totalWholesaleTry = lines.reduce((s, l) => s + l.unitWholesaleTry * l.qty, 0);
    return {
      totalPieces,
      stockPieces,
      productionPieces,
      totalGrossGram,
      totalHasGoldGram,
      totalLaborAndStoneUsd,
      totalWholesaleUsd,
      totalWholesaleTry,
      hasInternalBreakdown,
    };
  }, [lines]);

  const remainingCreditUsd = dealer
    ? Math.max(0, dealer.creditLimitUsd - dealer.usedCreditUsd)
    : 50000;
  const remainingHasGram = dealer
    ? Math.max(0, dealer.hasLimitGram - dealer.usedHasGram)
    : 200;

  const creditExceeded =
    (settlementMethod === 'OPEN_ACCOUNT' || settlementMethod === 'CONSIGNMENT') &&
    summary.totalWholesaleUsd > remainingCreditUsd;
  const hasLimitExceeded =
    settlementMethod === 'HAS_PLUS_CURRENCY' &&
    (summary.hasInternalBreakdown
      ? summary.totalHasGoldGram > remainingHasGram ||
        summary.totalLaborAndStoneUsd > remainingCreditUsd
      : summary.totalWholesaleUsd > remainingCreditUsd);

  const handleCopyProforma = (order: B2bOrderRecord) => {
    navigator.clipboard?.writeText(buildProformaClipboardText(order)).catch(() => {});
    setCopiedProforma(true);
    window.setTimeout(() => setCopiedProforma(false), 2000);
  };

  const handleDownloadDraftPdf = async () => {
    const { apiDownloadBlob } = await import('../../../lib/api/client');
    await apiDownloadBlob('/api/v1/b2b/draft/proforma.pdf', 'taslak-proforma.pdf');
  };

  const handleDownloadOrderPdf = async (orderNo: string) => {
    const { apiDownloadBlob } = await import('../../../lib/api/client');
    await apiDownloadBlob(
      `/api/v1/b2b/orders/${encodeURIComponent(orderNo)}/proforma.pdf`,
      `${orderNo}-proforma.pdf`
    );
  };

  const handleSubmitB2bOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});
    setSubmitError(null);

    const parsed = b2bOrderSchema.safeParse({
      dealerName,
      taxOfficeAndNo,
      contactPerson,
      settlementMethod,
      rateLockMode,
      consignmentDays: settlementMethod === 'CONSIGNMENT' ? consignmentDays : undefined,
      deliveryMethod,
      orderNote,
      acceptedWeightTolerance,
    });

    if (!parsed.success) {
      const map: Record<string, string> = {};
      parsed.error.issues.forEach((issue) => {
        const key = String(issue.path[0] ?? 'form');
        if (!map[key]) map[key] = issue.message;
      });
      setFieldErrors(map);
      return;
    }

    try {
      const record = await submitOrderMutation.mutateAsync({
        snapshotId: rates.snapshotId,
        usdTryRate: rates.liveUsdSell,
        goldRateTryPerGram: rates.liveHasGoldTrySell,
        organizationId: dealer?.organizationId ?? 'org_aydin_kuyum',
        branchId: dealer?.branchId ?? '',
        branchName: dealer?.branchName ?? 'Merkez',
        createdByUserId: user.id,
        createdByUserName: user.fullName,
        dealerCode: dealer?.dealerCode ?? 'BY-34018',
        dealerName: parsed.data.dealerName,
        taxOfficeAndNo: parsed.data.taxOfficeAndNo,
        contactPerson: parsed.data.contactPerson,
        settlementMethod: parsed.data.settlementMethod,
        rateLockMode: parsed.data.rateLockMode,
        consignmentDays: parsed.data.consignmentDays,
        deliveryMethod: parsed.data.deliveryMethod,
        orderNote: parsed.data.orderNote ?? '',
        acceptedWeightTolerance: parsed.data.acceptedWeightTolerance,
        totalPieces: summary.totalPieces,
        totalGrossGram: Number(summary.totalGrossGram.toFixed(2)),
        totalHasGoldGram: Number(summary.totalHasGoldGram.toFixed(4)),
        totalLaborAndStoneUsd: Number(summary.totalLaborAndStoneUsd.toFixed(2)),
        totalWholesaleUsd: Number(summary.totalWholesaleUsd.toFixed(2)),
        totalWholesaleTry: Number(summary.totalWholesaleTry.toFixed(2)),
      });
      setConfirmedOrder(record);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'B2B sipariş fişi kaydedilemedi.');
    }
  };

  return (
    <>
      <Dialog
        open={b2bOrderOpen}
        onOpenChange={(open) => {
          if (!open) setConfirmedOrder(null);
          setB2bOrderOpen(open);
        }}
      >
        <DialogContent className="max-w-6xl">
          <DialogHeader className="px-6 py-4 border-b border-border flex flex-row items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-zinc-600" />
                <DialogTitle className="text-section">
                  B2B Bayi Toptan Sipariş Fişi & Proforma
                </DialogTitle>
              </div>
              <DialogDescription>
                Has altın + işçilik/taş dövizi hesaplaşması, asorti çoklu ölçü dağılımı ve stok / atölye üretim planlaması.
              </DialogDescription>
            </div>

            <div className="inline-flex rounded-md border border-border bg-muted/40 p-0.5 text-xs mr-8 shrink-0">
              <button
                type="button"
                onClick={() => {
                  setConfirmedOrder(null);
                  setActiveTab('draft');
                }}
                className={`px-3 py-1.5 rounded-[5px] font-medium transition-colors cursor-pointer ${
                  activeTab === 'draft'
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Aktif Fiş ({summary.totalPieces} adet)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('history')}
                className={`px-3 py-1.5 rounded-[5px] font-medium transition-colors cursor-pointer ${
                  activeTab === 'history'
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Bayi Sipariş Geçmişi ({orders.length})
              </button>
            </div>
          </DialogHeader>

          <div className="p-6 max-h-[78vh] overflow-y-auto space-y-5">
            {/* Dealer Account & Live Bullion Bar */}
            {dealer && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <PortalStat
                  label="Aktif Bayi Hesabı"
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
                  label="Kullanılabilir Cari Limit (USD)"
                  value={`$${formatTrNumber(remainingCreditUsd, 0)}`}
                  hint={`Toplam limit: $${formatTrNumber(dealer.creditLimitUsd, 0)}`}
                />
                <PortalStat
                  label="Kullanılabilir Has Altın Limiti"
                  value={`${formatTrNumber(remainingHasGram, 2)} gr Has`}
                  hint={`Açık has: ${formatTrNumber(dealer.usedHasGram, 2)} gr`}
                  valueClassName="text-muted-foreground"
                />
                <PortalStat
                  label="Canlı Kur & Has Snapshot"
                  value={`${formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr`}
                  hint={
                    <span className="font-mono">
                      USD: {formatTrNumber(rates.liveUsdSell, 2)} TL · {rates.snapshotId}
                    </span>
                  }
                />
              </div>
            )}

            {/* Confirmed B2B Proforma Receipt */}
            {confirmedOrder && activeTab === 'draft' ? (
              <div className="max-w-3xl mx-auto space-y-5 py-2">
                <div className="border border-success/30 bg-success/10 rounded-lg p-5 flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <FileCheck2 className="w-5 h-5 text-success mt-0.5 shrink-0" />
                    <div className="space-y-1">
                      <div className="text-sm font-semibold text-success">
                        B2B Sipariş Fişi Oluşturuldu · {confirmedOrder.orderNo}
                      </div>
                      <p className="text-xs text-success/80">
                        {confirmedOrder.totalPieces} adet ·{' '}
                        {formatTrNumber(confirmedOrder.totalGrossGram, 2)} gr brüt · $
                        {formatTrNumber(confirmedOrder.totalWholesaleUsd, 2)} toptan iş emrine aktarıldı.
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 shrink-0">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleDownloadOrderPdf(confirmedOrder.orderNo)}
                    >
                      PDF İndir
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleCopyProforma(confirmedOrder)}
                    >
                      {copiedProforma ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-success" />
                          Kopyalandı
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          Proforma Kopyala
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                <div className="border border-border rounded-lg divide-y divide-border text-xs bg-white">
                  <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div>
                      <div className="text-muted-foreground">Hesaplaşma Modeli</div>
                      <div className="font-semibold text-foreground mt-0.5">
                        {settlementLabel(confirmedOrder.settlementMethod)}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Kur Politikası</div>
                      <div className="font-medium text-foreground mt-0.5">
                        {confirmedOrder.rateLockMode === 'LOCK_ON_ORDER'
                          ? 'Sipariş Anı Sabitlendi'
                          : 'Teslimat Günü Kesinleşir'}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Toplam Toptan USD</div>
                      <div className="font-mono font-semibold text-zinc-600 mt-0.5 tabular-nums">
                        ${formatTrNumber(confirmedOrder.totalWholesaleUsd, 2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Toplam Toptan TRY</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5 tabular-nums">
                        {formatTrNumber(confirmedOrder.totalWholesaleTry, 0)} TL
                      </div>
                    </div>
                  </div>

                  <div className="p-4 space-y-2">
                    <div className="font-semibold text-foreground">Sipariş Kalemleri</div>
                    {confirmedOrder.lines.map((line) => (
                      <div
                        key={line.id}
                        className="flex flex-wrap justify-between gap-2 text-muted-foreground"
                      >
                        <span>
                          <strong className="text-foreground">{line.qty}×</strong> {line.sku} ·{' '}
                          {line.title} ({line.sizeUnitLabel} {line.size}) ·{' '}
                          {line.supplyType === 'STOCK' ? 'Stoktan' : 'Atölye Üretim'}
                        </span>
                        <span className="font-mono tabular-nums text-foreground">
                          ${formatTrNumber(line.unitWholesaleUsd * line.qty, 2)} ·{' '}
                          {formatTrNumber(line.unitWholesaleTry * line.qty, 0)} TL
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setConfirmedOrder(null);
                      setActiveTab('history');
                    }}
                  >
                    Bayi Sipariş Geçmişi
                  </Button>
                  <Button
                    onClick={() => {
                      setConfirmedOrder(null);
                      setB2bOrderOpen(false);
                    }}
                  >
                    Kapat
                  </Button>
                </div>
              </div>
            ) : activeTab === 'history' ? (
              /* Past B2B Orders History */
              <div className="space-y-4">
                {orders.map((order) => (
                  <div
                    key={order.orderNo}
                    className="border border-border rounded-lg p-4 bg-white space-y-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3 pb-2.5 border-b border-border/60">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2.5">
                          <span className="font-mono text-xs font-semibold text-foreground">
                            {order.orderNo}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {order.dealerName}
                          </span>
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          {new Date(order.createdAt).toLocaleString('tr-TR')} ·{' '}
                          {settlementLabel(order.settlementMethod)} ·{' '}
                          {order.rateLockMode === 'LOCK_ON_ORDER'
                            ? `Sabit Kur (${order.snapshotId})`
                            : 'Teslimat Günü Kur/Has'}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-right font-mono text-xs tabular-nums">
                          <>
                            <div className="font-semibold text-foreground">
                              ${formatTrNumber(order.totalWholesaleUsd, 2)}
                            </div>
                            <div className="text-muted-foreground">
                              {formatTrNumber(order.totalWholesaleTry, 0)} TL
                            </div>
                          </>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => void handleDownloadOrderPdf(order.orderNo)}
                        >
                          PDF
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleCopyProforma(order)}
                        >
                          <Copy className="w-3.5 h-3.5" />
                          Proforma
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-1 text-xs">
                      {order.lines.map((line) => (
                        <div
                          key={line.id}
                          className="flex flex-wrap justify-between gap-2 text-muted-foreground"
                        >
                          <span>
                            <strong className="text-foreground">{line.qty}×</strong> {line.sku} ·{' '}
                            {line.title} ({line.sizeUnitLabel} {line.size}) ·{' '}
                            <span className="text-foreground">
                              {line.supplyType === 'STOCK' ? 'Hazır Stok' : 'Atölye Üretim'}
                            </span>
                            {line.dealerStampNote && ` · Damga: ${line.dealerStampNote}`}
                          </span>
                          <span className="font-mono tabular-nums text-foreground">
                            {formatTrNumber(line.unitGrossGram * line.qty, 2)} gr brüt ·{' '}
                            ${formatTrNumber(line.unitWholesaleUsd * line.qty, 2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : lines.length === 0 ? (
              /* Empty B2B Draft */
              <div className="py-12 text-center space-y-3">
                <ClipboardList className="w-9 h-9 text-zinc-300 mx-auto" />
                <div className="text-sm font-medium text-foreground">
                  Aktif B2B sipariş fişinizde kalem bulunmuyor
                </div>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  Vitrin veya Ürün Kartı (B2B Bayi / ERP modunda) üzerinden tekli adet veya çoklu
                  ölçü asorti matrisi ekleyerek toptan sipariş fişi oluşturabilirsiniz.
                </p>
                <Button variant="outline" size="sm" onClick={() => setB2bOrderOpen(false)}>
                  Kataloğa Dön
                </Button>
              </div>
            ) : (
              /* Active B2B Order Draft + Settlement Panel */
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Left: Assortment Order Lines */}
                <div className="lg:col-span-7 space-y-4">
                  <div className="flex items-center justify-between text-xs">
                    <div className="text-muted-foreground">
                      <strong className="text-foreground">{lines.length}</strong> satır ·{' '}
                      <strong className="text-foreground">{summary.totalPieces}</strong> adet (
                      {summary.stockPieces} stoktan, {summary.productionPieces} atölye üretim)
                    </div>
                    <button
                      type="button"
                      onClick={() => setClearConfirmOpen(true)}
                      className="text-red-700 hover:underline cursor-pointer"
                    >
                      Fişi Temizle
                    </button>
                  </div>

                  <div className="space-y-3">
                    {lines.map((line) => (
                      <div
                        key={line.id}
                        className="border border-border rounded-lg p-4 bg-white space-y-3"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="font-mono text-[11px] text-muted-foreground">
                              {line.sku} · {line.purityCode} {line.metalColor} · {line.sizeUnitLabel}{' '}
                              <strong className="text-foreground">{line.size}</strong>
                            </div>
                            <div className="text-base font-semibold text-foreground">
                              {line.title}
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <div className="inline-flex items-center border border-border rounded-md overflow-hidden">
                              <button
                                type="button"
                                aria-label="Adet azalt"
                                onClick={() =>
                                  line.qty <= 1
                                    ? removeLineMutation.mutate(line.id)
                                    : updateLineMutation.mutate({
                                        id: line.id,
                                        patch: { qty: line.qty - 1 },
                                      })
                                }
                                className="px-2 py-1 hover:bg-muted cursor-pointer"
                              >
                                <Minus className="w-3 h-3" />
                              </button>
                              <input
                                type="number"
                                min={1}
                                max={500}
                                value={line.qty}
                                onChange={(e) =>
                                  updateLineMutation.mutate({
                                    id: line.id,
                                    patch: { qty: Math.max(1, Number(e.target.value) || 1) },
                                  })
                                }
                                className="w-12 text-center text-xs font-mono tabular-nums py-1 focus:outline-none"
                              />
                              <button
                                type="button"
                                aria-label="Adet artır"
                                onClick={() =>
                                  updateLineMutation.mutate({
                                    id: line.id,
                                    patch: { qty: line.qty + 1 },
                                  })
                                }
                                className="px-2 py-1 hover:bg-muted cursor-pointer"
                              >
                                <Plus className="w-3 h-3" />
                              </button>
                            </div>
                            <button
                              type="button"
                              aria-label="Satırı sil"
                              data-delete="true"
                              onClick={() => removeLineMutation.mutate(line.id)}
                              className="p-1.5 text-destructive hover:bg-destructive/10 cursor-pointer rounded-md"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>

                        {/* Line weight + wholesale (blind-pool: no fire/labor internals) */}
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 bg-zinc-50 rounded-md p-2.5 text-[11px] font-mono tabular-nums">
                          <div>
                            <div className="text-muted-foreground font-sans">Brüt Ağırlık</div>
                            <div className="font-semibold text-foreground mt-0.5">
                              {formatTrNumber(line.unitGrossGram * line.qty, 2)} gr
                            </div>
                          </div>
                          <div>
                            <div className="text-muted-foreground font-sans">Toptan USD</div>
                            <div className="font-semibold text-foreground mt-0.5">
                              ${formatTrNumber(line.unitWholesaleUsd * line.qty, 2)}
                            </div>
                          </div>
                          <div>
                            <div className="text-muted-foreground font-sans">Toptan TRY</div>
                            <div className="font-semibold text-foreground mt-0.5">
                              {formatTrNumber(line.unitWholesaleTry * line.qty, 0)} TL
                            </div>
                          </div>
                        </div>

                        {/* Supply Type & Dealer Stamp Note */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                          <div className="inline-flex rounded-md border border-border p-0.5 bg-zinc-50">
                            <button
                              type="button"
                              onClick={() =>
                                updateLineMutation.mutate({
                                  id: line.id,
                                  patch: { supplyType: 'STOCK' },
                                })
                              }
                              className={`flex-1 py-1 px-2 rounded-[4px] text-[11px] font-medium transition-colors cursor-pointer ${
                                line.supplyType === 'STOCK'
                                  ? 'bg-foreground text-background'
                                  : 'text-muted-foreground hover:text-foreground'
                              }`}
                            >
                              Hazır Stoktan Ayır
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                updateLineMutation.mutate({
                                  id: line.id,
                                  patch: { supplyType: 'PRODUCTION' },
                                })
                              }
                              className={`flex-1 py-1 px-2 rounded-[4px] text-[11px] font-medium transition-colors cursor-pointer ${
                                line.supplyType === 'PRODUCTION'
                                  ? 'bg-foreground text-background'
                                  : 'text-muted-foreground hover:text-foreground'
                              }`}
                            >
                              Atölye Üretim (5–7 gün)
                            </button>
                          </div>

                          <Input
                            type="text"
                            maxLength={60}
                            value={line.dealerStampNote}
                            onChange={(e) =>
                              updateLineMutation.mutate({
                                id: line.id,
                                patch: { dealerStampNote: e.target.value },
                              })
                            }
                            placeholder="Bayi damgası / lazer marka notu..."
                            className="h-8 text-xs"
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Totals Strip */}
                  <div className="border border-border rounded-lg p-4 bg-zinc-50/70 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div>
                      <div className="text-muted-foreground">Toplam Adet / Brüt</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5 tabular-nums">
                        {summary.totalPieces} ad · {formatTrNumber(summary.totalGrossGram, 2)} gr
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Toplam Toptan USD</div>
                      <div className="font-mono font-semibold text-zinc-600 mt-0.5 tabular-nums">
                        ${formatTrNumber(summary.totalWholesaleUsd, 2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Toplam Toptan TRY</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5 tabular-nums">
                        {formatTrNumber(summary.totalWholesaleTry, 0)} TL
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Kalem Sayısı</div>
                      <div className="font-mono font-semibold text-foreground mt-0.5 tabular-nums">
                        {summary.stockPieces} stok / {summary.productionPieces} üretim
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right: Settlement Model, Rate Lock & Confirmation Form */}
                <form
                  onSubmit={handleSubmitB2bOrder}
                  className="lg:col-span-5 border border-border rounded-lg p-5 bg-zinc-50/60 space-y-4"
                >
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-foreground">
                      1. Kuyumculuk Hesaplaşma Modeli
                    </div>
                    <div className="space-y-1.5">
                      {SETTLEMENT_OPTIONS.map((opt) => {
                        const active = settlementMethod === opt.value;
                        return (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => setSettlementMethod(opt.value)}
                            className={`w-full text-left p-2.5 rounded-md border transition-colors cursor-pointer ${
                              active
                                ? 'border-foreground bg-white'
                                : 'border-border bg-transparent hover:bg-white'
                            }`}
                          >
                            <div className="text-xs font-semibold text-foreground">{opt.title}</div>
                            <div className="text-[11px] text-muted-foreground mt-0.5">
                              {opt.desc}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Active Settlement Summary Callout */}
                  <div className="border border-zinc-200 bg-white rounded-md p-3.5 space-y-1.5 text-xs">
                    <div className="text-[11px] font-medium text-muted-foreground">
                      Seçili Hesaplaşma Özeti
                    </div>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-mono text-base font-semibold text-foreground tabular-nums">
                        ${formatTrNumber(summary.totalWholesaleUsd, 2)} USD
                      </span>
                      <span className="font-mono text-xs text-muted-foreground tabular-nums">
                        ≈ {formatTrNumber(summary.totalWholesaleTry, 0)} TL
                      </span>
                    </div>
                    {settlementMethod === 'CONSIGNMENT' && (
                      <div className="pt-2 flex items-center justify-between gap-2 text-[11px]">
                        <span className="text-muted-foreground">Konsinye / Emanet Vadesi:</span>
                        <div className="inline-flex gap-1">
                          {[30, 45, 60].map((d) => (
                            <button
                              key={d}
                              type="button"
                              onClick={() => setConsignmentDays(d)}
                              className={`px-2 py-0.5 rounded border font-mono cursor-pointer ${
                                consignmentDays === d
                                  ? 'border-foreground bg-foreground text-background'
                                  : 'border-border text-foreground'
                              }`}
                            >
                              {d} gün
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {(creditExceeded || hasLimitExceeded) && (
                    <div className="border border-warning/40 bg-warning/10 rounded-md p-2.5 text-[11px] text-foreground flex items-start gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-warning shrink-0 mt-0.5" />
                      <span>
                        Sipariş tutarı bayinin kalan limitini aşıyor. Fiş yine de{' '}
                        <strong>Finans Onayı Bekliyor</strong> notuyla kaydedilebilir.
                      </span>
                    </div>
                  )}

                  {/* Rate Lock Policy */}
                  <div className="space-y-1.5 text-xs">
                    <div className="font-semibold text-foreground">
                      2. Kur & Has Altın Sabitleme Politikası
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setRateLockMode('LOCK_ON_ORDER')}
                        className={`p-2 rounded-md border text-left text-[11px] cursor-pointer ${
                          rateLockMode === 'LOCK_ON_ORDER'
                            ? 'border-foreground bg-white font-medium text-foreground'
                            : 'border-border text-muted-foreground hover:bg-white'
                        }`}
                      >
                        Sipariş Anı Sabitle
                        <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                          {rates.snapshotId}
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={() => setRateLockMode('SETTLE_ON_DELIVERY')}
                        className={`p-2 rounded-md border text-left text-[11px] cursor-pointer ${
                          rateLockMode === 'SETTLE_ON_DELIVERY'
                            ? 'border-foreground bg-white font-medium text-foreground'
                            : 'border-border text-muted-foreground hover:bg-white'
                        }`}
                      >
                        Teslimat Günü Kesinleştir
                        <div className="text-[10px] text-muted-foreground mt-0.5">
                          Sevk anı güncel has/kur
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* Delivery & Dealer Info */}
                  <div className="space-y-2.5 text-xs">
                    <div className="font-semibold text-foreground">3. Teslimat & Bayi Bilgisi</div>
                    <select
                      value={deliveryMethod}
                      onChange={(e) =>
                        setDeliveryMethod(
                          e.target.value as
                            | 'BRINKS_INSURED'
                            | 'KAPALICARSI_HANDOVER'
                            | 'FACTORY_PICKUP'
                        )
                      }
                      className="w-full h-8 px-2.5 rounded-md border border-input bg-white text-xs"
                    >
                      <option value="KAPALICARSI_HANDOVER">
                        Kapalıçarşı / Kuyumcukent Elden Teslimat
                      </option>
                      <option value="BRINKS_INSURED">
                        Brinks / Loomis Sigortalı Bayi Kuryesi
                      </option>
                      <option value="FACTORY_PICKUP">Atölyeden Bizzat Teslim Alma</option>
                    </select>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[11px] text-muted-foreground">Bayi Unvanı *</label>
                        <Input
                          type="text"
                          value={dealerName}
                          onChange={(e) => setDealerName(e.target.value)}
                          className="h-8 mt-0.5 text-xs"
                        />
                        {fieldErrors.dealerName && (
                          <p className="text-[11px] text-destructive mt-0.5">
                            {fieldErrors.dealerName}
                          </p>
                        )}
                      </div>
                      <div>
                        <label className="text-[11px] text-muted-foreground">
                          Sipariş Yetkilisi *
                        </label>
                        <Input
                          type="text"
                          value={contactPerson}
                          onChange={(e) => setContactPerson(e.target.value)}
                          className="h-8 mt-0.5 text-xs"
                        />
                        {fieldErrors.contactPerson && (
                          <p className="text-[11px] text-destructive mt-0.5">
                            {fieldErrors.contactPerson}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[11px] text-muted-foreground">
                          Vergi Dairesi / VKN *
                        </label>
                        <Input
                          type="text"
                          value={taxOfficeAndNo}
                          onChange={(e) => setTaxOfficeAndNo(e.target.value)}
                          className="h-8 mt-0.5 text-xs"
                        />
                        {fieldErrors.taxOfficeAndNo && (
                          <p className="text-[11px] text-destructive mt-0.5">
                            {fieldErrors.taxOfficeAndNo}
                          </p>
                        )}
                      </div>
                      <div>
                        <label className="text-[11px] text-muted-foreground">
                          Atölye / Sevk Notu
                        </label>
                        <Input
                          type="text"
                          value={orderNote}
                          onChange={(e) => setOrderNote(e.target.value)}
                          placeholder="Damga, paketleme, sertifika..."
                          className="h-8 mt-0.5 text-xs"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Jewelry ±5% Weight Tolerance Consent */}
                  <div className="border border-zinc-200 bg-white rounded-md p-3 text-[11px] text-muted-foreground space-y-1.5">
                    <div className="flex items-start gap-2">
                      <Scale className="w-3.5 h-3.5 text-zinc-600 shrink-0 mt-0.5" />
                      <span>
                        Kuyumculuk üretim standardı gereği döküm ve cila kaynaklı{' '}
                        <strong className="text-foreground">±%5 terazi gramaj farkı</strong>{' '}
                        teslimat anındaki gerçek tartım üzerinden kesin faturaya yansıtılır.
                      </span>
                    </div>
                    <label className="flex items-center gap-2 text-foreground font-medium cursor-pointer">
                      <input
                        type="checkbox"
                        checked={acceptedWeightTolerance}
                        onChange={(e) => setAcceptedWeightTolerance(e.target.checked)}
                      />
                      ±%5 gramaj tolerans ve tartım koşulunu kabul ediyorum.
                    </label>
                    {fieldErrors.acceptedWeightTolerance && (
                      <p className="text-destructive font-medium">
                        {fieldErrors.acceptedWeightTolerance}
                      </p>
                    )}
                  </div>

                  {submitError && (
                    <p className="text-xs text-destructive font-medium">{submitError}</p>
                  )}

                  <Separator />

                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => void handleDownloadDraftPdf()}
                    disabled={lines.length === 0}
                  >
                    Taslak Proforma PDF İndir
                  </Button>

                  <Button
                    type="submit"
                    className="w-full"
                    size="lg"
                    disabled={submitOrderMutation.isPending}
                  >
                    {submitOrderMutation.isPending
                      ? 'Proforma Oluşturuluyor...'
                      : `B2B Sipariş Fişini Onayla (${summary.totalPieces} Adet)`}
                  </Button>
                </form>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={clearConfirmOpen}
        onOpenChange={setClearConfirmOpen}
        variant="destructive"
        isLoading={clearDraftMutation.isPending}
        title="B2B sipariş fişini temizle"
        description="Aktif sipariş fişindeki tüm asorti kalemleri ve damga notları kaldırılacak."
        confirmLabel="Fişi Temizle"
        cancelLabel="Vazgeç"
        onConfirm={async () => {
          await clearDraftMutation.mutateAsync();
          setClearConfirmOpen(false);
        }}
      />
    </>
  );
}

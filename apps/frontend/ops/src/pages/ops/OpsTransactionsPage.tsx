import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Input,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { apiFetch } from '@taragold/shared/lib/api/client';

type Tx = {
  id: string;
  orderNo: string;
  orderStatus: string;
  provider: string;
  status: string;
  paymentId: string;
  conversationId: string;
  paidPrice: string;
  refundedAmount: string;
  refundableAmount: string;
  currency: string;
  installment: number;
  lastFourDigits: string;
  cardFamily?: string;
  transferReference?: string;
  bankName?: string;
  iban?: string;
  receiptStatus?: string;
  receiptUrl?: string | null;
  errorMessage: string;
  itemTransactions: Array<{ paymentTransactionId?: string }>;
  createdAt: string;
};

type RefundReq = {
  id: string;
  orderNo: string;
  kind: string;
  status: string;
  requestedAmount: string | null;
  reason: string;
  createdAt: string;
};

const STATUS_LABEL: Record<string, string> = {
  SUCCESS: 'Başarılı',
  FAILURE: 'Başarısız',
  CANCELLED: 'İptal Edildi',
  PARTIAL_REFUNDED: 'Kısmi İade',
  REFUNDED: 'Tam İade',
  INIT: 'Başlatıldı',
  REDIRECTED: 'Yönlendirildi',
  PENDING: 'Bekliyor',
};

export function OpsTransactionsPage() {
  const [rows, setRows] = useState<Tx[]>([]);
  const [requests, setRequests] = useState<RefundReq[]>([]);
  const [status, setStatus] = useState('');
  const [provider, setProvider] = useState('');
  const [orderNo, setOrderNo] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refundTxId, setRefundTxId] = useState<string | null>(null);
  const [refundAmount, setRefundAmount] = useState('');
  const [itemTxId, setItemTxId] = useState('');
  const [refundIban, setRefundIban] = useState('');
  const [refundHolder, setRefundHolder] = useState('');
  const [refundReceipt, setRefundReceipt] = useState<File | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (status) qs.set('status', status);
      if (provider) qs.set('provider', provider);
      if (orderNo) qs.set('orderNo', orderNo);
      const [txRes, reqRes] = await Promise.all([
        apiFetch<Tx[]>(`/api/v1/ops/payments/transactions?${qs.toString()}`),
        apiFetch<RefundReq[]>('/api/v1/ops/payments/refund-requests?status=PENDING'),
      ]);
      setRows(txRes.data ?? []);
      setRequests(reqRes.data ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Liste alınamadı');
    } finally {
      setLoading(false);
    }
  }, [status, provider, orderNo]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCancel = async (id: string) => {
    if (!window.confirm('Gün içi iptal (iyzico Cancel) gönderilsin mi? Onay gelmeden durum güncellenmez.')) {
      return;
    }
    setError(null);
    try {
      await apiFetch(`/api/v1/ops/payments/transactions/${id}/cancel`, { method: 'POST' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'İptal başarısız');
    }
  };

  const onRefund = async () => {
    if (!refundTxId) return;
    setError(null);
    const row = rows.find((r) => r.id === refundTxId);
    try {
      if (row?.provider === 'BANK_TRANSFER') {
        if (refundReceipt) {
          const form = new FormData();
          if (refundAmount) form.append('amount', refundAmount);
          if (refundIban.trim()) form.append('refundIban', refundIban.trim());
          if (refundHolder.trim()) form.append('refundAccountHolder', refundHolder.trim());
          form.append('receipt_file', refundReceipt);
          await apiFetch(`/api/v1/ops/payments/transactions/${refundTxId}/manual-refund`, {
            method: 'POST',
            body: form,
          });
        } else {
          await apiFetch(`/api/v1/ops/payments/transactions/${refundTxId}/manual-refund`, {
            method: 'POST',
            body: {
              amount: refundAmount || undefined,
              refundIban: refundIban.trim() || undefined,
              refundAccountHolder: refundHolder.trim() || undefined,
            },
          });
        }
      } else {
        await apiFetch(`/api/v1/ops/payments/transactions/${refundTxId}/refund`, {
          method: 'POST',
          body: {
            amount: refundAmount || undefined,
            paymentTransactionId: itemTxId || undefined,
          },
        });
      }
      setRefundTxId(null);
      setRefundAmount('');
      setItemTxId('');
      setRefundIban('');
      setRefundHolder('');
      setRefundReceipt(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'İade başarısız');
    }
  };

  const onApproveTransfer = async (id: string) => {
    if (!window.confirm('Havale ödemesini onaylayıp siparişi ilerletsin mi?')) return;
    setError(null);
    try {
      await apiFetch(`/api/v1/ops/payments/transactions/${id}/approve-transfer`, { method: 'POST' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Onay başarısız');
    }
  };

  const onRejectTransfer = async (id: string) => {
    const reason = window.prompt('Red gerekçesi (opsiyonel)') || '';
    setError(null);
    try {
      await apiFetch(`/api/v1/ops/payments/transactions/${id}/reject-transfer`, {
        method: 'POST',
        body: { reason },
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Red başarısız');
    }
  };

  const onRequestAction = async (id: string, action: 'APPROVE' | 'REJECT', useCancel = false) => {
    const adminNote = window.prompt('Yönetici notu (opsiyonel)') ?? '';
    setError(null);
    try {
      await apiFetch(`/api/v1/ops/payments/refund-requests/${id}/action`, {
        method: 'POST',
        body: { action, useCancel, adminNote: adminNote.trim() || undefined },
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Talep işlenemedi');
    }
  };

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Ödeme Operasyonu"
        title="Ödeme İşlemleri"
        description="iyzico işlem durumu, iptal / iade aksiyonları ve B2C iade talepleri."
      />

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      )}

      <PortalDataCard title="Filtreler" contentClassName="p-4 grid grid-cols-1 sm:flex sm:flex-wrap gap-3 sm:items-end">
        <div className="space-y-1 w-full sm:w-auto">
          <Label>Durum</Label>
          <select
            className="flex min-h-11 h-11 w-full sm:w-auto md:min-h-10 md:h-10 rounded-md border border-input bg-background px-3 text-base md:text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Tümü</option>
            {Object.keys(STATUS_LABEL).map((k) => (
              <option key={k} value={k}>
                {STATUS_LABEL[k]}
              </option>
            ))}
            <option value="PENDING">Havale Bekliyor</option>
            <option value="RECEIPT_UPLOADED">Dekont Yüklendi</option>
          </select>
        </div>
        <div className="space-y-1 w-full sm:w-auto">
          <Label>Yöntem</Label>
          <select
            className="flex min-h-11 h-11 w-full sm:w-auto md:min-h-10 md:h-10 rounded-md border border-input bg-background px-3 text-base md:text-sm"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="">Tümü</option>
            <option value="IYZICO">Kredi Kartı</option>
            <option value="BANK_TRANSFER">Havale / EFT</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label>Sipariş No</Label>
          <Input value={orderNo} onChange={(e) => setOrderNo(e.target.value)} placeholder="TG-…" />
        </div>
        <Button type="button" variant="outline" onClick={() => void load()}>
          <RefreshCw className="w-4 h-4" />
          Yenile
        </Button>
      </PortalDataCard>

      {requests.length > 0 && (
        <PortalDataCard title="Bekleyen İade / İptal Talepleri" contentClassName="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sipariş</TableHead>
                <TableHead>Tür</TableHead>
                <TableHead>Tutar</TableHead>
                <TableHead>Sebep</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {requests.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.orderNo}</TableCell>
                  <TableCell>{r.kind}</TableCell>
                  <TableCell className="font-mono">{r.requestedAmount ?? '—'}</TableCell>
                  <TableCell className="max-w-[240px] truncate text-xs">{r.reason || '—'}</TableCell>
                  <TableCell className="space-x-2 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void onRequestAction(r.id, 'APPROVE', r.kind === 'CANCEL')}
                    >
                      Onayla
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => void onRequestAction(r.id, 'REJECT')}>
                      Reddet
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </PortalDataCard>
      )}

      {/* Mobile card list */}
      <div className="md:hidden space-y-3">
        {rows.map((t) => (
          <PortalDataCard
            key={t.id}
            title={t.orderNo}
            contentClassName="p-4 space-y-3 text-xs"
          >
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{t.provider === 'BANK_TRANSFER' ? 'Havale' : 'Kart'}</Badge>
              <Badge variant="outline">{STATUS_LABEL[t.status] ?? t.status}</Badge>
            </div>
            <div className="font-mono tabular-nums text-sm">
              {t.paidPrice} {t.currency}
            </div>
            <div className="text-muted-foreground">
              {t.provider === 'BANK_TRANSFER'
                ? `${t.bankName || '—'} · ${t.transferReference || ''}`
                : `${t.lastFourDigits ? `****${t.lastFourDigits}` : '—'}${
                    t.installment > 1 ? ` · ${t.installment}T` : ''
                  }`}
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              {t.provider === 'BANK_TRANSFER' &&
                (t.status === 'PENDING' || t.status === 'RECEIPT_UPLOADED') && (
                  <>
                    <Button size="sm" className="min-h-11" onClick={() => void onApproveTransfer(t.id)}>
                      Havale Onayla
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="min-h-11"
                      onClick={() => void onRejectTransfer(t.id)}
                    >
                      Reddet
                    </Button>
                  </>
                )}
              {t.provider === 'IYZICO' && t.status === 'SUCCESS' && (
                <>
                  <Button size="sm" variant="outline" className="min-h-11" onClick={() => void onCancel(t.id)}>
                    İptal
                  </Button>
                  <Button
                    size="sm"
                    className="min-h-11"
                    onClick={() => {
                      setRefundTxId(t.id);
                      setRefundAmount(t.refundableAmount);
                      setItemTxId(t.itemTransactions?.[0]?.paymentTransactionId || '');
                    }}
                  >
                    İade
                  </Button>
                </>
              )}
            </div>
          </PortalDataCard>
        ))}
        {!loading && rows.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-8">Kayıt yok</p>
        )}
      </div>

      <PortalDataCard
        title={`İşlemler${loading ? '…' : ` (${rows.length})`}`}
        className="hidden md:block"
        contentClassName="p-0 overflow-x-auto"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Sipariş</TableHead>
              <TableHead>Yöntem</TableHead>
              <TableHead>Durum</TableHead>
              <TableHead>Ödenen</TableHead>
              <TableHead>Detay</TableHead>
              <TableHead>Referans</TableHead>
              <TableHead>Tarih</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((t) => (
              <TableRow key={t.id}>
                <TableCell className="font-mono text-xs">{t.orderNo}</TableCell>
                <TableCell className="text-xs">
                  {t.provider === 'BANK_TRANSFER' ? 'Havale' : 'Kart'}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{STATUS_LABEL[t.status] ?? t.status}</Badge>
                  {t.receiptStatus && t.receiptStatus !== 'NONE' ? (
                    <div className="text-[11px] text-muted-foreground mt-1">Dekont: {t.receiptStatus}</div>
                  ) : null}
                  {t.errorMessage ? (
                    <div className="text-[11px] text-red-600 mt-1 max-w-[160px] truncate">{t.errorMessage}</div>
                  ) : null}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {t.paidPrice} {t.currency}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {t.provider === 'BANK_TRANSFER'
                    ? t.bankName || '—'
                    : `${t.lastFourDigits ? `****${t.lastFourDigits}` : '—'}${
                        t.installment > 1 ? ` · ${t.installment}T` : ''
                      }${t.cardFamily ? ` · ${t.cardFamily}` : ''}`}
                </TableCell>
                <TableCell className="font-mono text-[11px]">
                  {t.transferReference || t.paymentId || '—'}
                </TableCell>
                <TableCell className="text-xs">{new Date(t.createdAt).toLocaleString('tr-TR')}</TableCell>
                <TableCell className="text-right space-x-1 whitespace-nowrap">
                  {t.provider === 'BANK_TRANSFER' &&
                    (t.status === 'PENDING' || t.status === 'RECEIPT_UPLOADED') && (
                      <>
                        {t.receiptUrl ? (
                          <a
                            href={t.receiptUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex h-8 items-center rounded-md px-2 text-xs underline"
                          >
                            Dekont
                          </a>
                        ) : null}
                        <Button size="sm" onClick={() => void onApproveTransfer(t.id)}>
                          Havale Onayla
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => void onRejectTransfer(t.id)}>
                          Reddet
                        </Button>
                      </>
                    )}
                  {t.provider === 'IYZICO' && t.status === 'SUCCESS' && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => void onCancel(t.id)}>
                        İptal
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          setRefundTxId(t.id);
                          setRefundAmount(t.refundableAmount);
                          const first = t.itemTransactions?.[0]?.paymentTransactionId || '';
                          setItemTxId(first);
                        }}
                      >
                        İade
                      </Button>
                    </>
                  )}
                  {t.provider === 'BANK_TRANSFER' && t.status === 'SUCCESS' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setRefundTxId(t.id);
                        setRefundAmount(t.refundableAmount);
                      }}
                    >
                      Manuel İade
                    </Button>
                  )}
                  {t.status === 'PARTIAL_REFUNDED' && t.provider === 'IYZICO' && (
                    <Button
                      size="sm"
                      onClick={() => {
                        setRefundTxId(t.id);
                        setRefundAmount(t.refundableAmount);
                        const first = t.itemTransactions?.[0]?.paymentTransactionId || '';
                        setItemTxId(first);
                      }}
                    >
                      Kısmi İade
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!loading && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-sm text-muted-foreground py-8">
                  Kayıt yok
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </PortalDataCard>

      {refundTxId && (() => {
        const activeRow = rows.find((r) => r.id === refundTxId);
        const isBank = activeRow?.provider === 'BANK_TRANSFER';
        return (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4">
          <div className="bg-card border border-border rounded-t-xl sm:rounded-lg shadow-lg w-full max-w-md p-5 sm:p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold">
              {isBank ? 'Manuel Havale İadesi' : 'Tam / Kısmi İade'}
            </h3>
            <p className="text-xs text-muted-foreground">
              {isBank
                ? 'Banka havalesi iadesi için tutar, iade IBAN, hesap sahibi ve opsiyonel iade dekontu girebilirsiniz.'
                : 'iyzico Refund API onayı gelmeden veritabanı güncellenmez. Kırılımlı iade için paymentTransactionId gerekir.'}
            </p>
            <div className="space-y-1.5">
              <Label>Tutar</Label>
              <Input value={refundAmount} onChange={(e) => setRefundAmount(e.target.value)} />
            </div>
            {isBank ? (
              <>
                <div className="space-y-1.5">
                  <Label>İade IBAN</Label>
                  <Input value={refundIban} onChange={(e) => setRefundIban(e.target.value)} placeholder="TR..." />
                </div>
                <div className="space-y-1.5">
                  <Label>Hesap Sahibi</Label>
                  <Input value={refundHolder} onChange={(e) => setRefundHolder(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>İade Dekontu (Opsiyonel)</Label>
                  <Input
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={(e) => setRefundReceipt(e.target.files?.[0] ?? null)}
                  />
                </div>
              </>
            ) : (
              <div className="space-y-1.5">
                <Label>paymentTransactionId</Label>
                <Input value={itemTxId} onChange={(e) => setItemTxId(e.target.value)} />
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setRefundTxId(null)}>
                Vazgeç
              </Button>
              <Button type="button" onClick={() => void onRefund()}>
                İade Gönder
              </Button>
            </div>
          </div>
        </div>
        );
      })()}
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { toast } from 'sonner';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import {
  useCreateOpsLedgerMutation,
  useOpsLedgerQuery,
  useOpsOrganizationsQuery,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';
import { ApiClientError } from '@taragold/shared/lib/api/client';

const ENTRY_LABELS: Record<string, string> = {
  PAYMENT_CREDIT: 'Tahsilat (USD)',
  HAS_DELIVERY: 'Has Teslimat',
  ORDER_REVERSAL: 'Sipariş Ters Kayıt',
  REFUND_CREDIT: 'İade Kredisi',
};

export function OpsFinancePage() {
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [entryType, setEntryType] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [postOpen, setPostOpen] = useState(false);
  const [organizationId, setOrganizationId] = useState('');
  const [postEntryType, setPostEntryType] = useState<'PAYMENT_CREDIT' | 'HAS_DELIVERY'>('PAYMENT_CREDIT');
  const [referenceNo, setReferenceNo] = useState('');
  const [amountUsd, setAmountUsd] = useState('');
  const [hasGoldGram, setHasGoldGram] = useState('');
  const [note, setNote] = useState('');

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedQ(q.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(t);
  }, [q]);

  const ledgerQuery = useOpsLedgerQuery({
    q: debouncedQ || undefined,
    entryType: entryType === 'all' ? undefined : entryType,
    page,
    pageSize: 40,
  });
  const orgsQuery = useOpsOrganizationsQuery({ pageSize: 200, isActive: true });
  const createLedgerMut = useCreateOpsLedgerMutation();

  const rows = ledgerQuery.data?.items ?? [];
  const pagination = ledgerQuery.data?.pagination;
  const orgs = orgsQuery.data?.items ?? [];

  const onPostLedger = async () => {
    try {
      await createLedgerMut.mutateAsync({
        organizationId,
        entryType: postEntryType,
        referenceNo: referenceNo.trim(),
        amountUsd: amountUsd || '0',
        hasGoldGram: hasGoldGram || '0',
        note: note.trim(),
      });
      toast.success('Cari hareket kaydedildi');
      setPostOpen(false);
      setReferenceNo('');
      setAmountUsd('');
      setHasGoldGram('');
      setNote('');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Kayıt başarısız');
    }
  };

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Bayi Cari Defter & Has Altın Hareketleri"
        title={`Cari Hesap${pagination ? ` (${pagination.total})` : ''}`}
        actions={
          <>
            <Select
              value={entryType}
              onValueChange={(v) => {
                setEntryType(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="h-9 w-44 text-xs">
                <SelectValue placeholder="Kayıt tipi" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm kayıtlar</SelectItem>
                {Object.entries(ENTRY_LABELS).map(([val, label]) => (
                  <SelectItem key={val} value={val}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Bayi veya referans ara..."
                className="h-9 pl-8 w-52 text-xs"
              />
            </div>
            <Button size="sm" variant="success" onClick={() => setPostOpen(true)}>
              <Plus className="w-3.5 h-3.5" />
              Tahsilat / Has
            </Button>
          </>
        }
      />

      <PortalDataCard>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Tarih</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Bayi</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Tip</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Referans</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">USD</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Has (gr)</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Not</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ledgerQuery.isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                  Yükleniyor...
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                  Cari kayıt bulunamadı.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="px-4 font-mono text-muted-foreground">
                    {new Date(row.createdAt).toLocaleString('tr-TR')}
                  </TableCell>
                  <TableCell className="px-4">
                    <div className="font-medium">{row.organizationName}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">{row.organizationCode}</div>
                  </TableCell>
                  <TableCell className="px-4 text-muted-foreground">
                    {ENTRY_LABELS[row.entryType] ?? row.entryType}
                  </TableCell>
                  <TableCell className="px-4 font-mono">{row.referenceNo}</TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums">
                    ${formatTrNumber(Number(row.amountUsd), 2)}
                  </TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums">
                    {formatTrNumber(Number(row.hasGoldGram), 4)}
                  </TableCell>
                  <TableCell className="px-4 text-muted-foreground max-w-[200px] truncate">
                    {row.note || '—'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </PortalDataCard>

      {pagination && pagination.totalPages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-xs">
          <Button type="button" size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Önceki
          </Button>
          <span className="text-muted-foreground font-mono tabular-nums">
            {pagination.page} / {pagination.totalPages}
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page >= pagination.totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Sonraki
          </Button>
        </div>
      ) : null}

      <Dialog open={postOpen} onOpenChange={setPostOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Tahsilat veya Has Teslimat Kaydı</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label>Bayi Firma</Label>
              <Select value={organizationId} onValueChange={setOrganizationId}>
                <SelectTrigger className="text-xs">
                  <SelectValue placeholder="Firma seçin" />
                </SelectTrigger>
                <SelectContent>
                  {orgs.map((org) => (
                    <SelectItem key={org.id} value={org.id}>
                      {org.code} — {org.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Kayıt Tipi</Label>
              <Select
                value={postEntryType}
                onValueChange={(v) => setPostEntryType(v as 'PAYMENT_CREDIT' | 'HAS_DELIVERY')}
              >
                <SelectTrigger className="text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="PAYMENT_CREDIT">Tahsilat (USD)</SelectItem>
                  <SelectItem value="HAS_DELIVERY">Has Teslimat</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ledger-ref">Referans No</Label>
              <Input id="ledger-ref" value={referenceNo} onChange={(e) => setReferenceNo(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="ledger-usd">Tutar (USD)</Label>
                <Input id="ledger-usd" value={amountUsd} onChange={(e) => setAmountUsd(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ledger-has">Has (gr)</Label>
                <Input id="ledger-has" value={hasGoldGram} onChange={(e) => setHasGoldGram(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ledger-note">Not</Label>
              <Input id="ledger-note" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              disabled={
                createLedgerMut.isPending ||
                !organizationId ||
                !referenceNo.trim() ||
                (postEntryType === 'PAYMENT_CREDIT' ? !amountUsd : !hasGoldGram)
              }
              onClick={() => void onPostLedger()}
            >
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
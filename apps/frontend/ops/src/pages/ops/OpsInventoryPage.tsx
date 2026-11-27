import { useEffect, useState } from 'react';
import { ArrowLeftRight, ChevronDown, ChevronUp, Plus, Search, Warehouse } from 'lucide-react';
import { toast } from 'sonner';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
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
  useOpsStockMovementsQuery,
  useOpsStockTransferMutation,
  useOpsStocksQuery,
  useOpsWarehousesQuery,
} from '@taragold/shared/features/ops/hooks/useOpsQueries';
import { apiFetch, ApiClientError } from '@taragold/shared/lib/api/client';

export function OpsInventoryPage() {
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [warehouseId, setWarehouseId] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [transferOpen, setTransferOpen] = useState(false);
  const [variantSku, setVariantSku] = useState('');
  const [sourceWarehouseId, setSourceWarehouseId] = useState('');
  const [targetWarehouseId, setTargetWarehouseId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [referenceNo, setReferenceNo] = useState('');
  const [movementsOpen, setMovementsOpen] = useState(false);
  const [whOpen, setWhOpen] = useState(false);
  const [whCode, setWhCode] = useState('');
  const [whName, setWhName] = useState('');
  const [mvOpen, setMvOpen] = useState(false);
  const [mvSku, setMvSku] = useState('');
  const [mvWhId, setMvWhId] = useState('');
  const [mvType, setMvType] = useState('INBOUND');
  const [mvQty, setMvQty] = useState('1');
  const [mvRef, setMvRef] = useState('');
  const [savingInv, setSavingInv] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedQ(q.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(t);
  }, [q]);

  const warehousesQuery = useOpsWarehousesQuery({ pageSize: 200, isActive: true });
  const stocksQuery = useOpsStocksQuery({
    q: debouncedQ || undefined,
    warehouseId: warehouseId === 'all' ? undefined : warehouseId,
    page,
    pageSize: 50,
  });
  const transferMut = useOpsStockTransferMutation();
  const movementsQuery = useOpsStockMovementsQuery(
    {
      warehouseId: warehouseId === 'all' ? undefined : warehouseId,
      page: 1,
      pageSize: 30,
    },
    movementsOpen
  );
  const movements = movementsQuery.data?.items ?? [];

  const warehouses = warehousesQuery.data?.items ?? [];
  const rows = stocksQuery.data?.items ?? [];
  const pagination = stocksQuery.data?.pagination;

  const onTransfer = async () => {
    try {
      await transferMut.mutateAsync({
        variantSku: variantSku.trim(),
        sourceWarehouseId,
        targetWarehouseId,
        quantity: Number(quantity),
        referenceNo: referenceNo.trim(),
      });
      toast.success('Stok transferi tamamlandı');
      setTransferOpen(false);
      setVariantSku('');
      setReferenceNo('');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Transfer başarısız');
    }
  };

  const onCreateWarehouse = async () => {
    setSavingInv(true);
    try {
      await apiFetch('/api/v1/ops/warehouses', {
        method: 'POST',
        body: { code: whCode.trim().toUpperCase(), name: whName.trim(), isActive: true },
      });
      toast.success('Depo oluşturuldu');
      setWhOpen(false);
      setWhCode('');
      setWhName('');
      await warehousesQuery.refetch();
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Depo oluşturulamadı');
    } finally {
      setSavingInv(false);
    }
  };

  const onCreateMovement = async () => {
    setSavingInv(true);
    try {
      await apiFetch('/api/v1/ops/stock-movements', {
        method: 'POST',
        body: {
          variantSku: mvSku.trim(),
          warehouseId: mvWhId,
          movementType: mvType,
          quantity: Number(mvQty) || 1,
          referenceNo: mvRef.trim(),
        },
      });
      toast.success('Stok hareketi kaydedildi');
      setMvOpen(false);
      setMvSku('');
      setMvRef('');
      await Promise.all([stocksQuery.refetch(), movementsQuery.refetch()]);
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : 'Stok hareketi başarısız');
    } finally {
      setSavingInv(false);
    }
  };

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Depo Konumu & Varyant Stok Bakiyeleri"
        title={`Stok & Depo${pagination ? ` (${pagination.total} satır)` : ''}`}
        actions={
          <>
            <Select
              value={warehouseId}
              onValueChange={(v) => {
                setWarehouseId(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="h-9 w-44 text-xs">
                <SelectValue placeholder="Depo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm depolar</SelectItem>
                {warehouses.map((wh) => (
                  <SelectItem key={wh.id} value={wh.id}>
                    {wh.code} — {wh.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="SKU veya depo ara..."
                className="h-9 pl-8 w-52 text-xs"
              />
            </div>
            <Button size="sm" variant="outline" onClick={() => setWhOpen(true)}>
              <Warehouse className="w-3.5 h-3.5" />
              Yeni Depo
            </Button>
            <Button size="sm" variant="outline" onClick={() => setMvOpen(true)}>
              <Plus className="w-3.5 h-3.5" />
              Stok Hareketi
            </Button>
            <Button size="sm" variant="outline" onClick={() => setTransferOpen(true)}>
              <ArrowLeftRight className="w-3.5 h-3.5" />
              Depolar Arası Transfer
            </Button>
          </>
        }
      />

      <PortalDataCard>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Depo</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Varyant SKU</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Ürün</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Ayar / Renk</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Miktar</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Rezerve</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Kullanılabilir</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {stocksQuery.isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                  Yükleniyor...
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                  Stok kaydı yok.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="px-4">
                    <div className="font-mono font-semibold">{row.warehouseCode}</div>
                    <div className="text-[11px] text-muted-foreground">{row.warehouseName}</div>
                  </TableCell>
                  <TableCell className="px-4 font-sku font-semibold">{row.variantSku}</TableCell>
                  <TableCell className="px-4">
                    <div>{row.productTitle}</div>
                    <div className="font-sku text-[11px] text-muted-foreground">{row.parentSku}</div>
                  </TableCell>
                  <TableCell className="px-4 text-muted-foreground">
                    {row.purityCode} {row.metalColor} · {row.size}
                  </TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums">{row.quantity}</TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums text-muted-foreground">
                    {row.reservedQty}
                  </TableCell>
                  <TableCell className="px-4 text-right">
                    <Badge variant={row.availableQty <= 0 ? 'destructive' : 'outline'} className="font-mono tabular-nums">
                      {row.availableQty}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </PortalDataCard>

      <PortalDataCard>
        <button
          type="button"
          className="flex w-full items-center justify-between px-4 py-3 text-xs font-semibold text-foreground hover:bg-muted/30"
          onClick={() => setMovementsOpen((v) => !v)}
        >
          <span>Stok Hareket Geçmişi</span>
          {movementsOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {movementsOpen ? (
          <Table className="text-xs border-t">
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="px-4 uppercase text-[11px]">Tarih</TableHead>
                <TableHead className="px-4 uppercase text-[11px]">Tip</TableHead>
                <TableHead className="px-4 uppercase text-[11px]">SKU</TableHead>
                <TableHead className="px-4 uppercase text-[11px]">Depo</TableHead>
                <TableHead className="px-4 text-right uppercase text-[11px]">Δ Adet</TableHead>
                <TableHead className="px-4 uppercase text-[11px]">Referans</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {movementsQuery.isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    Yükleniyor...
                  </TableCell>
                </TableRow>
              ) : movements.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    Hareket kaydı yok.
                  </TableCell>
                </TableRow>
              ) : (
                movements.map((mv) => (
                  <TableRow key={mv.id}>
                    <TableCell className="px-4 font-mono text-muted-foreground">
                      {new Date(mv.createdAt).toLocaleString('tr-TR')}
                    </TableCell>
                    <TableCell className="px-4">{mv.movementType}</TableCell>
                    <TableCell className="px-4 font-sku">{mv.variantSku ?? mv.parentSku}</TableCell>
                    <TableCell className="px-4 font-mono">{mv.warehouseCode ?? '—'}</TableCell>
                    <TableCell className="px-4 text-right font-mono tabular-nums">{mv.quantityDelta}</TableCell>
                    <TableCell className="px-4 font-mono text-muted-foreground">{mv.referenceNo}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        ) : null}
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

      <Dialog open={transferOpen} onOpenChange={setTransferOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Depolar Arası Transfer</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label>Varyant SKU</Label>
              <Input value={variantSku} onChange={(e) => setVariantSku(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Kaynak Depo</Label>
              <Select value={sourceWarehouseId} onValueChange={setSourceWarehouseId}>
                <SelectTrigger className="text-xs">
                  <SelectValue placeholder="Seçin" />
                </SelectTrigger>
                <SelectContent>
                  {warehouses.map((wh) => (
                    <SelectItem key={wh.id} value={wh.id}>
                      {wh.code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Hedef Depo</Label>
              <Select value={targetWarehouseId} onValueChange={setTargetWarehouseId}>
                <SelectTrigger className="text-xs">
                  <SelectValue placeholder="Seçin" />
                </SelectTrigger>
                <SelectContent>
                  {warehouses.map((wh) => (
                    <SelectItem key={wh.id} value={wh.id}>
                      {wh.code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Adet</Label>
                <Input value={quantity} onChange={(e) => setQuantity(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Referans No</Label>
                <Input value={referenceNo} onChange={(e) => setReferenceNo(e.target.value)} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              disabled={
                transferMut.isPending ||
                !variantSku.trim() ||
                !sourceWarehouseId ||
                !targetWarehouseId ||
                !referenceNo.trim()
              }
              onClick={() => void onTransfer()}
            >
              Transferi Uygula
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={whOpen} onOpenChange={setWhOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Yeni Depo Oluştur</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label>Depo Kodu</Label>
              <Input value={whCode} onChange={(e) => setWhCode(e.target.value)} placeholder="IST-MERKEZ" />
            </div>
            <div className="space-y-1.5">
              <Label>Depo Adı</Label>
              <Input value={whName} onChange={(e) => setWhName(e.target.value)} placeholder="İstanbul Merkez Kasa" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWhOpen(false)}>Vazgeç</Button>
            <Button disabled={savingInv || !whCode.trim() || !whName.trim()} onClick={() => void onCreateWarehouse()}>
              Oluştur
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={mvOpen} onOpenChange={setMvOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Manuel Stok Hareketi</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="space-y-1.5">
              <Label>Varyant SKU</Label>
              <Input value={mvSku} onChange={(e) => setMvSku(e.target.value)} placeholder="SE009-14K-BYZ-050" />
            </div>
            <div className="space-y-1.5">
              <Label>Depo</Label>
              <Select value={mvWhId} onValueChange={setMvWhId}>
                <SelectTrigger className="text-xs">
                  <SelectValue placeholder="Depo seçin" />
                </SelectTrigger>
                <SelectContent>
                  {warehouses.map((wh) => (
                    <SelectItem key={wh.id} value={wh.id}>
                      {wh.code} — {wh.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Hareket Tipi</Label>
              <Select value={mvType} onValueChange={setMvType}>
                <SelectTrigger className="text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="INBOUND">Stok Girişi (INBOUND)</SelectItem>
                  <SelectItem value="SHIP">Sevkiyat Çıkışı (SHIP)</SelectItem>
                  <SelectItem value="RESERVE">Rezervasyon (RESERVE)</SelectItem>
                  <SelectItem value="RELEASE">Rezervasyon İptali (RELEASE)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Adet</Label>
                <Input type="number" value={mvQty} onChange={(e) => setMvQty(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Referans No</Label>
                <Input value={mvRef} onChange={(e) => setMvRef(e.target.value)} placeholder="SAYIM-01" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMvOpen(false)}>Vazgeç</Button>
            <Button
              disabled={savingInv || !mvSku.trim() || !mvWhId || !mvRef.trim()}
              onClick={() => void onCreateMovement()}
            >
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
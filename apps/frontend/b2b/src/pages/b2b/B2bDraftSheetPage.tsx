import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardList, FileCheck2, Minus, Plus, Trash2 } from 'lucide-react';
import {
  PortalDataCard,
  PortalPageHeader,
  PortalStat,
  PortalStatsSkeleton,
  PortalTableSkeleton,
} from '@taragold/shared/components/portal';
import {
  Button,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import { ConfirmDialog } from '@taragold/shared/components/crud/ConfirmDialog';
import {
  useB2bDraftQuery,
  useClearB2bDraftMutation,
  useCommerceUI,
  useRemoveB2bDraftLineMutation,
  useUpdateB2bDraftLineMutation,
} from '@taragold/shared/features/commerce/hooks/useCommerceQueries';
import { formatTrNumber } from '@taragold/shared/utils/pricingEngine';

export function B2bDraftSheetPage() {
  const draftQuery = useB2bDraftQuery();
  const updateLine = useUpdateB2bDraftLineMutation();
  const removeLine = useRemoveB2bDraftLineMutation();
  const clearDraft = useClearB2bDraftMutation();
  const { setB2bOrderOpen } = useCommerceUI();
  const [clearOpen, setClearOpen] = useState(false);

  const lines = draftQuery.data?.lines ?? [];

  const totals = useMemo(() => {
    const pieces = lines.reduce((s, l) => s + l.qty, 0);
    const grossGram = lines.reduce((s, l) => s + l.unitGrossGram * l.qty, 0);
    const hasGram = lines.reduce((s, l) => s + (l.unitFireIncludedFineGram ?? 0) * l.qty, 0);
    const laborStoneUsd = lines.reduce((s, l) => s + (l.unitLaborAndStoneUsd ?? 0) * l.qty, 0);
    const wholesaleUsd = lines.reduce((s, l) => s + l.unitWholesaleUsd * l.qty, 0);
    const wholesaleTry = lines.reduce((s, l) => s + l.unitWholesaleTry * l.qty, 0);
    return { pieces, grossGram, hasGram, laborStoneUsd, wholesaleUsd, wholesaleTry };
  }, [lines]);

  return (
    <div className="space-y-6">
      <PortalPageHeader
        eyebrow="Toptan Taslak Fiş · Asorti &amp; Maden Özeti"
        title={`Aktif Sipariş Fişi (${totals.pieces} adet)`}
        actions={
          <>
            {lines.length > 0 && (
              <Button variant="outline" size="sm" onClick={() => setClearOpen(true)}>
                Fişi Temizle
              </Button>
            )}
            <Button variant="outline" size="sm" asChild>
              <Link to="/b2b/katalog">Ürün Ekle</Link>
            </Button>
            <Button size="sm" disabled={lines.length === 0} onClick={() => setB2bOrderOpen(true)}>
              <FileCheck2 className="w-3.5 h-3.5" />
              Hesaplaşma &amp; Proforma Onayla
            </Button>
          </>
        }
      />

      {draftQuery.isLoading ? (
        <div className="space-y-4">
          <PortalStatsSkeleton count={5} />
          <PortalDataCard>
            <PortalTableSkeleton rows={6} />
          </PortalDataCard>
        </div>
      ) : lines.length === 0 ? (
        <PortalDataCard contentClassName="py-16 px-6 text-center space-y-3">
          <ClipboardList className="w-9 h-9 text-muted-foreground/40 mx-auto" />
          <div className="text-base font-semibold text-foreground">
            Sipariş fişinizde henüz kalem bulunmuyor
          </div>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Toptan katalog veya ürün detay ekranından tekli ya da çoklu ölçü asorti satırları
            ekleyerek fiş oluşturabilirsiniz.
          </p>
          <div className="pt-2">
            <Button size="sm" asChild>
              <Link to="/b2b/katalog">Toptan Kataloğa Git</Link>
            </Button>
          </div>
        </PortalDataCard>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <PortalStat label="Toplam Adet" value={`${totals.pieces} adet`} />
            <PortalStat
              label="Brüt Gram"
              value={`${formatTrNumber(totals.grossGram, 2)} gr`}
            />
            <PortalStat
              label="Fire Dahil Has"
              value={`${formatTrNumber(totals.hasGram, 4)} gr`}
              valueClassName="text-muted-foreground"
            />
            <PortalStat
              label="İşçilik + Taş"
              value={`$${formatTrNumber(totals.laborStoneUsd, 2)}`}
            />
            <PortalStat
              label="Toptan Toplam"
              value={`$${formatTrNumber(totals.wholesaleUsd, 2)}`}
              hint={`≈ ${formatTrNumber(totals.wholesaleTry, 0)} TL`}
            />
          </div>

          <PortalDataCard>
            <Table className="text-xs">
              <TableHeader className="bg-muted/40">
                <TableRow>
                  <TableHead className="px-4 uppercase text-[11px]">SKU / Ürün</TableHead>
                  <TableHead className="px-4 uppercase text-[11px]">Tedarik Tipi</TableHead>
                  <TableHead className="px-4 uppercase text-[11px]">Bayi Damgası / Not</TableHead>
                  <TableHead className="px-4 text-center uppercase text-[11px]">Adet</TableHead>
                  <TableHead className="px-4 text-right uppercase text-[11px]">Fire Dahil Has</TableHead>
                  <TableHead className="px-4 text-right uppercase text-[11px]">İşçilik+Taş</TableHead>
                  <TableHead className="px-4 text-right uppercase text-[11px]">Toptan (USD)</TableHead>
                  <TableHead className="px-4 text-right uppercase text-[11px]">Sil</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell className="px-4">
                      <div className="font-sku text-[11px] text-muted-foreground">{line.sku}</div>
                      <div className="font-medium text-foreground">{line.title}</div>
                      <div className="text-[11px] text-muted-foreground">
                        {line.purityCode} {line.metalColor} · {line.sizeUnitLabel} {line.size}
                      </div>
                    </TableCell>
                    <TableCell className="px-4">
                      <select
                        aria-label={`${line.sku} tedarik tipi`}
                        value={line.supplyType}
                        onChange={(e) =>
                          updateLine.mutate({
                            id: line.id,
                            patch: { supplyType: e.target.value as 'STOCK' | 'PRODUCTION' },
                          })
                        }
                        className="h-8 px-2 rounded-md border border-border bg-background text-xs"
                      >
                        <option value="STOCK">Hazır Stok</option>
                        <option value="PRODUCTION">Atölye Üretim</option>
                      </select>
                    </TableCell>
                    <TableCell className="px-4">
                      <Input
                        type="text"
                        value={line.dealerStampNote}
                        onChange={(e) =>
                          updateLine.mutate({
                            id: line.id,
                            patch: { dealerStampNote: e.target.value },
                          })
                        }
                        placeholder="Damga / not..."
                        className="h-8 w-40 text-xs"
                      />
                    </TableCell>
                    <TableCell className="px-4">
                      <div className="inline-flex items-center border border-border rounded-md overflow-hidden mx-auto">
                        <button
                          type="button"
                          onClick={() =>
                            line.qty <= 1
                              ? removeLine.mutate(line.id)
                              : updateLine.mutate({ id: line.id, patch: { qty: line.qty - 1 } })
                          }
                          className="px-2 py-1 hover:bg-muted cursor-pointer"
                        >
                          <Minus className="w-3 h-3" />
                        </button>
                        <span className="px-2.5 py-1 font-mono tabular-nums">{line.qty}</span>
                        <button
                          type="button"
                          onClick={() =>
                            updateLine.mutate({ id: line.id, patch: { qty: line.qty + 1 } })
                          }
                          className="px-2 py-1 hover:bg-muted cursor-pointer"
                        >
                          <Plus className="w-3 h-3" />
                        </button>
                      </div>
                    </TableCell>
                    <TableCell className="px-4 text-right font-mono font-medium text-muted-foreground tabular-nums">
                      {formatTrNumber((line.unitFireIncludedFineGram ?? 0) * line.qty, 4)} gr
                    </TableCell>
                    <TableCell className="px-4 text-right font-mono tabular-nums text-muted-foreground">
                      ${formatTrNumber((line.unitLaborAndStoneUsd ?? 0) * line.qty, 2)}
                    </TableCell>
                    <TableCell className="px-4 text-right font-mono font-semibold text-foreground tabular-nums">
                      ${formatTrNumber(line.unitWholesaleUsd * line.qty, 2)}
                    </TableCell>
                    <TableCell className="px-4 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        aria-label="Satırı sil"
                        onClick={() => removeLine.mutate(line.id)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </PortalDataCard>

          <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card/95 backdrop-blur px-4 py-3 shadow-sm">
            <div className="text-xs text-muted-foreground">
              <span className="font-mono font-semibold text-foreground tabular-nums">
                ${formatTrNumber(totals.wholesaleUsd, 2)}
              </span>{' '}
              toptan · {totals.pieces} adet
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link to="/b2b/katalog">Kataloga Dön</Link>
              </Button>
              <Button size="sm" onClick={() => setB2bOrderOpen(true)}>
                <FileCheck2 className="w-3.5 h-3.5" />
                Hesaplaşma &amp; Proforma Onayla
              </Button>
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        open={clearOpen}
        onOpenChange={setClearOpen}
        variant="destructive"
        isLoading={clearDraft.isPending}
        title="B2B sipariş fişini temizle"
        description="Taslak sipariş fişindeki tüm kalemler silinecek."
        confirmLabel="Fişi Temizle"
        cancelLabel="Vazgeç"
        onConfirm={async () => {
          await clearDraft.mutateAsync();
          setClearOpen(false);
        }}
      />
    </div>
  );
}

import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Calculator, Search } from 'lucide-react';
import { PortalDataCard, PortalPageHeader } from '@taragold/shared/components/portal';
import {
  Badge,
  Button,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@taragold/shared/components/ui';
import {
  useActiveProductMetrics,
  usePortalSelection,
} from '@taragold/shared/features/catalog/hooks/useCatalogQueries';
import { computeJewelryMetrics, formatTrNumber } from '@taragold/shared/utils/pricingEngine';

/* ============================================================================
   1. OPS VARIANTS PAGE (/ops/varyantlar)
   ============================================================================ */
export function OpsVariantsPage() {
  const { products, rates } = useActiveProductMetrics();
  const [query, setQuery] = useState('');

  const rows = useMemo(() => {
    const out: Array<{
      sku: string;
      parentSku: string;
      title: string;
      purity: string;
      color: string;
      size: string;
      weightGram: number;
      stockQty: number;
      b2bUsd: number;
      b2cTry: number;
    }> = [];

    for (const product of products) {
      const baseMetrics = computeJewelryMetrics(product, rates);
      if (product.variants && product.variants.length > 0) {
        for (const v of product.variants) {
          // Prefer server-evaluated variant quotes; else recompute with variant axes.
          const variantMetrics = computeJewelryMetrics(
            {
              ...product,
              purityCode: v.purityCode,
              metalColor: v.metalColor,
              variantSize: v.size,
              centerStoneCarat: v.centerStoneCarat,
              grossWeightGram: v.grossWeightGram,
            },
            rates
          );
          out.push({
            sku: v.sku,
            parentSku: product.parentSku,
            title: product.title,
            purity: v.purityCode,
            color: v.metalColor,
            size: String(v.size),
            weightGram: v.grossWeightGram,
            stockQty: v.stockQty,
            b2bUsd: v.b2bPricing?.finalPriceLc ?? variantMetrics.finalB2bPriceCurrency,
            b2cTry: v.b2cPricing?.finalPriceTry ?? variantMetrics.discountedB2cPriceTry,
          });
        }
      } else {
        out.push({
          sku: baseMetrics.sku,
          parentSku: product.parentSku,
          title: product.title,
          purity: product.purityCode,
          color: product.metalColor,
          size: String(product.variantSize),
          weightGram: product.grossWeightGram,
          stockQty: product.stockQty ?? 0,
          b2bUsd: baseMetrics.finalB2bPriceCurrency,
          b2cTry: baseMetrics.discountedB2cPriceTry,
        });
      }
    }

    const q = query.trim().toLocaleLowerCase('tr-TR');
    if (!q) return out;
    return out.filter(
      (r) =>
        r.sku.toLowerCase().includes(q) ||
        r.parentSku.toLowerCase().includes(q) ||
        r.title.toLocaleLowerCase('tr-TR').includes(q)
    );
  }, [products, rates, query]);

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="SKU Matrisi · Ayar, Renk, Ölçü ve Varyant Stoku"
        title={`Varyant Yönetimi (${rows.length} SKU)`}
        actions={
          <>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="SKU veya ürün ara..."
                className="h-9 pl-8 w-56 text-xs"
              />
            </div>
            <Button size="sm" variant="outline" asChild>
              <Link to="/ops/urunler">Ürün Kartından Düzenle</Link>
            </Button>
          </>
        }
      />

      <PortalDataCard>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Varyant SKU</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Model / Başlık</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Ayar &amp; Renk</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Ölçü</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Brüt (gr)</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Stok</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">B2C (TL)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.sku}>
                <TableCell className="px-4 font-sku font-semibold text-foreground">{row.sku}</TableCell>
                <TableCell className="px-4">
                  <div className="font-medium text-foreground">{row.title}</div>
                  <div className="font-sku text-[11px] text-muted-foreground">{row.parentSku}</div>
                </TableCell>
                <TableCell className="px-4 text-muted-foreground">
                  {row.purity} {row.color}
                </TableCell>
                <TableCell className="px-4 font-mono text-muted-foreground">{row.size}</TableCell>
                <TableCell className="px-4 text-right font-mono tabular-nums text-muted-foreground">
                  {formatTrNumber(row.weightGram, 2)}
                </TableCell>
                <TableCell className="px-4 text-right">
                  <Badge
                    variant={row.stockQty <= 0 ? 'destructive' : 'outline'}
                    className={
                      row.stockQty <= 0
                        ? 'font-mono tabular-nums'
                        : row.stockQty <= 2
                          ? 'font-mono tabular-nums text-amber-700 border-amber-200'
                          : 'font-mono tabular-nums text-emerald-700 border-emerald-200'
                    }
                  >
                    {row.stockQty}
                  </Badge>
                </TableCell>
                <TableCell className="px-4 text-right font-mono font-semibold tabular-nums text-foreground">
                  {formatTrNumber(row.b2cTry, 0)} TL
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </PortalDataCard>
    </div>
  );
}

/* ============================================================================
   2. OPS STONE & MOUNT PAGE (/ops/tas-montur)
   ============================================================================ */
export function OpsStoneMountPage() {
  const { products } = useActiveProductMetrics();

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="Montür Kafa/Kol Kodları, İzinli Karat Aralığı &amp; Çoklu Taş Satırları"
        title="Taş &amp; Montür Teknik Yapısı"
        actions={
          <Button size="sm" variant="outline" asChild>
            <Link to="/ops/urunler">Katalogda Düzenle</Link>
          </Button>
        }
      />

      <PortalDataCard>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Parent SKU</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Montür / Kafa / Kol</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">İzinli Karat</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Taş Satırları (Adet × Karat)</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Sertifika</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {products.map((p) => {
              const mount = p.mountSpec;
              const stones = p.stoneLines ?? [];
              return (
                <TableRow key={p.parentSku} className="align-top">
                  <TableCell className="px-4">
                    <div className="font-sku font-semibold text-foreground">{p.parentSku}</div>
                    <div className="text-[11px] text-muted-foreground">{p.title}</div>
                  </TableCell>
                  <TableCell className="px-4 font-mono text-muted-foreground">
                    {mount ? (
                      <div>
                        <div>
                          {mount.headCode || '—'} / {mount.bandCode || '—'}
                        </div>
                        <div className="font-sans text-[11px] text-muted-foreground">
                          Yapı: {mount.structure} · Kafa/Kol:{' '}
                          {formatTrNumber(
                            (mount.headWeightGram ?? 0) + (mount.bandWeightGram ?? 0),
                            2
                          )}{' '}
                          gr
                        </div>
                      </div>
                    ) : (
                      <span className="font-sans text-muted-foreground">Standart Model</span>
                    )}
                  </TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums text-muted-foreground">
                    {mount
                      ? `${formatTrNumber(mount.allowedCaratMin, 2)} – ${formatTrNumber(mount.allowedCaratMax, 2)} ct`
                      : '—'}
                  </TableCell>
                  <TableCell className="px-4 space-y-1">
                    {stones.length > 0 ? (
                      stones.map((line) => (
                        <div key={line.id} className="font-mono text-[11px] text-muted-foreground">
                          {line.role === 'MERKEZ' ? 'Merkez' : line.role} · {line.count}×{' '}
                          {formatTrNumber(line.carat, 2)} {line.measureUnit} (
                          {line.cutShape || line.stoneType}) · {line.colorGrade || '—'}/
                          {line.clarity || '—'}
                        </div>
                      ))
                    ) : (
                      <div className="text-muted-foreground">
                        {p.stoneType} ·{' '}
                        {formatTrNumber(p.centerStoneCarat + p.sideStoneCarat, 2)} ct ·{' '}
                        {p.stoneColorGrade}/{p.stoneClarity}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="px-4 font-mono text-muted-foreground">{p.certificateAgency}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </PortalDataCard>
    </div>
  );
}

/* ============================================================================
   3. OPS RECIPES PAGE (/ops/receteler)
   ============================================================================ */
export function OpsRecipesPage() {
  const navigate = useNavigate();
  const { products, rates } = useActiveProductMetrics();
  const { setSelectedParentSku } = usePortalSelection();

  return (
    <div className="space-y-5">
      <PortalPageHeader
        eyebrow="13 Birimli Defter Para Birimi (LC), Maliyet Satırları &amp; Kanal Kuralları"
        title={`Maliyet Reçeteleri (${products.length})`}
        actions={
          <Button size="sm" asChild>
            <Link to="/ops/fiyat-motoru">
              <Calculator className="w-3.5 h-3.5" />
              Fiyat Motoruna Git
            </Link>
          </Button>
        }
      />

      <PortalDataCard>
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="px-4 uppercase text-[11px]">Model</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Fiyat Modu</TableHead>
              <TableHead className="px-4 uppercase text-[11px]">Defter Birimi (LC)</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">Maliyet Kalemi</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">B2B Net</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">B2C Net (TL)</TableHead>
              <TableHead className="px-4 text-right uppercase text-[11px]">İşlem</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {products.map((p) => {
              const metrics = computeJewelryMetrics(p, rates);
              return (
                <TableRow key={p.parentSku}>
                  <TableCell className="px-4">
                    <div className="font-sku font-semibold text-foreground">{p.parentSku}</div>
                    <div className="text-[11px] text-muted-foreground">{p.title}</div>
                  </TableCell>
                  <TableCell className="px-4 font-mono text-muted-foreground">Model {p.pricingMode}</TableCell>
                  <TableCell className="px-4 font-sku font-medium text-muted-foreground">
                    {p.ledger?.lcCurrency ?? p.pricingCurrency ?? 'TRY'}
                  </TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums text-muted-foreground">
                    {p.ledger?.channelRules?.length ?? 0} kanal kuralı
                  </TableCell>
                  <TableCell className="px-4 text-right font-mono tabular-nums text-foreground">
                    {formatTrNumber(metrics.finalB2bPriceCurrency, 2)} {p.pricingCurrency}
                  </TableCell>
                  <TableCell className="px-4 text-right font-mono font-semibold tabular-nums text-foreground">
                    {formatTrNumber(metrics.discountedB2cPriceTry, 0)} TL
                  </TableCell>
                  <TableCell className="px-4 text-right">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedParentSku(p.parentSku);
                        navigate('/ops/fiyat-motoru');
                      }}
                      className="text-xs font-medium text-muted-foreground hover:underline cursor-pointer"
                    >
                      Reçeteyi Aç →
                    </button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </PortalDataCard>
    </div>
  );
}


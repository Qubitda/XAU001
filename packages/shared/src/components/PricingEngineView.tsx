import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Globe,
  Plus,
  RotateCcw,
  Trash2,
} from 'lucide-react';
import { PortalDataCard } from './portal';
import { Button, Input } from './ui';
import { cn } from '../lib/utils';
import {
  AdjustmentUnit,
  ChannelPricingRule,
  ComputedJewelryMetrics,
  FxCurrencyCode,
  LiveRates,
  PricingChannelTarget,
  PricingLedgerConfig,
  PricingMode,
  ProductState,
  PurityCode,
  StoneMeasureUnit,
  StoneType,
} from '../types/jewelry';
import {
  deriveSalesChannelsFromRules,
  formatCurrencyValue,
  formatTrNumber,
  FX_CURRENCIES,
  getMatrixRate,
  PURITY_MAP,
  STONE_UNIT_GUIDE,
  TROY_OZ_TO_GRAM,
} from '../utils/pricingEngine';
import {
  useDefinitionOptions,
  usePurityFinenessMap,
} from '../features/definitions/hooks/useDefinitionsQuery';
import { cloneLedger, withCurrentValue } from '../data/productDefaults';
import { Link } from 'react-router-dom';

interface PricingEngineViewProps {
  product: ProductState;
  rates: LiveRates;
  computed: ComputedJewelryMetrics;
  onUpdateProduct: (patch: Partial<ProductState>) => void;
  onUpdateRates: (patch: Partial<LiveRates>) => void;
}

const PRICING_FIELD_SELECT_CLASS = 'flex h-8 w-full items-center rounded-md border border-input bg-background px-2.5 text-xs shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

const ADJUSTMENT_UNITS: AdjustmentUnit[] = [
  '%',
  'TRY',
  'USD',
  'EUR',
  'GBP',
  'CHF',
  'XAU',
  'XAG',
  'XPT',
  'XPD',
];

const PRECIOUS_METAL_LABELS: Partial<Record<FxCurrencyCode, string>> = {
  XAU: 'Altın',
  XAG: 'Gümüş',
  XPT: 'Platin',
  XPD: 'Paladyum',
};

const isPreciousMetalCode = (code: FxCurrencyCode): boolean =>
  code === 'XAU' || code === 'XAG' || code === 'XPT' || code === 'XPD';

/** Shrinks wide content to container width — no horizontal scroll. */
function FitWidthScale({ children, deps = [] }: { children: ReactNode; deps?: unknown[] }) {
  const outerRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [innerHeight, setInnerHeight] = useState<number | null>(null);

  useLayoutEffect(() => {
    const outer = outerRef.current;
    const inner = innerRef.current;
    if (!outer || !inner) return;

    const fit = () => {
      const available = outer.clientWidth;
      const needed = inner.scrollWidth;
      const next = needed > 0 && available > 0 ? Math.min(1, available / needed) : 1;
      setScale(next);
      setInnerHeight(inner.offsetHeight);
    };

    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(outer);
    ro.observe(inner);
    window.addEventListener('resize', fit);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', fit);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return (
    <div
      ref={outerRef}
      className="w-full max-w-full overflow-hidden"
      style={{ height: innerHeight != null ? innerHeight * scale : undefined }}
    >
      <div
        ref={innerRef}
        className="origin-top-left will-change-transform"
        style={{
          transform: `scale(${scale})`,
          width: scale < 1 ? `${100 / scale}%` : '100%',
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function PricingEngineView({
  product,
  rates,
  computed,
  onUpdateProduct,
  onUpdateRates,
}: PricingEngineViewProps) {
  const [matrixExpanded, setMatrixExpanded] = useState<boolean>(false);
  const stoneTypeDefs = useDefinitionOptions('tas_tipi');
  const purityDefs = useDefinitionOptions('ayar_kodu');
  const { map: finenessMap } = usePurityFinenessMap();

  const stoneTypeOptions: StoneType[] = withCurrentValue(
    stoneTypeDefs.options.map((o) => o.value as StoneType),
    product.stoneType
  );
  const purityOptions: PurityCode[] = withCurrentValue(
    purityDefs.options.map((o) => o.value as PurityCode),
    product.purityCode
  );

  const resolveFineness = (code: string): number => {
    if (finenessMap[code] != null) return finenessMap[code];
    return PURITY_MAP[code]?.fineness ?? 0;
  };

  const ledger = cloneLedger(product.ledger);
  const lc = computed.ledger.lcCurrency;
  const stoneUnit: StoneMeasureUnit = product.stoneMeasureUnit ?? 'ct';

  const updateLedger = (patch: Partial<PricingLedgerConfig>) => {
    const nextLedger: PricingLedgerConfig = {
      ...ledger,
      ...patch,
    };
    onUpdateProduct({
      ledger: nextLedger,
      ...(patch.channelRules
        ? { salesChannels: deriveSalesChannelsFromRules(patch.channelRules) }
        : {}),
    });
  };

  const handleStoneTypeChange = (nextStoneType: StoneType) => {
    const guide = STONE_UNIT_GUIDE.find((g) => g.stoneType === nextStoneType);
    onUpdateProduct({
      stoneType: nextStoneType,
      stoneMeasureUnit: guide ? guide.defaultUnit : 'ct',
    });
  };

  const handleTotalStoneWeightChange = (nextTotal: number) => {
    const safeTotal = Math.max(0, nextTotal);
    if (safeTotal >= product.sideStoneCarat) {
      onUpdateProduct({
        centerStoneCarat: Number((safeTotal - product.sideStoneCarat).toFixed(4)),
      });
    } else {
      onUpdateProduct({
        centerStoneCarat: Number(safeTotal.toFixed(4)),
        sideStoneCarat: 0,
      });
    }
  };

  const usedChannels = new Set(ledger.channelRules.map((r) => r.channel));
  const hasB2bRule = usedChannels.has('B2B');
  const hasB2bApiRule = usedChannels.has('B2B_API');
  const hasB2cApiRule = usedChannels.has('B2C_API');
  const canAddMoreChannels = !(hasB2bRule && hasB2bApiRule && hasB2cApiRule);

  const handleAddChannelRule = (preferred?: PricingChannelTarget) => {
    const target: PricingChannelTarget =
      preferred ??
      (!hasB2bRule ? 'B2B' : !hasB2bApiRule ? 'B2B_API' : 'B2C_API');

    if (usedChannels.has(target)) return;

    const newRule: ChannelPricingRule = {
      id: `ch-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      channel: target,
      profit:
        target === 'B2C_API'
          ? { unit: '%', value: 45 }
          : { unit: '%', value: 15 },
      discount: { unit: '%', value: 0 },
      platformFee: { unit: '%', value: 1 },
    };

    updateLedger({
      channelRules: [...ledger.channelRules, newRule],
    });
  };

  const handleUpdateChannelRule = (
    ruleId: string,
    patch: Partial<ChannelPricingRule>
  ) => {
    if (
      patch.channel &&
      ledger.channelRules.some((r) => r.id !== ruleId && r.channel === patch.channel)
    ) {
      return;
    }
    updateLedger({
      channelRules: ledger.channelRules.map((r) =>
        r.id === ruleId ? { ...r, ...patch } : r
      ),
    });
  };

  const handleRemoveChannelRule = (ruleId: string) => {
    updateLedger({
      channelRules: ledger.channelRules.filter((r) => r.id !== ruleId),
    });
  };

  const handleBaseRateChange = (code: FxCurrencyCode, newTryValue: number) => {
    const safeVal = Math.max(0.0001, newTryValue);
    const nextFx = {
      ...rates.fxBaseRates,
      [code]: code === 'TRY' ? 1 : safeVal,
    };
    const nextHasGoldTry =
      code === 'XAU' ? Number((safeVal / TROY_OZ_TO_GRAM).toFixed(2)) : rates.liveHasGoldTrySell;
    onUpdateRates({
      sourceMode: 'manual',
      fxBaseRates: nextFx,
      liveUsdSell: nextFx.USD,
      liveEurSell: nextFx.EUR,
      liveHasGoldTrySell: nextHasGoldTry,
    });
  };

  const parameterLabel =
    product.stoneType === 'Taşsız'
      ? 'Parametre: Taşsız Ürün'
      : stoneUnit === 'gr'
        ? 'Parametre: Gram × 1,00 = Gram'
        : stoneUnit === 'mm'
          ? 'Parametre: mm × 0,05 = Gram (Tahmini)'
          : 'Parametre: Karat × 0,20 = Gram';

  const parameterUnitSuffix =
    product.stoneType === 'Taşsız'
      ? 'gr'
      : stoneUnit === 'gr'
        ? 'gr/gr'
        : stoneUnit === 'mm'
          ? 'gr/mm'
          : 'gr/ct';

  return (
    <div className="space-y-8 w-full max-w-full min-w-0 overflow-x-hidden">
      {/* ÇAPRAZ KUR & DEĞERLİ METAL MATRİSİ */}
      <PortalDataCard
        title="Çapraz Kur & Değerli Metal Matrisi (A \ B)"
        contentClassName="p-4"
        className="overflow-hidden max-w-full min-w-0"
        toolbar={
          <div className="flex flex-wrap items-center justify-end gap-2 text-xs min-w-0 max-w-full">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="hidden lg:inline-flex h-7 min-h-7 px-2 text-xs shrink-0"
              onClick={() => setMatrixExpanded((prev) => !prev)}
            >
              {matrixExpanded ? (
                <>
                  <ChevronDown className="mr-1 h-3.5 w-3.5" /> Daralt
                </>
              ) : (
                <>
                  <ChevronRight className="mr-1 h-3.5 w-3.5" /> Genişlet
                </>
              )}
            </Button>

            <div className="hidden sm:flex flex-wrap items-center gap-2 text-muted-foreground min-w-0">
              <Globe className="h-3.5 w-3.5 shrink-0" />
              <span>
                USD{' '}
                <strong className="text-foreground">
                  {formatTrNumber(rates.fxBaseRates.USD, 2)}
                </strong>
              </span>
              <span>
                EUR{' '}
                <strong className="text-foreground">
                  {formatTrNumber(rates.fxBaseRates.EUR, 2)}
                </strong>
              </span>
              <span>
                Has{' '}
                <strong className="text-foreground">
                  {formatTrNumber(rates.liveHasGoldTrySell, 2)}
                </strong>
              </span>
              <span>
                XAG{' '}
                <strong className="text-foreground">
                  {formatTrNumber(rates.fxBaseRates.XAG, 2)}
                </strong>
              </span>
              <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] truncate max-w-[140px]">
                {rates.snapshotId}
              </span>
            </div>
          </div>
        }
      >
        <div className="space-y-3 min-w-0 max-w-full">
          <p className="text-xs text-muted-foreground">
            İlk sütundaki (<strong>TRY</strong>) baz kur ve değerli metal ons (
            <strong>XAU Altın, XAG Gümüş, XPT Platin, XPD Paladyum</strong>) değerlerini
            düzenlediğinizde tüm 13×13 çapraz kur hücreleri ve maliyet satırları anında
            güncellenir.
          </p>

          {/* Mobil & tablet: her zaman açık hızlı TRY baz kur düzenleyici */}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:hidden">
            {FX_CURRENCIES.filter((code) => code !== 'TRY').map((code) => {
              const metalLabel = PRECIOUS_METAL_LABELS[code];
              const val = rates.fxBaseRates[code] ?? 0;
              return (
                <div
                  key={`mobile-fx-${code}`}
                  className="flex items-center justify-between gap-2 rounded-md border bg-muted/20 px-3 py-2 min-w-0"
                >
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-foreground">
                      {code}{' '}
                      {metalLabel ? (
                        <span className="font-normal text-muted-foreground">({metalLabel})</span>
                      ) : null}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {isPreciousMetalCode(code) ? '1 Ons / TRY' : '1 Birim / TRY'}
                    </div>
                  </div>
                  <Input
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={val}
                    onChange={(e) =>
                      handleBaseRateChange(code, parseFloat(e.target.value) || 0)
                    }
                    aria-label={`${code} TRY satış kuru`}
                    className="h-8 min-h-8 w-24 sm:w-28 max-w-[40%] min-w-0 shrink-0 text-right font-mono text-xs tabular-nums"
                  />
                </div>
              );
            })}
          </div>

          {/* Masaüstü: FitWidthScale ile taşmasız 13×13 matris */}
          {matrixExpanded ? (
            <div className="hidden lg:block min-w-0 max-w-full overflow-hidden">
              <FitWidthScale
                deps={[rates.fxBaseRates, rates.liveHasGoldTrySell, matrixExpanded]}
              >
                <div className="rounded-md border">
                  <table className="w-full border-collapse text-[11px]">
                    <thead>
                      <tr className="bg-primary text-primary-foreground">
                        <th className="px-2.5 py-2 text-left font-semibold whitespace-nowrap">
                          A \ B
                        </th>
                        {FX_CURRENCIES.map((colCode) => (
                          <th
                            key={`head-${colCode}`}
                            className="px-2 py-2 text-right font-semibold whitespace-nowrap"
                          >
                            <div>{colCode}</div>
                            {PRECIOUS_METAL_LABELS[colCode] ? (
                              <div className="text-[9px] font-normal text-primary-foreground/70">
                                {PRECIOUS_METAL_LABELS[colCode]}
                              </div>
                            ) : null}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {FX_CURRENCIES.map((rowCode) => {
                        const rowVal = rates.fxBaseRates[rowCode] ?? 1;
                        return (
                          <tr key={`row-${rowCode}`} className="hover:bg-muted/40">
                            <td className="bg-background px-2.5 py-1.5 font-semibold whitespace-nowrap border-r">
                              <span>{rowCode}</span>
                              {PRECIOUS_METAL_LABELS[rowCode] ? (
                                <span className="ml-1 text-[10px] font-normal text-muted-foreground">
                                  {PRECIOUS_METAL_LABELS[rowCode]}
                                </span>
                              ) : null}
                            </td>

                            {FX_CURRENCIES.map((colCode) => {
                              const isDiagonal = rowCode === colCode;

                              if (colCode === 'TRY') {
                                return (
                                  <td
                                    key={`${rowCode}-${colCode}`}
                                    className="bg-muted px-1.5 py-1 text-right whitespace-nowrap"
                                  >
                                    {rowCode === 'TRY' ? (
                                      <span className="inline-block rounded bg-muted px-2 py-1 font-mono font-semibold text-foreground tabular-nums">
                                        1,000
                                      </span>
                                    ) : (
                                      <Input
                                        type="number"
                                        step="any"
                                        value={rowVal}
                                        onChange={(e) =>
                                          handleBaseRateChange(
                                            rowCode,
                                            parseFloat(e.target.value) || 0
                                          )
                                        }
                                        aria-label={`${rowCode} TRY satış kuru`}
                                        className="h-7 min-h-7 w-28 min-w-[7rem] px-1.5 text-right font-mono text-[11px] tabular-nums"
                                      />
                                    )}
                                  </td>
                                );
                              }

                              const cellRate = getMatrixRate(
                                rowCode,
                                colCode,
                                rates.fxBaseRates
                              );
                              const decimals =
                                cellRate >= 10000
                                  ? 1
                                  : cellRate >= 100
                                    ? 2
                                    : cellRate >= 1
                                      ? 3
                                      : 6;

                              return (
                                <td
                                  key={`${rowCode}-${colCode}`}
                                  className="px-2 py-1.5 text-right font-mono tabular-nums whitespace-nowrap"
                                >
                                  {isDiagonal ? (
                                    <span className="inline-block rounded bg-muted px-1.5 py-0.5 font-semibold text-foreground">
                                      1,000
                                    </span>
                                  ) : (
                                    <span className="text-foreground/90">
                                      {formatTrNumber(cellRate, decimals)}
                                    </span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </FitWidthScale>
            </div>
          ) : null}
        </div>
      </PortalDataCard>

      {/* SECTION B: 4-BLOCK TECHNICAL CALCULATION SHEET */}
      <section className="space-y-5">
          {/* 1. Taş Hesaplaması */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="bg-primary text-primary-foreground px-5 py-2.5 text-xs font-semibold tracking-wide">
              Taş Hesaplaması
            </div>
            <div className="divide-y divide-border text-xs">
              {/* Taş Tipi */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Taş Tipi
                </div>
                <div className="sm:col-span-4 px-4 py-2 space-y-1">
                  <select
                    value={product.stoneType}
                    onChange={(e) => handleStoneTypeChange(e.target.value as StoneType)}
                    aria-label="Taş tipi seçimi"
                    disabled={stoneTypeDefs.isLoading || stoneTypeDefs.isError}
                    className="text-xs font-medium bg-muted/50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {stoneTypeDefs.isLoading ? (
                      <option value={product.stoneType || ''}>Tanımlar yükleniyor...</option>
                    ) : null}
                    {!stoneTypeDefs.isLoading && stoneTypeDefs.options.length === 0 ? (
                      <option value={product.stoneType || ''}>
                        Tanım tablosunda aktif kayıt bulunamadı
                      </option>
                    ) : null}
                    {!stoneTypeDefs.isLoading
                      ? stoneTypeOptions.map((st) => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))
                      : null}
                  </select>
                  {stoneTypeDefs.isError ? (
                    <p className="text-[11px] text-muted-foreground">
                      Taş tipi tanımları yüklenemedi.{' '}
                      <button
                        type="button"
                        className="underline font-medium"
                        onClick={() => void stoneTypeDefs.refetch()}
                      >
                        Tekrar dene
                      </button>
                    </p>
                  ) : null}
                  {!stoneTypeDefs.isLoading &&
                  !stoneTypeDefs.isError &&
                  stoneTypeDefs.options.length === 0 ? (
                    <p className="text-[11px] text-muted-foreground">
                      Tanımları eklemek için{' '}
                      <Link to="/ops/tanimlar" className="underline text-foreground">
                        Tanım Yönetimi
                      </Link>
                      .
                    </p>
                  ) : null}
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Taş türüne göre ölçü birimi önerilir
                </div>
              </div>

              {/* Toplam Taş Ağırlığı */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Toplam Taş Ağırlığı
                </div>
                <div className="sm:col-span-4 px-4 py-2 flex items-center gap-2">
                  <Input
                    type="number"
                    step="0.01"
                    min={0}
                    value={computed.totalStoneCarat}
                    disabled={product.stoneType === 'Taşsız'}
                    onChange={(e) => handleTotalStoneWeightChange(Number(e.target.value) || 0)}
                    aria-label="Toplam taş ağırlığı"
                    className="w-28 text-right font-mono tabular-nums bg-muted/50"
                  />
                  <select
                    value={stoneUnit}
                    disabled={product.stoneType === 'Taşsız'}
                    onChange={(e) =>
                      onUpdateProduct({ stoneMeasureUnit: e.target.value as StoneMeasureUnit })
                    }
                    aria-label="Taş ölçü birimi"
                    className="px-2 py-1.5 font-mono text-xs bg-card border border-border rounded-md text-foreground disabled:opacity-50"
                  >
                    <option value="ct">ct</option>
                    <option value="gr">gr</option>
                    <option value="mm">mm</option>
                  </select>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Merkez + yan taş toplamı
                </div>
              </div>

              {/* Parametre */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  {parameterLabel}
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono tabular-nums text-foreground">
                  {formatTrNumber(computed.stoneTareFactor, 4)}{' '}
                  <span className="text-muted-foreground">{parameterUnitSuffix}</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Standart dönüşüm katsayısı
                </div>
              </div>

              {/* Taş Gram Karşılığı — tüm satır vurgulu */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center bg-muted text-foreground">
                <div className="sm:col-span-4 px-5 py-2.5 font-semibold">
                  Taş Gram Karşılığı
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono font-bold tabular-nums text-foreground">
                  {formatTrNumber(computed.stoneTareGram, 4)} <span className="font-normal text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground font-medium">
                  Otomatik hesaplanır
                </div>
              </div>
            </div>
          </div>

          {/* 2. Ağırlık / Gramaj */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="bg-primary text-primary-foreground px-5 py-2.5 text-xs font-semibold tracking-wide">
              Ağırlık / Gramaj
            </div>
            <div className="divide-y divide-border text-xs">
              {/* Brüt Ağırlık (Terazi) */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Brüt Ağırlık (Terazi)
                </div>
                <div className="sm:col-span-4 px-4 py-2 flex items-center gap-2">
                  <Input
                    type="number"
                    step="0.01"
                    min={0}
                    value={product.grossWeightGram}
                    onChange={(e) =>
                      onUpdateProduct({
                        grossWeightGram: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    aria-label="Brüt ağırlık gram"
                    className="w-28 text-right px-2.5 py-1.5 font-mono tabular-nums bg-muted/50 border border-input rounded-md text-foreground focus:outline-none focus:border-ring"
                  />
                  <span className="font-mono text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Zorunlu. Teraziden okunan taşlı toplam ağırlık.
                </div>
              </div>

              {/* Taş Ağırlığı */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Taş Ağırlığı
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono font-semibold tabular-nums text-foreground">
                  {formatTrNumber(computed.stoneTareGram, 4)}{' '}
                  <span className="font-normal text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Taş gram karşılığından otomatik gelir
                </div>
              </div>

              {/* Net Maden Ağırlığı */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-semibold text-foreground">
                  Net Maden Ağırlığı
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono font-bold tabular-nums text-foreground">
                  {formatTrNumber(computed.netMetalGram, 4)}{' '}
                  <span className="font-normal text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Brüt Ağırlık − Taş Ağırlığı
                </div>
              </div>

              {/* Has Maden Ağırlığı — tüm satır vurgulu */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center bg-muted text-foreground">
                <div className="sm:col-span-4 px-5 py-2.5 font-semibold">
                  Has Maden Ağırlığı
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono font-bold tabular-nums text-foreground">
                  {formatTrNumber(computed.fineMetalGram, 4)}{' '}
                  <span className="font-normal text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Net Maden Ağırlığı × Maden Ayarı
                </div>
              </div>
            </div>
          </div>

          {/* 3. Fire Hesaplaması */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="bg-primary text-primary-foreground px-5 py-2.5 text-xs font-semibold tracking-wide">
              Fire Hesaplaması
            </div>
            <div className="divide-y divide-border text-xs">
              {/* Fire Oranı */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Fire Oranı
                </div>
                <div className="sm:col-span-4 px-4 py-2 flex items-center gap-2">
                  <Input
                    type="number"
                    step="0.25"
                    min={0}
                    max={30}
                    value={product.fireRatePct}
                    onChange={(e) =>
                      onUpdateProduct({
                        fireRatePct: Math.max(0, Number(e.target.value) || 0),
                      })
                    }
                    aria-label="Fire oranı yüzde"
                    className="w-28 text-right px-2.5 py-1.5 font-mono tabular-nums bg-muted/50 border border-input rounded-md text-foreground focus:outline-none focus:border-ring"
                  />
                  <span className="font-mono text-zinc-600">%</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Elle girilir
                </div>
              </div>

              {/* Net Maden Ağırlığı */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Net Maden Ağırlığı
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono tabular-nums text-foreground">
                  {formatTrNumber(computed.netMetalGram, 4)}{' '}
                  <span className="text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Otomatik gelir
                </div>
              </div>

              {/* Fire Ağırlığı */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Fire Ağırlığı
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono font-semibold tabular-nums text-foreground">
                  {formatTrNumber(computed.fireWeightGram, 4)}{' '}
                  <span className="font-normal text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Net Maden Ağırlığı × Fire Oranı
                </div>
              </div>

              {/* Fire Dahil Maden Tüketimi */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center">
                <div className="sm:col-span-4 px-5 py-2.5 bg-muted/60 font-medium text-foreground">
                  Fire Dahil Maden Tüketimi
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono font-semibold tabular-nums text-foreground">
                  {formatTrNumber(computed.fireIncludedMetalGram, 4)}{' '}
                  <span className="font-normal text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground">
                  Net Maden Ağırlığı + Fire Ağırlığı
                </div>
              </div>

              {/* Fire Dahil Has Maden Ağırlığı — tüm satır vurgulu */}
              <div className="grid grid-cols-1 sm:grid-cols-12 items-center bg-muted text-foreground">
                <div className="sm:col-span-4 px-5 py-2.5 font-semibold">
                  Fire Dahil Has Maden Ağırlığı
                </div>
                <div className="sm:col-span-4 px-4 py-2.5 font-mono font-bold tabular-nums text-foreground">
                  {formatTrNumber(computed.fireIncludedFineMetalGram, 4)}{' '}
                  <span className="font-normal text-muted-foreground">gr</span>
                </div>
                <div className="sm:col-span-4 px-4 py-2 text-[11px] text-muted-foreground font-medium">
                  Fire dahil maden tüketimi × Maden Ayarı
                </div>
              </div>
            </div>
          </div>

          {/* 4. Metal Hesaplaması */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="bg-primary text-primary-foreground px-5 py-2.5 text-xs font-semibold tracking-wide">
              Metal Hesaplaması
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-12 items-center text-xs">
              <div className="sm:col-span-4 px-5 py-3 bg-muted/60 font-medium text-foreground">
                Maden Ayarı
              </div>
              <div className="sm:col-span-4 px-4 py-2.5 space-y-1">
                <div className="flex items-center gap-2.5">
                  <select
                    value={product.purityCode}
                    onChange={(e) => onUpdateProduct({ purityCode: e.target.value as PurityCode })}
                    aria-label="Maden ayarı seçimi"
                    disabled={purityDefs.isLoading || purityDefs.isError}
                    className="px-3 py-1.5 font-mono text-xs font-semibold bg-muted/50 border border-input rounded-md text-foreground focus:outline-none focus:border-ring disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {purityDefs.isLoading ? (
                      <option value={product.purityCode || ''}>Tanımlar yükleniyor...</option>
                    ) : null}
                    {!purityDefs.isLoading && purityDefs.options.length === 0 ? (
                      <option value={product.purityCode || ''}>
                        Tanım tablosunda aktif kayıt bulunamadı
                      </option>
                    ) : null}
                    {!purityDefs.isLoading
                      ? purityOptions.map((code) => (
                          <option key={code} value={code}>
                            {formatTrNumber(resolveFineness(code), 3)} ({code})
                          </option>
                        ))
                      : null}
                  </select>
                  <span className="text-[11px] text-muted-foreground whitespace-nowrap">has katsayısı</span>
                </div>
                {purityDefs.isError ? (
                  <p className="text-[11px] text-muted-foreground">
                    Ayar tanımları yüklenemedi.{' '}
                    <button
                      type="button"
                      className="underline font-medium"
                      onClick={() => void purityDefs.refetch()}
                    >
                      Tekrar dene
                    </button>
                  </p>
                ) : null}
                {!purityDefs.isLoading &&
                !purityDefs.isError &&
                purityDefs.options.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground">
                    Tanımları eklemek için{' '}
                    <Link to="/ops/tanimlar" className="underline text-foreground">
                      Tanım Yönetimi
                    </Link>
                    .
                  </p>
                ) : null}
              </div>
              <div className="sm:col-span-4 px-4 py-2.5 text-[11px] text-muted-foreground">
                Ürün ayarına göre seçilir (tanım tablosu).
              </div>
            </div>
          </div>
      </section>

      {/* SECTION C: LC CURRENCY + MODEL 1 / MODEL 2 + 5-ROW COST TABLE + DYNAMIC SALES CHANNELS */}
      <PortalDataCard contentClassName="p-0 overflow-hidden">
        {/* Preserved Control Row: LC İşlem Dövizi + Model 1 / Model 2 */}
        <div className="px-6 py-4 border-b border-border bg-muted/40 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-xs font-semibold text-foreground whitespace-nowrap">
              LC İşlem Dövizi:
            </label>
            <select
              value={ledger.lcCurrency}
              onChange={(e) =>
                updateLedger({
                  lcCurrency: e.target.value as FxCurrencyCode,
                  metalRateOverride: null,
                  laborRateOverride: null,
                  stoneRateOverride: null,
                  mountingRateOverride: null,
                  otherCostRateOverride: null,
                  supplierRateOverride: null,
                })
              }
              className="px-3 py-1.5 text-xs font-mono font-semibold bg-card border border-border rounded-md text-foreground focus:outline-none focus:border-ring"
            >
              {FX_CURRENCIES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <span className="text-xs text-zinc-600">
              LC Fiyat her zaman burada seçilen para birimine çevrilir.
            </span>
          </div>

          <div className="inline-flex items-center gap-1 p-1 bg-muted rounded-md">
            {(
              [
                { id: '1', label: 'Model 1 · Detaylı (Maden + İşçilik + Taş)' },
                { id: '2', label: 'Model 2 · Sade (Tedarikçi Hazır Fiyatı)' },
              ] as const
            ).map((m) => (
              <Button
                key={m.id}
                type="button"
                size="xs"
                variant={product.pricingMode === m.id ? 'default' : 'ghost'}
                onClick={() => onUpdateProduct({ pricingMode: m.id as PricingMode })}
                className="whitespace-nowrap shrink-0"
              >
                {m.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Main Cost Ledger Table (5 Rows in Model 1 / 1 Row in Model 2) */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-primary text-primary-foreground">
                <th className="py-3 px-5 font-semibold w-[32%]">Maliyet Kalemi</th>
                <th className="py-3 px-3 font-semibold w-[14%]">Para Birimi</th>
                <th className="py-3 px-3 font-semibold text-right w-[18%]">FC Fiyat</th>
                <th className="py-3 px-3 font-semibold text-right w-[16%]">
                  Kur ({`FC → ${lc}`})
                </th>
                <th className="py-3 px-5 font-semibold text-right w-[20%]">
                  LC Fiyat ({lc})
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {product.pricingMode === '1' ? (
                <>
                  {/* ROW 1: MADEN MALİYETİ */}
                  <tr className="bg-card hover:bg-muted/60">
                    <td className="py-3 px-5">
                      <div className="font-semibold text-foreground">Maden Maliyeti</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5 flex flex-wrap items-center gap-2">
                        <span>
                          {ledger.metalFcManual === null
                            ? `Fire Dahil Has Maden (${formatTrNumber(computed.fireIncludedFineMetalGram, 4)} gr) × Has Altın`
                            : 'Elle girildi'}
                        </span>
                        {ledger.metalFcManual !== null && (
                          <button
                            type="button"
                            onClick={() => updateLedger({ metalFcManual: null })}
                            className="text-foreground underline cursor-pointer"
                          >
                            Otomatiğe dön
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <select
                        value={ledger.metalCurrency}
                        onChange={(e) =>
                          updateLedger({
                            metalCurrency: e.target.value as FxCurrencyCode,
                            metalRateOverride: null,
                          })
                        }
                        className={cn(PRICING_FIELD_SELECT_CLASS, 'font-mono')}
                      >
                        {FX_CURRENCIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Input
                        type="number"
                        step="0.01"
                        value={
                          ledger.metalFcManual !== null
                            ? ledger.metalFcManual
                            : Number(computed.ledger.metalAutoFcPrice.toFixed(2))
                        }
                        onChange={(e) =>
                          updateLedger({ metalFcManual: Number(e.target.value) || 0 })
                        }
                        className="w-28 text-right font-mono tabular-nums"
                      />
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="inline-flex items-center justify-end gap-1.5">
                        <Input
                          type="number"
                          step="0.01"
                          value={Number(computed.ledger.metalLine.effectiveRate.toFixed(4))}
                          onChange={(e) =>
                            updateLedger({ metalRateOverride: Number(e.target.value) || 0 })
                          }
                          className={`w-24 text-right px-2 py-1.5 font-mono tabular-nums border rounded-md focus:outline-none ${
                            computed.ledger.metalLine.isRateOverridden
                              ? 'border-ring bg-muted text-foreground'
                              : 'border-border bg-card text-foreground'
                          }`}
                        />
                        {computed.ledger.metalLine.isRateOverridden && (
                          <button
                            type="button"
                            onClick={() => updateLedger({ metalRateOverride: null })}
                            title="Matris kuruna sıfırla"
                            className="p-1 text-muted-foreground hover:text-foreground cursor-pointer"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-5 text-right font-mono font-semibold text-foreground tabular-nums">
                      {formatTrNumber(computed.ledger.metalLine.lcPrice, 2)}
                    </td>
                  </tr>

                  {/* ROW 2: TOPLAM İŞÇİLİK MALİYETİ */}
                  <tr className="bg-card hover:bg-muted/60">
                    <td className="py-3 px-5">
                      <div className="font-semibold text-foreground">Toplam İşçilik Maliyeti</div>
                    </td>
                    <td className="py-3 px-3">
                      <select
                        value={ledger.laborCurrency}
                        onChange={(e) =>
                          updateLedger({
                            laborCurrency: e.target.value as FxCurrencyCode,
                            laborRateOverride: null,
                          })
                        }
                        className={cn(PRICING_FIELD_SELECT_CLASS, 'font-mono')}
                      >
                        {FX_CURRENCIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Input
                        type="number"
                        step="0.5"
                        min={0}
                        value={ledger.laborFcPrice}
                        onChange={(e) =>
                          updateLedger({
                            laborFcPrice: Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        aria-label="Toplam işçilik maliyeti FC fiyat"
                        className="w-28 text-right font-mono tabular-nums"
                      />
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="inline-flex items-center justify-end gap-1.5">
                        <Input
                          type="number"
                          step="0.01"
                          value={Number(computed.ledger.laborLine.effectiveRate.toFixed(4))}
                          onChange={(e) =>
                            updateLedger({ laborRateOverride: Number(e.target.value) || 0 })
                          }
                          className={`w-24 text-right px-2 py-1.5 font-mono tabular-nums border rounded-md focus:outline-none ${
                            computed.ledger.laborLine.isRateOverridden
                              ? 'border-ring bg-muted text-foreground'
                              : 'border-border bg-card text-foreground'
                          }`}
                        />
                        {computed.ledger.laborLine.isRateOverridden && (
                          <button
                            type="button"
                            onClick={() => updateLedger({ laborRateOverride: null })}
                            title="Matris kuruna sıfırla"
                            className="p-1 text-muted-foreground hover:text-foreground cursor-pointer"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-5 text-right font-mono font-semibold text-foreground tabular-nums">
                      {formatTrNumber(computed.ledger.laborLine.lcPrice, 2)}
                    </td>
                  </tr>

                  {/* ROW 3: TAŞ MALİYETİ */}
                  <tr className="bg-card hover:bg-muted/60">
                    <td className="py-3 px-5">
                      <div className="font-semibold text-foreground">Taş Maliyeti</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        {product.stoneType} · {formatTrNumber(computed.totalStoneCarat, 2)} {stoneUnit}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <select
                        value={ledger.stoneCurrency}
                        onChange={(e) =>
                          updateLedger({
                            stoneCurrency: e.target.value as FxCurrencyCode,
                            stoneRateOverride: null,
                          })
                        }
                        className={cn(PRICING_FIELD_SELECT_CLASS, 'font-mono')}
                      >
                        {FX_CURRENCIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Input
                        type="number"
                        step="10"
                        value={ledger.stoneFcPrice}
                        onChange={(e) =>
                          updateLedger({ stoneFcPrice: Math.max(0, Number(e.target.value) || 0) })
                        }
                        className="w-28 text-right font-mono tabular-nums"
                      />
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="inline-flex items-center justify-end gap-1.5">
                        <Input
                          type="number"
                          step="0.01"
                          value={Number(computed.ledger.stoneLine.effectiveRate.toFixed(4))}
                          onChange={(e) =>
                            updateLedger({ stoneRateOverride: Number(e.target.value) || 0 })
                          }
                          className={`w-24 text-right px-2 py-1.5 font-mono tabular-nums border rounded-md focus:outline-none ${
                            computed.ledger.stoneLine.isRateOverridden
                              ? 'border-ring bg-muted text-foreground'
                              : 'border-border bg-card text-foreground'
                          }`}
                        />
                        {computed.ledger.stoneLine.isRateOverridden && (
                          <button
                            type="button"
                            onClick={() => updateLedger({ stoneRateOverride: null })}
                            title="Matris kuruna sıfırla"
                            className="p-1 text-muted-foreground hover:text-foreground cursor-pointer"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-5 text-right font-mono font-semibold text-foreground tabular-nums">
                      {formatTrNumber(computed.ledger.stoneLine.lcPrice, 2)}
                    </td>
                  </tr>

                  {/* ROW 4: MONTÜR MALİYETİ */}
                  <tr className="bg-card hover:bg-muted/60">
                    <td className="py-3 px-5">
                      <div className="font-semibold text-foreground">Montür Maliyeti</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        Varsa hazır montür / döküm dış alım bedeli
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <select
                        value={ledger.mountingCurrency}
                        onChange={(e) =>
                          updateLedger({
                            mountingCurrency: e.target.value as FxCurrencyCode,
                            mountingRateOverride: null,
                          })
                        }
                        className={cn(PRICING_FIELD_SELECT_CLASS, 'font-mono')}
                      >
                        {FX_CURRENCIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Input
                        type="number"
                        step="10"
                        value={ledger.mountingFcPrice}
                        onChange={(e) =>
                          updateLedger({
                            mountingFcPrice: Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        className="w-28 text-right font-mono tabular-nums"
                      />
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="inline-flex items-center justify-end gap-1.5">
                        <Input
                          type="number"
                          step="0.01"
                          value={Number(computed.ledger.mountingLine.effectiveRate.toFixed(4))}
                          onChange={(e) =>
                            updateLedger({ mountingRateOverride: Number(e.target.value) || 0 })
                          }
                          className={`w-24 text-right px-2 py-1.5 font-mono tabular-nums border rounded-md focus:outline-none ${
                            computed.ledger.mountingLine.isRateOverridden
                              ? 'border-ring bg-muted text-foreground'
                              : 'border-border bg-card text-foreground'
                          }`}
                        />
                        {computed.ledger.mountingLine.isRateOverridden && (
                          <button
                            type="button"
                            onClick={() => updateLedger({ mountingRateOverride: null })}
                            title="Matris kuruna sıfırla"
                            className="p-1 text-muted-foreground hover:text-foreground cursor-pointer"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-5 text-right font-mono font-semibold text-foreground tabular-nums">
                      {computed.ledger.mountingLine.lcPrice > 0
                        ? formatTrNumber(computed.ledger.mountingLine.lcPrice, 2)
                        : '—'}
                    </td>
                  </tr>

                  {/* ROW 5: DİĞER MALİYETLER */}
                  <tr className="bg-card hover:bg-muted/60">
                    <td className="py-3 px-5">
                      <div className="font-semibold text-foreground">Diğer Maliyetler</div>
                      <div className="text-[11px] text-muted-foreground mt-0.5">
                        Sertifika, rodaj, kutu, ambalaj veya ek işçilik kalemleri
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <select
                        value={ledger.otherCostCurrency}
                        onChange={(e) =>
                          updateLedger({
                            otherCostCurrency: e.target.value as FxCurrencyCode,
                            otherCostRateOverride: null,
                          })
                        }
                        className={cn(PRICING_FIELD_SELECT_CLASS, 'font-mono')}
                      >
                        {FX_CURRENCIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Input
                        type="number"
                        step="10"
                        value={ledger.otherCostFcPrice}
                        onChange={(e) =>
                          updateLedger({
                            otherCostFcPrice: Math.max(0, Number(e.target.value) || 0),
                          })
                        }
                        className="w-28 text-right font-mono tabular-nums"
                      />
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="inline-flex items-center justify-end gap-1.5">
                        <Input
                          type="number"
                          step="0.01"
                          value={Number(computed.ledger.otherCostLine.effectiveRate.toFixed(4))}
                          onChange={(e) =>
                            updateLedger({ otherCostRateOverride: Number(e.target.value) || 0 })
                          }
                          className={`w-24 text-right px-2 py-1.5 font-mono tabular-nums border rounded-md focus:outline-none ${
                            computed.ledger.otherCostLine.isRateOverridden
                              ? 'border-ring bg-muted text-foreground'
                              : 'border-border bg-card text-foreground'
                          }`}
                        />
                        {computed.ledger.otherCostLine.isRateOverridden && (
                          <button
                            type="button"
                            onClick={() => updateLedger({ otherCostRateOverride: null })}
                            title="Matris kuruna sıfırla"
                            className="p-1 text-muted-foreground hover:text-foreground cursor-pointer"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-5 text-right font-mono font-semibold text-foreground tabular-nums">
                      {computed.ledger.otherCostLine.lcPrice > 0
                        ? formatTrNumber(computed.ledger.otherCostLine.lcPrice, 2)
                        : '—'}
                    </td>
                  </tr>
                </>
              ) : (
                /* MODEL 2: AUTOMATIC REFERENCE METAL COST + SINGLE SUPPLIER LINE */
                (() => {
                  const autoMetalTry =
                    computed.fireIncludedFineMetalGram * rates.liveHasGoldTrySell;
                  const supplierFcTryRate = rates.fxBaseRates[ledger.supplierCurrency] ?? 1;
                  const autoMetalInSupplierFc =
                    supplierFcTryRate > 0 ? autoMetalTry / supplierFcTryRate : 0;
                  const autoMetalInLc =
                    computed.ledger.lcToTryRate > 0
                      ? autoMetalTry / computed.ledger.lcToTryRate
                      : 0;
                  const diffFromMetalLc = computed.ledger.supplierLine.lcPrice - autoMetalInLc;
                  const isBelowMetalCost = diffFromMetalLc < -0.01;

                  return (
                    <>
                      {/* Reference Row: Otomatik Maden Maliyeti (Toplam Maliyete Eklenmez) */}
                      <tr className="bg-muted">
                        <td className="py-3 px-5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-foreground">Maden Maliyeti</span>
                            <span className="text-[11px] font-medium text-foreground">
                              (Referans · Otomatik)
                            </span>
                          </div>
                          <div className="text-[11px] text-muted-foreground mt-0.5">
                            Fire Dahil Has Maden (
                            {formatTrNumber(computed.fireIncludedFineMetalGram, 4)} gr) × Has Altın (
                            {formatTrNumber(rates.liveHasGoldTrySell, 2)} TL/gr) · Bilgi amaçlıdır,
                            toplama ayrıca eklenmez
                          </div>
                        </td>
                        <td className="py-3 px-3 font-mono text-xs text-foreground">
                          {ledger.supplierCurrency}
                        </td>
                        <td className="py-3 px-3 text-right font-mono font-medium text-foreground tabular-nums">
                          {formatTrNumber(autoMetalInSupplierFc, 2)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-zinc-600 tabular-nums">
                          {formatTrNumber(computed.ledger.supplierLine.effectiveRate, 4)}
                        </td>
                        <td className="py-3 px-5 text-right font-mono font-semibold text-foreground tabular-nums">
                          {formatTrNumber(autoMetalInLc, 2)}
                        </td>
                      </tr>

                      {/* Editable Supplier Ready Price Row */}
                      <tr className="bg-card hover:bg-muted/60">
                        <td className="py-3.5 px-5">
                          <div className="font-semibold text-foreground">
                            Tedarikçi Hazır Satış Bedeli (Model 2)
                          </div>
                          <div className="text-[11px] mt-0.5 flex flex-wrap items-center gap-2">
                            {isBelowMetalCost ? (
                              <>
                                <span className="text-muted-foreground font-medium">
                                  Girilen fiyat referans maden maliyetinin altında (
                                  {formatTrNumber(diffFromMetalLc, 2)} {lc}).
                                </span>
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateLedger({
                                      supplierFcPrice: Number(autoMetalInSupplierFc.toFixed(2)),
                                    })
                                  }
                                  className="text-foreground underline hover:text-black cursor-pointer"
                                >
                                  Maden maliyetini baz al
                                </button>
                              </>
                            ) : (
                              <span className="text-muted-foreground">
                                Maden üstü işçilik/taş/tedarik farkı:{' '}
                                <strong className="font-mono text-foreground">
                                  +{formatTrNumber(diffFromMetalLc, 2)} {lc}
                                </strong>
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-3">
                          <select
                            value={ledger.supplierCurrency}
                            onChange={(e) =>
                              updateLedger({
                                supplierCurrency: e.target.value as FxCurrencyCode,
                                supplierRateOverride: null,
                              })
                            }
                            className={cn(PRICING_FIELD_SELECT_CLASS, 'font-mono')}
                          >
                            {FX_CURRENCIES.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-3.5 px-3 text-right">
                          <Input
                            type="number"
                            step="10"
                            value={ledger.supplierFcPrice}
                            onChange={(e) =>
                              updateLedger({
                                supplierFcPrice: Math.max(0, Number(e.target.value) || 0),
                              })
                            }
                            className="w-28 text-right font-mono tabular-nums"
                          />
                        </td>
                        <td className="py-3.5 px-3 text-right">
                          <div className="inline-flex items-center justify-end gap-1.5">
                            <Input
                              type="number"
                              step="0.01"
                              value={Number(computed.ledger.supplierLine.effectiveRate.toFixed(4))}
                              onChange={(e) =>
                                updateLedger({ supplierRateOverride: Number(e.target.value) || 0 })
                              }
                              className={`w-24 text-right px-2 py-1.5 font-mono tabular-nums border rounded-md ${
                                computed.ledger.supplierLine.isRateOverridden
                                  ? 'border-ring bg-muted text-foreground'
                                  : 'border-border bg-card text-foreground'
                              }`}
                            />
                            {computed.ledger.supplierLine.isRateOverridden && (
                              <button
                                type="button"
                                onClick={() => updateLedger({ supplierRateOverride: null })}
                                title="Matris kuruna sıfırla"
                                className="p-1 text-muted-foreground hover:text-foreground cursor-pointer"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-5 text-right font-mono font-semibold text-foreground tabular-nums">
                          {formatTrNumber(computed.ledger.supplierLine.lcPrice, 2)}
                        </td>
                      </tr>
                    </>
                  );
                })()
              )}

              <tr className="bg-muted text-foreground">
                <td colSpan={4} className="py-3.5 px-5 font-semibold text-sm">
                  Toplam Maliyet ({lc})
                </td>
                <td className="py-3.5 px-5 text-right font-mono text-base font-bold tabular-nums">
                  {formatTrNumber(computed.ledger.totalCostLc, 2)} {lc}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Fire Method Note */}
        <div className="px-6 py-2.5 bg-card border-t border-border text-[11px] italic text-muted-foreground">
          Not: Hesaplama {PURITY_MAP[product.purityCode]?.label ?? product.purityCode} ({formatTrNumber(computed.millesimalFineness || resolveFineness(product.purityCode), 3)}) ve net ağırlık üzerinden %{formatTrNumber(product.fireRatePct, 2)} fire yöntemiyle hazırlanmıştır. Fire oranı işletme/üretim yöntemine göre değiştirilebilir.
        </div>

        {/* DYNAMIC SALES CHANNEL PRICING RULES (B2B / B2B_API / B2C_API — hardcoded) */}
        <div className="border-t border-border bg-muted/40 px-6 py-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">
                Satış Kanalları · Kâr, İndirim ve Komisyon Kuralları
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Sabit kanallar: <strong>B2B</strong>, <strong>B2B API</strong>,{' '}
                <strong>B2C API</strong>. Operasyon akışına bağlıdır; serbest kanal eklenemez.
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {canAddMoreChannels ? (
                <Button
                  type="button"
                  size="sm"
                  variant="success"
                  onClick={() => handleAddChannelRule()}
                  className="whitespace-nowrap"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Satış Kanalı Ekle
                </Button>
              ) : (
                <span className="text-xs text-muted-foreground font-medium whitespace-nowrap">
                  Tüm kanallar tanımlı (B2B · B2B API · B2C API)
                </span>
              )}
            </div>
          </div>

          {ledger.channelRules.length === 0 ? (
            <div className="bg-card border border-dashed border-border rounded-lg p-8 text-center space-y-3">
              <div className="text-sm font-semibold text-foreground">
                Henüz satış kanalı eklenmedi
              </div>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                Bu ürün için fiyat oluşturmak üzere B2B, B2B API veya B2C API kanalını ekleyin.
              </p>
              <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
                <Button
                  type="button"
                  size="sm"
                  variant="success"
                  onClick={() => handleAddChannelRule('B2B')}
                >
                  <Plus className="w-3.5 h-3.5" />
                  B2B Ekle
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="success"
                  onClick={() => handleAddChannelRule('B2B_API')}
                >
                  <Plus className="w-3.5 h-3.5" />
                  B2B API Ekle
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="success"
                  onClick={() => handleAddChannelRule('B2C_API')}
                >
                  <Plus className="w-3.5 h-3.5" />
                  B2C API Ekle
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {ledger.channelRules.map((rule, idx) => {
                const calc = computed.ledger.channels.find((c) => c.id === rule.id);
                const otherChannels = new Set(
                  ledger.channelRules.filter((r) => r.id !== rule.id).map((r) => r.channel)
                );
                const channelDisplayName =
                  rule.channel === 'B2B'
                    ? 'B2B Satış Fiyatı (Bayi Portalı)'
                    : rule.channel === 'B2B_API'
                      ? 'B2B API Satış Fiyatı'
                      : 'B2C API Satış Fiyatı';

                return (
                  <div
                    key={rule.id}
                    className="bg-card border border-border rounded-lg overflow-hidden"
                  >
                    {/* Channel Card Header */}
                    <div className="px-5 py-3 bg-muted/60 border-b border-border flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-mono text-[11px] text-zinc-400">
                          Kanal #{idx + 1}
                        </span>
                        <select
                          value={rule.channel}
                          onChange={(e) =>
                            handleUpdateChannelRule(rule.id, {
                              channel: e.target.value as PricingChannelTarget,
                            })
                          }
                          aria-label="Satış kanalı seçimi"
                          className="px-3 py-1.5 text-xs font-semibold bg-card border border-border rounded-md text-foreground focus:outline-none focus:border-ring"
                        >
                          <option value="B2B" disabled={otherChannels.has('B2B')}>
                            B2B (Bayi Portalı)
                          </option>
                          <option value="B2B_API" disabled={otherChannels.has('B2B_API')}>
                            B2B API
                          </option>
                          <option value="B2C_API" disabled={otherChannels.has('B2C_API')}>
                            B2C API
                          </option>
                        </select>
                      </div>

                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <span className="text-[11px] text-muted-foreground mr-2">Nihai:</span>
                          <span className="font-mono text-sm font-bold text-foreground tabular-nums">
                            {formatTrNumber(calc?.finalPriceLc ?? 0, 2)} {lc}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveChannelRule(rule.id)}
                          title="Bu satış kanalını kaldır"
                          data-delete="true"
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs text-destructive hover:bg-destructive/10 rounded-md transition-colors cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Sil
                        </button>
                      </div>
                    </div>

                    {/* Channel Ledger Rows */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <tbody className="divide-y divide-border">
                          {/* Row 1: Satış Kârı */}
                          <tr className="hover:bg-muted/50">
                            <td className="py-2.5 px-5 font-medium text-foreground w-[32%]">
                              Satış Kârı
                            </td>
                            <td className="py-2.5 px-3 w-[14%]">
                              <select
                                value={rule.profit.unit}
                                onChange={(e) =>
                                  handleUpdateChannelRule(rule.id, {
                                    profit: {
                                      ...rule.profit,
                                      unit: e.target.value as AdjustmentUnit,
                                    },
                                  })
                                }
                                className="px-2.5 py-1.5 font-mono text-xs bg-muted border border-border rounded-md"
                              >
                                {ADJUSTMENT_UNITS.map((u) => (
                                  <option key={u} value={u}>
                                    {u}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono text-zinc-400 w-[18%]">
                              {rule.profit.unit === '%' ? 'Maliyet %' : 'Sabit Tutar'}
                            </td>
                            <td className="py-2.5 px-3 text-right w-[16%]">
                              <Input
                                type="number"
                                step={rule.profit.unit === '%' ? '0.5' : '100'}
                                value={rule.profit.value}
                                onChange={(e) =>
                                  handleUpdateChannelRule(rule.id, {
                                    profit: {
                                      ...rule.profit,
                                      value: Math.max(0, Number(e.target.value) || 0),
                                    },
                                  })
                                }
                                className="w-28 text-right font-mono tabular-nums"
                              />
                            </td>
                            <td className="py-2.5 px-5 text-right font-mono font-medium text-foreground tabular-nums w-[20%]">
                              + {formatTrNumber(calc?.profitLc ?? 0, 2)}
                            </td>
                          </tr>

                          {/* Row 2: Satış İndirimi */}
                          <tr className="hover:bg-muted/50">
                            <td className="py-2.5 px-5 font-medium text-foreground">
                              Satış İndirimi
                            </td>
                            <td className="py-2.5 px-3">
                              <select
                                value={rule.discount.unit}
                                onChange={(e) =>
                                  handleUpdateChannelRule(rule.id, {
                                    discount: {
                                      ...rule.discount,
                                      unit: e.target.value as AdjustmentUnit,
                                    },
                                  })
                                }
                                className="px-2.5 py-1.5 font-mono text-xs bg-muted border border-border rounded-md"
                              >
                                {ADJUSTMENT_UNITS.map((u) => (
                                  <option key={u} value={u}>
                                    {u}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono text-zinc-400">
                              {rule.discount.unit === '%' ? 'Satış %' : 'Sabit Tutar'}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <Input
                                type="number"
                                step={rule.discount.unit === '%' ? '0.5' : '50'}
                                value={rule.discount.value}
                                onChange={(e) =>
                                  handleUpdateChannelRule(rule.id, {
                                    discount: {
                                      ...rule.discount,
                                      value: Math.max(0, Number(e.target.value) || 0),
                                    },
                                  })
                                }
                                className="w-28 text-right font-mono tabular-nums"
                              />
                            </td>
                            <td className="py-2.5 px-5 text-right font-mono font-medium text-muted-foreground tabular-nums">
                              − {formatTrNumber(calc?.discountLc ?? 0, 2)}
                            </td>
                          </tr>

                          <tr className="bg-muted text-foreground">
                            <td colSpan={4} className="py-2 px-5 font-semibold">
                              Toplam Satış (İndirim Sonrası)
                            </td>
                            <td className="py-2 px-5 text-right font-mono font-semibold tabular-nums">
                              {formatTrNumber(calc?.totalSalesLc ?? 0, 2)} {lc}
                            </td>
                          </tr>

                          {/* Row 3: Platform Servis / Komisyon Bedeli */}
                          <tr className="hover:bg-muted/50">
                            <td className="py-2.5 px-5 font-medium text-foreground">
                              Platform Servis / Komisyon Bedeli
                            </td>
                            <td className="py-2.5 px-3">
                              <select
                                value={rule.platformFee.unit}
                                onChange={(e) =>
                                  handleUpdateChannelRule(rule.id, {
                                    platformFee: {
                                      ...rule.platformFee,
                                      unit: e.target.value as AdjustmentUnit,
                                    },
                                  })
                                }
                                className="px-2.5 py-1.5 font-mono text-xs bg-muted border border-border rounded-md"
                              >
                                {ADJUSTMENT_UNITS.map((u) => (
                                  <option key={u} value={u}>
                                    {u}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono text-zinc-400">
                              {rule.platformFee.unit === '%' ? 'Maliyet %' : 'Sabit Tutar'}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <Input
                                type="number"
                                step={rule.platformFee.unit === '%' ? '0.25' : '50'}
                                value={rule.platformFee.value}
                                onChange={(e) =>
                                  handleUpdateChannelRule(rule.id, {
                                    platformFee: {
                                      ...rule.platformFee,
                                      value: Math.max(0, Number(e.target.value) || 0),
                                    },
                                  })
                                }
                                className="w-28 text-right font-mono tabular-nums"
                              />
                            </td>
                            <td className="py-2.5 px-5 text-right font-mono font-medium text-foreground tabular-nums">
                              + {formatTrNumber(calc?.platformFeeLc ?? 0, 2)}
                            </td>
                          </tr>

                          {/* Final Channel Price Row — full row uses theme primary contrast */}
                          <tr className="bg-primary text-primary-foreground">
                            <td colSpan={3} className="py-3 px-5 font-semibold text-sm">
                              {channelDisplayName}
                            </td>
                            <td className="py-3 px-3 text-right font-mono text-xs tabular-nums text-primary-foreground/70">
                              {lc !== 'TRY'
                                ? `${formatTrNumber(calc?.finalPriceTry ?? 0, 2)} TL`
                                : rule.channel === 'B2B'
                                  ? formatCurrencyValue(computed.finalB2bPriceCurrency, 'USD')
                                  : `Liste: ${formatTrNumber(calc?.listPriceTry ?? 0, 2)} TL`}
                            </td>
                            <td className="py-3 px-5 text-right font-mono text-base font-bold tabular-nums">
                              {formatTrNumber(calc?.finalPriceLc ?? 0, 2)} {lc}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}

              {canAddMoreChannels && (
                <Button
                  type="button"
                  variant="success"
                  onClick={() => handleAddChannelRule()}
                  className="w-full h-auto min-h-11 py-3"
                >
                  <Plus className="w-3.5 h-3.5" />
                  {!hasB2cApiRule
                    ? 'B2C Satış Kanalı Ekle (Perakende Fiyatı Ayrıca Tanımla)'
                    : 'B2B Satış Kanalı Ekle (Bayi Fiyatını Ayrıca Tanımla)'}
                </Button>
              )}
            </div>
          )}
        </div>
      </PortalDataCard>
    </div>
  );
}

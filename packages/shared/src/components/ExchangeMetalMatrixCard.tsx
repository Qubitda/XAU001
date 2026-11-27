import { ReactNode, useLayoutEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Globe } from 'lucide-react';
import { PortalDataCard } from './portal';
import { Button, Input } from './ui';
import { FxCurrencyCode, LiveRates } from '../types/jewelry';
import {
  FX_CURRENCIES,
  formatTrNumber,
  getMatrixRate,
} from '../utils/pricingEngine';

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

interface ExchangeMetalMatrixCardProps {
  rates: LiveRates;
  onBaseRateChange: (code: FxCurrencyCode, newTryValue: number) => void;
  defaultExpanded?: boolean;
  readOnly?: boolean;
}

export function ExchangeMetalMatrixCard({
  rates,
  onBaseRateChange,
  defaultExpanded = true,
  readOnly = false,
}: ExchangeMetalMatrixCardProps) {
  const [matrixExpanded, setMatrixExpanded] = useState<boolean>(defaultExpanded);

  return (
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
                  disabled={readOnly}
                  value={val}
                  onChange={(e) =>
                    onBaseRateChange(code, parseFloat(e.target.value) || 0)
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
                                      disabled={readOnly}
                                      value={rowVal}
                                      onChange={(e) =>
                                        onBaseRateChange(
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
  );
}

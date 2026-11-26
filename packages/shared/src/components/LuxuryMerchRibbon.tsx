interface LuxuryMerchRibbonProps {
  discountPct: number;
  isNewCollection: boolean;
  size?: 'card' | 'detail';
}

/**
 * Product image discount badge — compact red tilted sticker.
 * Always shows whole-number % (no decimals).
 */
export function LuxuryMerchRibbon({
  discountPct,
  isNewCollection,
  size = 'card',
}: LuxuryMerchRibbonProps) {
  void isNewCollection;
  if (discountPct <= 0) return null;

  const pct = Math.max(1, Math.round(discountPct));
  const isDetail = size === 'detail';

  return (
    <div
      aria-label={`%${pct} Sepet İndirimi`}
      className={`pointer-events-none absolute top-2 left-2 z-20 select-none ${
        isDetail ? 'origin-top-left scale-[1.05]' : ''
      }`}
    >
      <div
        className="rotate-[8deg] rounded-[7px] bg-[#E31C23] text-white shadow-[0_3px_10px_rgba(180,20,28,0.32)] px-[7px] py-[5px] leading-none"
      >
        <div className="flex items-center gap-[5px]">
          <span className="text-[13px] font-extrabold tabular-nums tracking-tight">
            %{pct}
          </span>
          <span className="relative inline-flex items-center justify-center shrink-0">
            {/* Simple cart glyph matching reference sticker */}
            <svg
              width="12"
              height="12"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
              className="block"
            >
              <path
                d="M1.2 1.4h1.5l.35 1.2h10.4l-1.15 5.2H4.05L3.55 5.1"
                stroke="white"
                strokeWidth="1.35"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="5.2" cy="13.1" r="1.15" fill="white" />
              <circle cx="11.3" cy="13.1" r="1.15" fill="white" />
            </svg>
            {/* Motion / sparkle ticks */}
            <span aria-hidden="true" className="absolute -top-[3px] -right-[4px]">
              <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                <path d="M7.2 1.1 L4.6 2.2" stroke="white" strokeWidth="1" strokeLinecap="round" />
                <path d="M7.4 2.8 L4.9 3.2" stroke="white" strokeWidth="1" strokeLinecap="round" />
                <path d="M6.6 4.3 L4.6 4.1" stroke="white" strokeWidth="1" strokeLinecap="round" />
              </svg>
            </span>
          </span>
        </div>
        <div className="mt-[4px] text-[7.5px] font-bold tracking-[0.01em] whitespace-nowrap">
          Sepet İndirimi
        </div>
      </div>
    </div>
  );
}

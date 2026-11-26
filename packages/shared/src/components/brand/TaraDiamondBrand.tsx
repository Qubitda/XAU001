interface TaraStarMarkProps {
  className?: string;
}

/**
 * TARA DIAMOND signature four-pointed faceted star emblem.
 * Preserves the sculptural chamfered diamond-star geometry from the brand guidelines.
 */
export function TaraStarMark({ className = 'w-6 h-6' }: TaraStarMarkProps) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Top-left bright gold facet */}
      <path d="M20 2 L20 20 L16 16 Z" fill="#D5BC8E" />
      <path d="M2 20 L20 20 L16 16 Z" fill="#C7AA77" />
      {/* Top-right warm champagne facet */}
      <path d="M20 2 L24 16 L20 20 Z" fill="#A98955" />
      <path d="M38 20 L24 16 L20 20 Z" fill="#9A7A46" />
      {/* Bottom-left satin gold facet */}
      <path d="M2 20 L16 24 L20 20 Z" fill="#B89A68" />
      <path d="M20 38 L16 24 L20 20 Z" fill="#9E7F4D" />
      {/* Bottom-right deep bronze-gold facet */}
      <path d="M38 20 L20 20 L24 24 Z" fill="#7D6237" />
      <path d="M20 38 L20 20 L24 24 Z" fill="#8D7040" />
    </svg>
  );
}

interface TaraDiamondLogoProps {
  variant?: 'horizontal' | 'stacked';
  tone?: 'dark' | 'light';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function TaraDiamondLogo({
  variant = 'horizontal',
  tone = 'dark',
  size = 'md',
  className = '',
}: TaraDiamondLogoProps) {
  const titleColor = tone === 'light' ? 'text-primary-foreground' : 'text-foreground';
  const subColor = tone === 'light' ? 'text-primary-foreground/70' : 'text-muted-foreground';
  const lineColor = tone === 'light' ? 'bg-primary-foreground/40' : 'bg-border';

  const starSize =
    size === 'sm' ? 'w-6 h-6' : size === 'lg' ? 'w-9 h-9' : 'w-7 h-7 sm:w-8 sm:h-8';
  const taraTextSize =
    size === 'sm'
      ? 'text-[17px] tracking-[0.22em]'
      : size === 'lg'
        ? 'text-[26px] tracking-[0.24em]'
        : 'text-[19px] sm:text-[22px] tracking-[0.24em]';
  const diamondTextSize =
    size === 'sm'
      ? 'text-[7.5px] tracking-[0.36em]'
      : size === 'lg'
        ? 'text-[10px] tracking-[0.42em]'
        : 'text-[8.5px] sm:text-[9px] tracking-[0.38em]';

  if (variant === 'stacked') {
    return (
      <div className={`inline-flex flex-col items-center select-none ${className}`}>
        <TaraStarMark className={starSize} />
        <span className={`font-serif font-medium leading-none mt-1.5 ${taraTextSize} ${titleColor}`}>
          TARA
        </span>
        <span className="inline-flex items-center gap-2 mt-1">
          <span className={`w-3.5 h-px ${lineColor}`} aria-hidden="true" />
          <span className={`font-sans uppercase leading-none ${diamondTextSize} ${subColor}`}>
            DIAMOND
          </span>
          <span className={`w-3.5 h-px ${lineColor}`} aria-hidden="true" />
        </span>
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 sm:gap-2.5 select-none ${className}`}>
      <TaraStarMark className={`${starSize} shrink-0`} />
      <div className="flex flex-col items-center leading-none">
        <span className={`font-serif font-medium leading-none ${taraTextSize} ${titleColor}`}>
          TARA
        </span>
        <span className={`font-sans uppercase leading-none mt-1 ${diamondTextSize} ${subColor}`}>
          DIAMOND
        </span>
      </div>
    </div>
  );
}

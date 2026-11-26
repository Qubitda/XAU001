/**
 * Storefront presentational primitives (B2C).
 * Colors: Design System semantic tokens (see packages/shared/src/styles/).
 */
import { type ReactNode, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronRight, Heart, ShoppingBag } from 'lucide-react';
import type { ComputedJewelryMetrics, MetalColor, ProductState } from '../../../types/jewelry';
import {
  resolveProductMedia,
  type ResolvedProductMedia,
} from '../../../data/productMedia';
import { JewelryIllustration } from '../../../components/JewelryIllustration';
import { LuxuryMerchRibbon } from '../../../components/LuxuryMerchRibbon';
import { formatTrNumber } from '../../../utils/pricingEngine';
import { cn } from '../../../lib/utils';

export const TARA_INPUT_CLASS =
  'w-full h-11 px-3.5 rounded-md border border-input bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25 transition-colors';

export const TARA_SELECT_CLASS =
  'h-10 px-3 rounded-md border border-input bg-muted text-xs font-medium text-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25 transition-colors cursor-pointer';

export const TARA_SEARCH_INPUT_CLASS =
  'w-full h-10 pl-9 pr-8 rounded-md border border-input bg-muted text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25 transition-colors';

export const TARA_PRIMARY_BTN_CLASS =
  'inline-flex items-center justify-center gap-2 min-h-[44px] px-5 rounded-md bg-primary text-primary-foreground text-xs sm:text-[13px] font-medium hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-45 disabled:pointer-events-none transition-colors cursor-pointer whitespace-nowrap';

export const TARA_SUCCESS_BTN_CLASS =
  'inline-flex items-center justify-center gap-2 min-h-[40px] px-4 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-45 disabled:pointer-events-none transition-colors cursor-pointer whitespace-nowrap';

export const TARA_SECONDARY_BTN_CLASS =
  'inline-flex items-center justify-center gap-2 min-h-[40px] px-4 rounded-md border border-border bg-card text-foreground text-xs font-medium hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-45 disabled:pointer-events-none transition-colors cursor-pointer whitespace-nowrap';

export interface BreadcrumbItem {
  label: string;
  to?: string;
  onClick?: () => void;
}

export function StorefrontBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav
      aria-label="Sayfa yolu"
      className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground"
    >
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        return (
          <span key={`${item.label}-${idx}`} className="inline-flex items-center gap-1.5 min-w-0">
            {idx > 0 && (
              <ChevronRight className="w-3 h-3 text-ring shrink-0" aria-hidden="true" />
            )}
            {isLast ? (
              <span className="text-foreground font-medium truncate">{item.label}</span>
            ) : item.to ? (
              <Link
                to={item.to}
                className="hover:text-foreground transition-colors truncate"
              >
                {item.label}
              </Link>
            ) : item.onClick ? (
              <button
                type="button"
                onClick={item.onClick}
                className="hover:text-foreground transition-colors truncate cursor-pointer"
              >
                {item.label}
              </button>
            ) : (
              <span className="truncate">{item.label}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}

export interface StorefrontPageHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  breadcrumb?: BreadcrumbItem[];
  actions?: ReactNode;
}

export function StorefrontPageHeader({
  eyebrow,
  title,
  subtitle,
  breadcrumb,
  actions,
}: StorefrontPageHeaderProps) {
  return (
    <header className="space-y-4">
      {breadcrumb && breadcrumb.length > 0 ? <StorefrontBreadcrumb items={breadcrumb} /> : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between border-b border-border pb-5">
        <div className="min-w-0 space-y-2">
          {eyebrow ? (
            <p className="text-xs font-medium tracking-[0.12em] uppercase text-muted-foreground">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="text-[32px] sm:text-[40px] font-medium text-foreground leading-[1.1]">
            {title}
          </h1>
          {subtitle ? (
            <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">{subtitle}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>
        ) : null}
      </div>
    </header>
  );
}

interface StorefrontEmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function StorefrontEmptyState({
  icon,
  title,
  description,
  action,
}: StorefrontEmptyStateProps) {
  return (
    <div className="rounded-md border border-border bg-muted/40 py-14 px-6 text-center space-y-3">
      {icon ? <div className="flex justify-center text-ring">{icon}</div> : null}
      <h2 className="text-2xl font-medium text-foreground">{title}</h2>
      {description ? (
        <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
          {description}
        </p>
      ) : null}
      {action ? <div className="pt-2 flex justify-center">{action}</div> : null}
    </div>
  );
}

export type StorefrontProductCardVariant = 'default' | 'collection';

interface StorefrontProductCardProps {
  product: ProductState;
  metrics: ComputedJewelryMetrics;
  media: ResolvedProductMedia;
  activeColor?: MetalColor;
  isFavorite?: boolean;
  isAdded?: boolean;
  showColorSwatches?: boolean;
  showQuickAdd?: boolean;
  variant?: StorefrontProductCardVariant;
  onOpen: () => void;
  onSelectColor?: (color: MetalColor) => void;
  onToggleFavorite?: () => void;
  onQuickAdd?: () => void;
}

export function StorefrontProductCard({
  product,
  metrics,
  media,
  activeColor,
  isFavorite = false,
  isAdded = false,
  showColorSwatches = false,
  showQuickAdd = true,
  variant = 'default',
  onOpen,
  onSelectColor,
  onToggleFavorite,
  onQuickAdd,
}: StorefrontProductCardProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const [hoverFailed, setHoverFailed] = useState(false);

  const displayColor = activeColor ?? product.metalColor;
  // Always bind image + tone filter to the visible metal color (home = collection)
  const displayMedia = resolveProductMedia(
    product.parentSku,
    displayColor,
    product.galleryImages
  );
  const resolvedMedia = displayMedia.mainUrl ? displayMedia : media;

  useEffect(() => {
    setImgFailed(false);
    setHoverFailed(false);
  }, [displayColor, resolvedMedia.mainUrl, resolvedMedia.hoverUrl]);
  const isOutOfStock = product.stockStatus === 'Tükendi';
  const hasDiscount = metrics.ledger.hasB2cChannel && metrics.discountAmountTry > 0;
  const isCollectionLayout = variant === 'collection';
  const variantTotal =
    product.variants && product.variants.length > 0
      ? product.variants.length
      : product.availableColors.length;

  const activeDiscountPct =
    metrics.ledger.hasB2cChannel && metrics.discountAmountTry > 0
      ? metrics.ledger.effectiveB2cDiscountPct
      : 0;

  const mediaFrameClass = isCollectionLayout
    ? 'relative h-[220px] sm:h-[260px] xl:h-[280px] bg-muted rounded-sm overflow-hidden cursor-pointer'
    : 'relative aspect-[4/3] bg-muted overflow-hidden cursor-pointer';

  const articleClass = isCollectionLayout
    ? 'group flex h-full flex-col gap-3'
    : 'group bg-card border border-border rounded-md overflow-hidden flex h-full flex-col hover:border-ring transition-colors';

  const collectionMeta = `${product.purityCode} ${displayColor}${
    metrics.totalStoneCarat > 0 ? ` · ${formatTrNumber(metrics.totalStoneCarat, 2)} ct` : ''
  }`;

  const stockStatusClass =
    product.stockStatus === 'Stokta'
      ? 'text-foreground'
      : product.stockStatus === 'Tükendi'
        ? 'text-destructive'
        : 'text-muted-foreground';

  const swatches =
    showColorSwatches && onSelectColor && product.availableColors.length > 0 ? (
      <div className={isCollectionLayout ? 'flex items-center gap-2' : 'pt-2 flex items-center gap-2'}>
        {product.availableColors.slice(0, 3).map((color) => {
          const dotBg =
            color === 'Beyaz'
              ? 'bg-gradient-to-br from-[#F4F3F1] to-[#CFCBC4]'
              : color === 'Sarı'
                ? 'bg-gradient-to-br from-[#F4DF9B] to-[#C89D3C]'
                : 'bg-gradient-to-br from-[#F1C7B8] to-[#BF7E68]';
          const isCurrent = displayColor === color;
          return (
            <button
              key={color}
              type="button"
              aria-label={`${product.title} — ${color} Altın önizle`}
              onClick={(e) => {
                e.stopPropagation();
                setImgFailed(false);
                setHoverFailed(false);
                onSelectColor(color);
              }}
              className={cn(
                'w-3.5 h-3.5 rounded-full border transition-transform cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                dotBg,
                isCurrent
                  ? 'border-foreground scale-110 ring-2 ring-ring/40'
                  : 'border-border hover:scale-105'
              )}
            />
          );
        })}
        {!isCollectionLayout ? (
          <span className="text-[11px] text-muted-foreground ml-0.5">{displayColor}</span>
        ) : null}
      </div>
    ) : null;

  const mediaStage = (
    <>
      <LuxuryMerchRibbon
        discountPct={activeDiscountPct}
        isNewCollection={false}
        size="card"
      />

      {onToggleFavorite ? (
        <button
          type="button"
          aria-label={isFavorite ? 'Favorilerden çıkar' : 'Favorilere ekle'}
          onClick={(e) => {
            e.stopPropagation();
            onToggleFavorite();
          }}
          className={cn(
            'absolute top-3 right-3 z-20 w-8 h-8 rounded-full bg-card/95 border border-border flex items-center justify-center transition-colors cursor-pointer',
            isFavorite ? 'text-destructive' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Heart className={cn('w-4 h-4', isFavorite && 'fill-current')} />
        </button>
      ) : null}

      {!imgFailed && resolvedMedia.mainUrl ? (
        <>
          <img
            src={resolvedMedia.mainUrl}
            alt={`${product.title} — ${displayColor} Altın`}
            referrerPolicy="no-referrer"
            onError={() => setImgFailed(true)}
            style={resolvedMedia.toneFilter ? { filter: resolvedMedia.toneFilter } : undefined}
            className={cn(
              'w-full h-full object-cover transition-all duration-500 ease-out',
              !hoverFailed && 'group-hover:opacity-0 group-hover:scale-105'
            )}
          />
          {!hoverFailed && resolvedMedia.hoverUrl ? (
            <img
              src={resolvedMedia.hoverUrl}
              alt={`${product.title} — ${resolvedMedia.hoverLabel}`}
              referrerPolicy="no-referrer"
              onError={() => setHoverFailed(true)}
              style={resolvedMedia.toneFilter ? { filter: resolvedMedia.toneFilter } : undefined}
              className="absolute inset-0 w-full h-full object-cover opacity-0 scale-105 group-hover:opacity-100 group-hover:scale-100 transition-all duration-500 ease-out"
            />
          ) : null}
        </>
      ) : (
        <div className="w-full h-full flex items-center justify-center p-6">
          <JewelryIllustration
            visualType={product.visualType}
            metalColor={displayColor}
            stoneType={product.stoneType}
            centerStoneCarat={product.centerStoneCarat}
            sideStoneCarat={product.sideStoneCarat}
            className="w-full max-w-[200px] h-auto"
          />
        </div>
      )}
    </>
  );

  const quickAddButton =
    showQuickAdd && metrics.ledger.hasB2cChannel && onQuickAdd ? (
      <button
        type="button"
        disabled={isOutOfStock}
        onClick={(e) => {
          e.stopPropagation();
          onQuickAdd();
        }}
        className={cn(
          TARA_SUCCESS_BTN_CLASS,
          isCollectionLayout ? 'w-full h-9 min-h-9 px-3.5' : 'shrink-0 min-h-[38px] px-3'
        )}
      >
        {isAdded ? (
          <>
            <Check className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Eklendi</span>
          </>
        ) : isCollectionLayout ? (
          <span>Sepete Ekle</span>
        ) : (
          <>
            <ShoppingBag className="w-3.5 h-3.5" />
            <span>Sepete Ekle</span>
          </>
        )}
      </button>
    ) : null;

  return (
    <article className={articleClass}>
      <div onClick={onOpen} className={mediaFrameClass}>
        {mediaStage}
      </div>

      <div
        className={cn(
          'flex flex-1 flex-col',
          isCollectionLayout ? 'gap-2' : 'p-4 pb-0 gap-1.5'
        )}
      >
        {!isCollectionLayout ? (
          <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
            <span className="truncate">
              {product.subCategory || product.category}
              {product.certificateAgency ? ` · ${product.certificateAgency}` : ''}
            </span>
            <span className={cn('shrink-0 font-medium', stockStatusClass)}>
              {product.stockStatus}
            </span>
          </div>
        ) : null}

        <button
          type="button"
          onClick={onOpen}
          className="min-h-[2.75rem] text-left text-lg font-medium leading-snug text-foreground line-clamp-2 transition-colors hover:text-primary cursor-pointer"
        >
          {product.title}
        </button>

        <p className="min-h-[1.1rem] text-xs text-muted-foreground tabular-nums leading-relaxed">
          {isCollectionLayout ? (
            collectionMeta
          ) : (
            <>
              <span>
                {product.purityCode} {displayColor} Altın
              </span>
              {metrics.totalStoneCarat > 0 ? (
                <>
                  <span className="mx-1 text-border" aria-hidden="true">
                    ·
                  </span>
                  <span>{formatTrNumber(metrics.totalStoneCarat, 2)} ct</span>
                </>
              ) : null}
              {variantTotal > 1 && !showColorSwatches ? (
                <>
                  <span className="mx-1 text-border" aria-hidden="true">
                    ·
                  </span>
                  <span>{variantTotal} seçenek</span>
                </>
              ) : null}
            </>
          )}
        </p>

        {isCollectionLayout ? (
          <div className="min-h-[2.5rem] tabular-nums space-y-0.5">
            {metrics.ledger.hasB2cChannel ? (
              <>
                <div
                  className={cn(
                    'font-mono text-[11px] text-muted-foreground line-through',
                    !hasDiscount && 'invisible'
                  )}
                >
                  ₺{formatTrNumber(metrics.finalB2cPriceTry, 0)}
                </div>
                <p className="font-mono text-[13px] font-medium text-foreground">
                  ₺{formatTrNumber(metrics.discountedB2cPriceTry, 0)}
                </p>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">Yalnızca bayi kanalında</p>
            )}
          </div>
        ) : null}

        <div className="mt-auto flex flex-col gap-2 pt-2">
          <div className="min-h-[1.25rem]">
            {showColorSwatches && onSelectColor && product.availableColors.length > 1
              ? swatches
              : null}
          </div>

          {isCollectionLayout ? (
            quickAddButton
          ) : (
            <div className="border-t border-border/75 pt-3 pb-4 flex items-end justify-between gap-2">
              <div className="tabular-nums min-w-0 min-h-[2.5rem] flex flex-col justify-end">
                {metrics.ledger.hasB2cChannel ? (
                  <>
                    <div
                      className={cn(
                        'font-mono text-[11px] text-muted-foreground line-through',
                        !hasDiscount && 'invisible'
                      )}
                    >
                      {formatTrNumber(metrics.finalB2cPriceTry, 0)} TL
                    </div>
                    <div className="font-mono text-[15px] font-semibold text-foreground">
                      {formatTrNumber(metrics.discountedB2cPriceTry, 0)} TL
                    </div>
                  </>
                ) : (
                  <div className="text-xs text-muted-foreground">Yalnızca bayi kanalında</div>
                )}
              </div>
              {quickAddButton}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
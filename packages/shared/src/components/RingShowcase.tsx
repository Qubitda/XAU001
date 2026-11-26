import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Expand,
  FileText,
  Film,
  Play,
  RotateCw,
  Ruler,
  X,
} from 'lucide-react';
import { ProductState, ComputedJewelryMetrics } from '../types/jewelry';
import { formatTrNumber } from '../utils/pricingEngine';
import { MediaAssetKind, resolveProductGallery } from '../data/productMedia';
import { JewelryIllustration } from './JewelryIllustration';
import { LuxuryMerchRibbon } from './LuxuryMerchRibbon';

/**
 * Product gallery / metal visualization.
 * Metal & logo SVG colors are intentional product design — do NOT remap to UI chrome tokens.
 */

interface RingShowcaseProps {
  product: ProductState;
  computed: ComputedJewelryMetrics;
  dealerWatermarkName?: string;
  showDealerWatermark?: boolean;
  b2cLuxuryMode?: boolean;
}

type GalleryFilter = 'all' | 'photo' | 'video' | 'content';

export function RingShowcase({
  product,
  computed,
  dealerWatermarkName,
  showDealerWatermark = false,
  b2cLuxuryMode = false,
}: RingShowcaseProps) {
  const gallery = useMemo(() => resolveProductGallery(product), [product]);
  const [filter, setFilter] = useState<GalleryFilter>('all');
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [angle, setAngle] = useState<number>(18);
  const [isPlayingVideo, setIsPlayingVideo] = useState<boolean>(false);
  const [lightboxOpen, setLightboxOpen] = useState<boolean>(false);
  const stripRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const visibleItems = useMemo(() => {
    if (filter === 'all') return gallery;
    if (filter === 'photo') return gallery.filter((i) => i.kind === 'photo');
    if (filter === 'video') return gallery.filter((i) => i.kind === 'video' || i.kind === 'spin360');
    return gallery.filter((i) => i.kind === 'document' || i.kind === 'blueprint');
  }, [gallery, filter]);

  const syncScrollControls = useCallback(() => {
    const el = stripRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    setActiveIndex(0);
    setIsPlayingVideo(false);
    if (stripRef.current) {
      stripRef.current.scrollTo({ left: 0, behavior: 'smooth' });
    }
  }, [product.parentSku, filter]);

  useEffect(() => {
    syncScrollControls();
    window.addEventListener('resize', syncScrollControls);
    return () => window.removeEventListener('resize', syncScrollControls);
  }, [visibleItems.length, syncScrollControls]);

  const scrollStrip = (direction: 'left' | 'right') => {
    const el = stripRef.current;
    if (!el) return;
    el.scrollBy({
      left: direction === 'left' ? -220 : 220,
      behavior: 'smooth',
    });
  };

  const safeIndex = activeIndex < visibleItems.length ? activeIndex : 0;
  const activeItem = visibleItems[safeIndex] ?? gallery[0];

  const handlePrev = () => {
    setIsPlayingVideo(false);
    setActiveIndex((prev) => (prev - 1 + visibleItems.length) % visibleItems.length);
  };

  const handleNext = () => {
    setIsPlayingVideo(false);
    setActiveIndex((prev) => (prev + 1) % visibleItems.length);
  };

  const counts = useMemo(
    () => ({
      all: gallery.length,
      photo: gallery.filter((i) => i.kind === 'photo').length,
      video: gallery.filter((i) => i.kind === 'video' || i.kind === 'spin360').length,
      content: gallery.filter((i) => i.kind === 'document' || i.kind === 'blueprint').length,
    }),
    [gallery]
  );

  const lux = b2cLuxuryMode;

  const renderKindIcon = (kind: MediaAssetKind) => {
    if (kind === 'video') return <Film className="w-3.5 h-3.5" />;
    if (kind === 'spin360') return <RotateCw className="w-3.5 h-3.5" />;
    if (kind === 'document') return <FileText className="w-3.5 h-3.5" />;
    if (kind === 'blueprint') return <Ruler className="w-3.5 h-3.5" />;
    return null;
  };

  return (
    <div
      className={`overflow-hidden flex flex-col ${
        lux ? 'bg-card border border-border rounded-[6px]' : 'bg-card border border-border rounded-lg'
      }`}
    >
      {/* Top Media Type Filter Strip */}
      <div
        className={`px-3.5 sm:px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 border-b ${
          lux ? 'border-border bg-card' : 'border-border bg-card'
        }`}
      >
        <div
          className={`flex items-center gap-1 p-1 overflow-x-auto no-scrollbar ${
            lux ? 'bg-muted rounded-[4px]' : 'bg-muted rounded-md'
          }`}
        >
          {(
            [
              { id: 'all', label: `Tümü (${counts.all})` },
              { id: 'photo', label: `Fotoğraf (${counts.photo})` },
              { id: 'video', label: `Video & 360° (${counts.video})` },
              { id: 'content', label: `Belge & Şema (${counts.content})` },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setFilter(tab.id)}
              className={`px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                lux ? 'rounded-[3px]' : 'rounded-md'
              } ${
                filter === tab.id
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <span
          className={`text-[11px] font-mono tabular-nums ${lux ? 'text-muted-foreground' : 'text-muted-foreground'}`}
        >
          {safeIndex + 1} / {visibleItems.length} · {product.metalColor} Altın
        </span>
      </div>

      {/* Main Stage (4:3 Locked Aspect Ratio — CLS = 0) */}
      <div
        className={`relative aspect-[4/3] w-full flex items-center justify-center overflow-hidden group ${
          lux ? 'bg-muted' : 'bg-muted'
        }`}
      >
        {/* Dynamic Dealer Watermark Preview (Section 12) */}
        {showDealerWatermark && dealerWatermarkName && (
          <div
            className={`absolute top-4 right-4 z-20 text-right backdrop-blur-xs px-3 py-1.5 ${
              lux
                ? 'border border-input bg-card rounded-[4px]'
                : 'border border-border bg-card/95 rounded-md'
            }`}
          >
            <div
              className="text-sm font-semibold tracking-wide text-foreground"
            >
              {dealerWatermarkName}
            </div>
            <div className={`text-[11px] ${lux ? 'text-muted-foreground' : 'text-muted-foreground'}`}>
              Dinamik Bayi Filigranı · {computed.sku}
            </div>
          </div>
        )}

        {/* PHOTO RENDERER */}
        {activeItem.kind === 'photo' && (
          <>
            <LuxuryMerchRibbon
              discountPct={
                computed.ledger.hasB2cChannel && computed.discountAmountTry > 0
                  ? computed.ledger.effectiveB2cDiscountPct
                  : 0
              }
              isNewCollection={false}
              size="detail"
            />
            <img
              src={activeItem.url}
              alt={`${product.title} — ${activeItem.label}`}
              referrerPolicy="no-referrer"
              style={{
                filter: activeItem.toneFilter,
                transform: activeItem.zoomScale ? `scale(${activeItem.zoomScale})` : undefined,
                transformOrigin: activeItem.focalPosition ?? 'center center',
              }}
              className="w-full h-full object-cover transition-all duration-300"
            />
            <button
              type="button"
              onClick={() => setLightboxOpen(true)}
              aria-label="Fotoğrafı tam ekran büyüt"
              className={`absolute bottom-3.5 right-3.5 z-20 px-2.5 py-1.5 text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer ${
                lux
                  ? 'bg-background hover:bg-card text-foreground rounded-[4px] border border-border hover:border-ring'
                  : 'bg-card/95 hover:bg-card text-foreground rounded-md border border-border hover:border-ring'
              }`}
            >
              <Expand className={`w-3.5 h-3.5 ${lux ? 'text-muted-foreground' : 'text-muted-foreground'}`} />
              <span>Büyüt</span>
            </button>
          </>
        )}

        {/* VIDEO RENDERER (Supports both 16:9 Daylight Sparkle & 9:16 Reels) */}
        {activeItem.kind === 'video' && activeItem.aspectHint === '9:16' && (
          <div className="w-full h-full bg-primary flex items-center justify-center p-5">
            <div className="h-full max-h-[340px] aspect-[9/16] bg-primary text-primary-foreground rounded-xl overflow-hidden shadow-2xl relative flex flex-col justify-between">
              <img
                src={activeItem.posterUrl}
                alt={`${product.title} — ${activeItem.label}`}
                referrerPolicy="no-referrer"
                className={`absolute inset-0 w-full h-full object-cover transition-transform duration-[4000ms] ${
                  isPlayingVideo ? 'scale-110 opacity-90' : 'scale-100 opacity-75'
                }`}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-black/45" />
              <div className="relative z-10 p-3.5 flex items-center justify-between text-[10px] text-primary-foreground/80 font-mono">
                <span>9:16 REELS · 0:{activeItem.durationSec}</span>
                <span className="truncate max-w-[90px]">{activeItem.url}</span>
              </div>
              <div className="relative z-10 my-auto flex justify-center">
                <button
                  type="button"
                  onClick={() => setIsPlayingVideo((v) => !v)}
                  className="px-3.5 py-2 rounded-full bg-card/20 hover:bg-card/30 backdrop-blur-xs border border-white/40 text-xs font-medium text-primary-foreground flex items-center gap-1.5 cursor-pointer"
                >
                  <Play className="w-3.5 h-3.5" />
                  {isPlayingVideo ? 'Duraklat' : 'Reels Oynat'}
                </button>
              </div>
              <div className="relative z-10 p-3.5 space-y-1">
                <div className="text-base font-semibold leading-tight text-primary-foreground">
                  {product.title}
                </div>
                <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-white/20">
                  <span className="font-mono text-primary-foreground/80">{computed.sku}</span>
                  <span className="font-mono text-muted-foreground tabular-nums">
                    {formatTrNumber(computed.discountedB2cPriceTry, 0)} TL
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeItem.kind === 'video' && activeItem.aspectHint !== '9:16' && (
          <div className="relative w-full h-full bg-primary flex items-center justify-center overflow-hidden">
            <img
              src={activeItem.posterUrl}
              alt={`${product.title} — ${activeItem.label}`}
              referrerPolicy="no-referrer"
              style={activeItem.toneFilter ? { filter: activeItem.toneFilter } : undefined}
              className={`w-full h-full object-cover transition-transform duration-[4500ms] ease-out ${
                isPlayingVideo ? 'scale-115 opacity-95' : 'scale-100 opacity-75'
              }`}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/20 to-black/30" />
            <button
              type="button"
              onClick={() => setIsPlayingVideo((v) => !v)}
              className="relative z-10 px-5 py-2.5 rounded-md bg-card/95 hover:bg-card text-foreground text-xs font-semibold flex items-center gap-2 shadow-lg cursor-pointer"
            >
              <Play className="w-4 h-4 fill-foreground" />
              {isPlayingVideo
                ? `Oynatılıyor · ${activeItem.label}`
                : `${activeItem.label} (0:${activeItem.durationSec})`}
            </button>
            <div className="absolute bottom-3.5 left-4 right-4 z-10 flex items-center justify-between text-[11px] font-mono text-primary-foreground/80">
              <span>{activeItem.url}</span>
              <span>16:9 · HLS / MP4</span>
            </div>
          </div>
        )}

        {/* 360° SPIN RENDERER */}
        {activeItem.kind === 'spin360' && (
          <div className="w-full h-full bg-gradient-to-b from-muted to-background p-6 flex flex-col items-center justify-center">
            <JewelryIllustration
              visualType={product.visualType}
              metalColor={product.metalColor}
              stoneType={product.stoneType}
              centerStoneCarat={product.centerStoneCarat}
              sideStoneCarat={product.sideStoneCarat}
              angle={angle}
              showDimensions={false}
              title={`${product.title} — 360° dönen tabla`}
              className="w-full max-w-[290px] h-auto select-none"
            />
            <div className="w-full max-w-xs mt-1 flex items-center gap-3">
              <span className="text-xs font-mono text-muted-foreground">0°</span>
              <input
                type="range"
                min={0}
                max={360}
                value={angle}
                onChange={(e) => setAngle(Number(e.target.value))}
                aria-label="360 derece dönüş açısı"
                className="w-full accent-foreground cursor-pointer"
              />
              <span className="text-xs font-mono text-muted-foreground tabular-nums w-10 text-right">
                {angle}°
              </span>
            </div>
          </div>
        )}

        {/* CERTIFICATE DOCUMENT RENDERER */}
        {activeItem.kind === 'document' && (
          <div
            className={`w-full h-full p-5 sm:p-6 flex items-center justify-center ${
              lux ? 'bg-muted' : 'bg-muted'
            }`}
          >
            <div
              className={`w-full max-w-md p-5 sm:p-6 ${
                lux
                  ? 'bg-card border border-border rounded-[6px]'
                  : 'bg-card border border-border rounded-lg'
              }`}
            >
              <div
                className={`flex items-start justify-between pb-4 gap-3 border-b ${
                  lux ? 'border-border' : 'border-border'
                }`}
              >
                <div>
                  <div
                    className={`text-[11px] font-mono tracking-wider ${
                      lux ? 'text-muted-foreground' : 'text-muted-foreground'
                    }`}
                  >
                    {product.certificateAgency} DOĞRULAMA RAPORU
                  </div>
                  <div
                    className="text-xl font-semibold mt-1 text-foreground"
                  >
                    Gemological Certificate Dossier
                  </div>
                </div>
                <div
                  className={`text-right font-mono text-xs shrink-0 ${
                    lux ? 'text-muted-foreground' : 'text-muted-foreground'
                  }`}
                >
                  <div>No: {product.certificateNumber}</div>
                  <div
                    className={`mt-0.5 truncate max-w-[140px] ${'text-muted-foreground'}`}
                  >
                    {product.certificateFileUrl}
                  </div>
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 mt-4 text-xs">
                <div>
                  <dt className={'text-muted-foreground'}>Kesim / Şekil</dt>
                  <dd className={`font-medium mt-0.5 ${lux ? 'text-foreground' : 'text-foreground'}`}>
                    {product.stoneCutShape}
                  </dd>
                </div>
                <div>
                  <dt className={'text-muted-foreground'}>Toplam Karat</dt>
                  <dd
                    className={`font-mono font-medium mt-0.5 tabular-nums ${
                      lux ? 'text-foreground' : 'text-foreground'
                    }`}
                  >
                    {formatTrNumber(computed.totalStoneCarat, 2)} ct (
                    {formatTrNumber(product.centerStoneCarat, 2)} +{' '}
                    {formatTrNumber(product.sideStoneCarat, 2)})
                  </dd>
                </div>
                <div>
                  <dt className={'text-muted-foreground'}>Renk Derecesi</dt>
                  <dd
                    className={`font-mono font-medium mt-0.5 ${lux ? 'text-foreground' : 'text-foreground'}`}
                  >
                    {product.stoneColorGrade}
                  </dd>
                </div>
                <div>
                  <dt className={'text-muted-foreground'}>Berraklık (Clarity)</dt>
                  <dd
                    className={`font-mono font-medium mt-0.5 ${lux ? 'text-foreground' : 'text-foreground'}`}
                  >
                    {product.stoneClarity}
                  </dd>
                </div>
                <div>
                  <dt className={'text-muted-foreground'}>Kesim Kalitesi</dt>
                  <dd className={`font-medium mt-0.5 ${lux ? 'text-foreground' : 'text-foreground'}`}>
                    {product.stoneCutGrade}
                  </dd>
                </div>
                <div>
                  <dt className={'text-muted-foreground'}>Menşei / Mıhlama</dt>
                  <dd className={`font-medium mt-0.5 ${lux ? 'text-foreground' : 'text-foreground'}`}>
                    {product.stoneOrigin} · {product.settingType}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        )}

        {/* TECHNICAL DIMENSIONS BLUEPRINT RENDERER */}
        {activeItem.kind === 'blueprint' && (
          <div className="w-full h-full bg-muted p-6 flex flex-col items-center justify-center">
            <JewelryIllustration
              visualType={product.visualType}
              metalColor={product.metalColor}
              stoneType={product.stoneType}
              centerStoneCarat={product.centerStoneCarat}
              sideStoneCarat={product.sideStoneCarat}
              showDimensions={true}
              widthMm={product.widthMm}
              thicknessMm={product.thicknessMm}
              heightMm={product.heightMm}
              title={`${product.title} — teknik ölçü şeması`}
              className="w-full max-w-[320px] h-auto select-none"
            />
          </div>
        )}

        {/* Previous / Next Navigation Arrows */}
        {visibleItems.length > 1 && (
          <>
            <button
              type="button"
              onClick={handlePrev}
              aria-label="Önceki medya"
              className={`absolute left-3 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full flex items-center justify-center transition-opacity opacity-95 md:opacity-0 md:group-hover:opacity-100 cursor-pointer ${
                lux
                  ? 'bg-background hover:bg-card border border-border hover:border-ring text-foreground'
                  : 'bg-card/95 hover:bg-card border border-border hover:border-ring text-foreground'
              }`}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleNext}
              aria-label="Sonraki medya"
              className={`absolute right-3 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full flex items-center justify-center transition-opacity opacity-95 md:opacity-0 md:group-hover:opacity-100 cursor-pointer ${
                lux
                  ? 'bg-background hover:bg-card border border-border hover:border-ring text-foreground'
                  : 'bg-card/95 hover:bg-card border border-border hover:border-ring text-foreground'
              }`}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </>
        )}
      </div>

      {/* Sleek Scrollbar-Free Multi-Media Thumbnail Filmstrip */}
      <div
        className={`border-t p-3 space-y-2.5 ${
          lux ? 'border-border bg-card' : 'border-border bg-card'
        }`}
      >
        <div className="relative">
          {canScrollLeft && (
            <div
              className={`pointer-events-none absolute inset-y-0 left-0 z-10 w-10 flex items-center justify-start bg-gradient-to-r to-transparent ${
                lux ? 'from-card via-card/90' : 'from-card via-card/90'
              }`}
            >
              <button
                type="button"
                onClick={() => scrollStrip('left')}
                aria-label="Küçük resimleri sola kaydır"
                className={`pointer-events-auto w-7 h-7 rounded-full flex items-center justify-center transition-colors cursor-pointer ${
                  lux
                    ? 'bg-background border border-border text-foreground hover:border-ring'
                    : 'bg-muted border border-border text-foreground hover:border-ring'
                }`}
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div
            ref={stripRef}
            onScroll={syncScrollControls}
            className="flex items-center gap-2 overflow-x-auto no-scrollbar scroll-smooth py-0.5 px-0.5"
          >
            {visibleItems.map((item, idx) => {
              const isSelected = idx === safeIndex;
              const thumbImg = item.kind === 'photo' ? item.url : item.posterUrl;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setActiveIndex(idx);
                    setIsPlayingVideo(false);
                  }}
                  aria-label={`${item.label} seç`}
                  aria-current={isSelected ? 'true' : undefined}
                  className={`relative shrink-0 w-20 overflow-hidden border transition-all text-left cursor-pointer ${
                    lux ? 'rounded-[4px]' : 'rounded-md'
                  } ${
                    isSelected
                      ? lux
                        ? 'border-foreground ring-1 ring-ring'
                        : 'border-foreground ring-1 ring-ring'
                      : lux
                        ? 'border-border opacity-80 hover:opacity-100 hover:border-ring'
                        : 'border-border opacity-90 hover:opacity-100 hover:border-ring'
                  }`}
                >
                  <div
                    className={`aspect-[4/3] relative flex items-center justify-center overflow-hidden ${
                      lux ? 'bg-muted' : 'bg-muted'
                    }`}
                  >
                    {thumbImg ? (
                      <>
                        <img
                          src={thumbImg}
                          alt={item.label}
                          referrerPolicy="no-referrer"
                          style={{
                            filter: item.toneFilter,
                            transform: item.zoomScale ? `scale(${item.zoomScale})` : undefined,
                          }}
                          className="w-full h-full object-cover"
                        />
                        {item.kind === 'video' && (
                          <div className="absolute inset-0 bg-black/35 flex items-center justify-center text-primary-foreground">
                            <Play className="w-4 h-4 fill-white" />
                          </div>
                        )}
                      </>
                    ) : (
                      <div
                        className={`flex flex-col items-center gap-1 ${lux ? 'text-muted-foreground' : 'text-muted-foreground'}`}
                      >
                        {renderKindIcon(item.kind)}
                        <span className="text-[9px] font-mono uppercase">{item.kind}</span>
                      </div>
                    )}
                  </div>
                  <div
                    className={`px-1.5 py-1 text-[10px] font-medium truncate ${
                      lux ? 'bg-card text-muted-foreground' : 'bg-card text-muted-foreground'
                    }`}
                  >
                    {item.label}
                  </div>
                </button>
              );
            })}
          </div>

          {canScrollRight && (
            <div
              className={`pointer-events-none absolute inset-y-0 right-0 z-10 w-10 flex items-center justify-end bg-gradient-to-l to-transparent ${
                lux ? 'from-card via-card/90' : 'from-card via-card/90'
              }`}
            >
              <button
                type="button"
                onClick={() => scrollStrip('right')}
                aria-label="Küçük resimleri sağa kaydır"
                className={`pointer-events-auto w-7 h-7 rounded-full flex items-center justify-center transition-colors cursor-pointer ${
                  lux
                    ? 'bg-background border border-border text-foreground hover:border-ring'
                    : 'bg-muted border border-border text-foreground hover:border-ring'
                }`}
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Active Asset Caption */}
        <div
          className={`flex flex-wrap items-center justify-between gap-2 text-[11px] pt-1.5 border-t ${
            lux ? 'text-muted-foreground border-border' : 'text-muted-foreground border-border'
          }`}
        >
          <span>
            <strong className={`font-medium ${lux ? 'text-foreground' : 'text-foreground'}`}>
              {activeItem.label}
            </strong>
            {activeItem.description ? ` · ${activeItem.description}` : ''}
          </span>
          <span className={lux ? 'text-muted-foreground' : 'text-muted-foreground'}>
            {product.purityCode} {product.metalColor} Altın
          </span>
        </div>
      </div>

      {/* High-Resolution Lightbox Modal */}
      {lightboxOpen && activeItem.kind === 'photo' && (
        <div
          className={`fixed inset-0 z-50 backdrop-blur-xs flex items-center justify-center p-4 sm:p-6 ${
            lux ? 'bg-primary' : 'bg-primary/80'
          }`}
          onClick={() => setLightboxOpen(false)}
          role="dialog"
          aria-label="Tam ekran ürün fotoğrafı"
        >
          <div
            className={`relative max-w-4xl w-full overflow-hidden shadow-2xl ${
              lux
                ? 'bg-card border border-border rounded-[6px]'
                : 'bg-card border border-border rounded-lg'
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className={`flex items-center justify-between px-5 py-3 border-b text-xs ${
                lux ? 'border-border' : 'border-border'
              }`}
            >
              <span className={`font-medium ${lux ? 'text-foreground' : 'text-foreground'}`}>
                {product.title} · {activeItem.label} ({product.metalColor} Altın)
              </span>
              <button
                type="button"
                onClick={() => setLightboxOpen(false)}
                aria-label="Kapat"
                className={`p-1.5 cursor-pointer ${lux ? 'text-muted-foreground hover:text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div
              className={`aspect-[4/3] w-full overflow-hidden ${lux ? 'bg-muted' : 'bg-muted'}`}
            >
              <img
                src={activeItem.url}
                alt={`${product.title} — ${activeItem.label}`}
                referrerPolicy="no-referrer"
                style={{
                  filter: activeItem.toneFilter,
                  transform: activeItem.zoomScale ? `scale(${activeItem.zoomScale})` : undefined,
                  transformOrigin: activeItem.focalPosition ?? 'center center',
                }}
                className="w-full h-full object-cover"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

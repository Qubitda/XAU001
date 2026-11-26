import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react';

import timeless1920 from '../../../assets/images/hero/hero-timeless-elegance-1920.jpg';
import timeless2560 from '../../../assets/images/hero/hero-timeless-elegance-2560.jpg';
import arrivals1920 from '../../../assets/images/hero/hero-new-arrivals-1920.jpg';
import arrivals2560 from '../../../assets/images/hero/hero-new-arrivals-2560.jpg';
import atelier1920 from '../../../assets/images/hero/hero-atelier-craft-1920.jpg';
import atelier2560 from '../../../assets/images/hero/hero-atelier-craft-2560.jpg';

export interface HeroCampaignSlide {
  id: string;
  eyebrow: string;
  titleLines: [string, string];
  subtitle: string;
  ctaLabel: string;
  ctaHref: string;
  /** Default/fallback URL (prefer the largest asset). */
  imageUrl: string;
  /** Responsive candidates, e.g. `url 1920w, url 2560w`. */
  imageSrcSet: string;
  imageSizes?: string;
  imageAlt: string;
  imagePositionClass: string;
}

export const DEFAULT_HERO_SLIDES: HeroCampaignSlide[] = [
  {
    id: 'timeless-elegance',
    eyebrow: 'TARA DIAMOND',
    titleLines: ['Zamansız', 'Bir Zarafet'],
    subtitle: 'Her anınıza eşlik eden özel tasarımlar.',
    ctaLabel: 'Koleksiyonu Keşfet',
    ctaHref: '/koleksiyon',
    imageUrl: timeless2560,
    imageSrcSet: `${timeless1920} 1920w, ${timeless2560} 2560w`,
    imageSizes: '100vw',
    imageAlt: 'TARA DIAMOND sertifikalı pırlanta mücevher kampanyası',
    imagePositionClass: 'object-[68%_22%] sm:object-[72%_25%]',
  },
  {
    id: 'new-arrivals',
    eyebrow: 'YENİ KOLEKSİYON',
    titleLines: ['Işıltının', 'Saf Hali'],
    subtitle: 'GIA ve HRD sertifikalı yeni sezon pırlanta yüzükler.',
    ctaLabel: 'Yeni Gelenleri İncele',
    ctaHref: '/koleksiyon?filter=new_collection',
    imageUrl: arrivals2560,
    imageSrcSet: `${arrivals1920} 1920w, ${arrivals2560} 2560w`,
    imageSizes: '100vw',
    imageAlt: 'TARA DIAMOND pırlanta tektaş yüzük yeni sezon koleksiyonu',
    imagePositionClass: 'object-[62%_center] sm:object-[66%_center]',
  },
  {
    id: 'atelier-craft',
    eyebrow: 'ATÖLYE ZANAATI',
    titleLines: ['Kuşaklar Boyu', 'Süren Değer'],
    subtitle: 'El işçiliği altın montürler ve sigortalı özel teslimat.',
    ctaLabel: 'Kampanyaları Gör',
    ctaHref: '/koleksiyon?filter=discounted',
    imageUrl: atelier2560,
    imageSrcSet: `${atelier1920} 1920w, ${atelier2560} 2560w`,
    imageSizes: '100vw',
    imageAlt: 'TARA DIAMOND traverten üzerinde tektaş yüzük ve suyolu bileklik',
    imagePositionClass: 'object-[60%_65%] sm:object-[65%_65%]',
  },
];

interface HeroBannerSliderProps {
  slides?: HeroCampaignSlide[];
  autoAdvanceMs?: number;
}

export function HeroBannerSlider({
  slides = DEFAULT_HERO_SLIDES,
  autoAdvanceMs = 8000,
}: HeroBannerSliderProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  const safeSlides = slides.length > 0 ? slides : DEFAULT_HERO_SLIDES;
  const activeSlide = safeSlides[activeIndex % safeSlides.length];

  const handlePrev = () => {
    setActiveIndex((prev) => (prev - 1 + safeSlides.length) % safeSlides.length);
  };

  const handleNext = () => {
    setActiveIndex((prev) => (prev + 1) % safeSlides.length);
  };

  useEffect(() => {
    if (safeSlides.length <= 1 || isPaused) return;
    if (
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return;
    }
    const timer = window.setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % safeSlides.length);
    }, autoAdvanceMs);
    return () => window.clearInterval(timer);
  }, [safeSlides.length, isPaused, autoAdvanceMs]);

  return (
    <section
      aria-label="Öne çıkan kampanya"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      className="relative w-full overflow-hidden bg-muted border-b border-border"
    >
      <div className="relative min-h-[470px] sm:min-h-[500px] lg:min-h-[560px] xl:min-h-[600px] flex items-center">
        {/* Background Campaign Image — 1920/2560 srcset, no build-time recompress */}
        <img
          key={activeSlide.id}
          src={activeSlide.imageUrl}
          srcSet={activeSlide.imageSrcSet}
          sizes={activeSlide.imageSizes ?? '100vw'}
          alt={activeSlide.imageAlt}
          fetchPriority="high"
          decoding="async"
          className={`absolute inset-0 w-full h-full object-cover ${activeSlide.imagePositionClass}`}
        />

        {/* Editorial Champagne Ivory Scrim for Crisp Dark Serif Legibility */}
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-t from-background/95 via-background/80 to-background/20 sm:bg-gradient-to-r sm:from-background/96 sm:via-background/78 sm:to-transparent"
        />

        {/* Hero Copy Overlay */}
        <div className="relative z-10 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-12 sm:py-16 lg:py-20">
          <div className="max-w-md lg:max-w-lg space-y-5 sm:space-y-6">
            {/* Eyebrow with Champagne Gold Hairline Rules */}
            <div className="inline-flex items-center gap-3 text-[11px] sm:text-xs tracking-[0.26em] text-muted-foreground font-medium">
              <span className="w-6 sm:w-8 h-px bg-primary" aria-hidden="true" />
              <span>{activeSlide.eyebrow}</span>
              <span className="w-6 sm:w-8 h-px bg-primary" aria-hidden="true" />
            </div>

            {/* Editorial Serif Headline */}
            <h1 className="font-serif text-[40px] min-[375px]:text-[44px] sm:text-5xl lg:text-[62px] font-normal text-foreground leading-[1.04] tracking-[-0.01em]">
              <span className="block">{activeSlide.titleLines[0]}</span>
              <span className="block">{activeSlide.titleLines[1]}</span>
            </h1>

            {/* Subtitle */}
            <p className="text-sm sm:text-base text-muted-foreground leading-relaxed max-w-sm">
              {activeSlide.subtitle}
            </p>

            {/* Primary CTA */}
            <div className="pt-1">
              <Link
                to={activeSlide.ctaHref}
                className="inline-flex items-center justify-center gap-3 min-h-[46px] px-6 sm:px-7 py-3 rounded-[4px] bg-primary text-primary-foreground text-xs sm:text-[13px] font-medium tracking-[0.04em] hover:bg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background transition-colors whitespace-nowrap"
              >
                <span>{activeSlide.ctaLabel}</span>
                <ArrowRight className="w-4 h-4 shrink-0" />
              </Link>
            </div>

            {/* Minimal Numeric Slider Controls (< 1 / 3 >) */}
            {safeSlides.length > 1 && (
              <div className="pt-4 sm:pt-6 flex items-center gap-3 text-xs text-muted-foreground">
                <button
                  type="button"
                  onClick={handlePrev}
                  aria-label="Önceki kampanya"
                  className="inline-flex items-center justify-center w-8 h-8 rounded-full hover:bg-primary/8 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="font-mono text-xs tabular-nums tracking-wider select-none">
                  <strong className="font-semibold text-foreground">{activeIndex + 1}</strong>
                  <span className="mx-1 text-muted-foreground">/</span>
                  <span>{safeSlides.length}</span>
                </span>
                <button
                  type="button"
                  onClick={handleNext}
                  aria-label="Sonraki kampanya"
                  className="inline-flex items-center justify-center w-8 h-8 rounded-full hover:bg-primary/8 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import heroCampaignVideo from '../../../assets/videos/hero-campaign.mp4';

export function HeroBannerSlider() {
  return (
    <section
      aria-label="Öne çıkan kampanya"
      className="relative w-full overflow-hidden bg-muted border-b border-border"
    >
      <div className="relative min-h-[500px] sm:min-h-[560px] lg:min-h-[640px] xl:min-h-[680px] flex items-center">
        {/* Background Campaign Video */}
        <video
          src={heroCampaignVideo}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          aria-hidden="true"
          className="absolute inset-0 w-full h-full object-cover object-[72%_22%] sm:object-[68%_24%] lg:object-[62%_25%]"
        />

        {/* Subtle Left-Edge White Transparent Gradient for Crisp Legibility */}
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-t from-white/80 via-white/30 to-transparent sm:bg-gradient-to-r sm:from-white/80 sm:via-white/35 sm:via-45% sm:to-transparent"
        />

        {/* Hero Copy Overlay */}
        <div className="relative z-10 max-w-[1440px] mx-auto w-full px-4 sm:px-6 lg:px-12 pt-28 pb-12 sm:pt-32 sm:pb-16 lg:pt-36 lg:pb-20">
          <div className="max-w-sm lg:max-w-[440px]">
            {/* Eyebrow */}
            <div className="inline-flex items-center gap-3 text-[11px] tracking-[0.26em] text-stone-700 font-medium">
              <span className="w-6 sm:w-8 h-px bg-[#A58C72]" aria-hidden="true" />
              <span>TARA DIAMOND</span>
              <span className="w-6 sm:w-8 h-px bg-[#A58C72]" aria-hidden="true" />
            </div>

            {/* Editorial Serif Headline (58-62px on desktop) */}
            <h1 className="mt-4 font-serif text-[44px] sm:text-[54px] lg:text-[62px] font-normal text-[#171717] leading-[1.04] tracking-[-0.015em] text-balance">
              <span className="block">Zamansız</span>
              <span className="block">Bir Zarafet</span>
            </h1>

            {/* Subtitle — tighter gap & stronger contrast */}
            <p className="mt-3 text-[15px] sm:text-base text-[#171717]/85 font-normal leading-relaxed max-w-md">
              Her anınıza eşlik eden, özenle tasarlanmış mücevherler.
            </p>

            {/* Primary CTA — 48px height, clean black, slightly rounded */}
            <div className="mt-6 sm:mt-7">
              <Link
                to="/koleksiyon"
                className="inline-flex items-center justify-center gap-2.5 h-12 min-h-[48px] px-7 rounded-[4px] bg-[#171717] text-[#F7F5F1] text-[13px] font-semibold tracking-[0.04em] hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background transition-colors whitespace-nowrap"
              >
                <span>Koleksiyonu Keşfet</span>
                <ArrowRight className="w-4 h-4 shrink-0" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

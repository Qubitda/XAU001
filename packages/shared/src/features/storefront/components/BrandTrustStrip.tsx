import { Award, Gem, Gift, ShieldCheck } from 'lucide-react';

const TRUST_PILLARS = [
  {
    id: 'authenticity',
    icon: Award,
    title: 'Orijinallik',
    subtitle: 'Ürün Sertifikası',
  },
  {
    id: 'secure-shopping',
    icon: ShieldCheck,
    title: 'Güvenli Alışveriş',
    subtitle: 'SSL Güvenlik',
  },
  {
    id: 'craftsmanship',
    icon: Gem,
    title: 'Kaliteli İşçilik',
    subtitle: 'Usta Zanaat',
  },
  {
    id: 'packaging',
    icon: Gift,
    title: 'Özel Ambalaj',
    subtitle: 'Marka Kutusu',
  },
] as const;

interface BrandTrustStripProps {
  /** @deprecated collection-bar kaldırıldı — her yerde detaylı şerit kullanılır */
  variant?: 'detailed' | 'collection-bar';
}

export function BrandTrustStrip(_props: BrandTrustStripProps = {}) {
  return (
    <section aria-label="TARA DIAMOND güvenceleri" className="border-y border-border bg-card">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-12 py-8 sm:py-10">
        <div className="grid grid-cols-1 min-[420px]:grid-cols-2 lg:grid-cols-4 gap-y-5 gap-x-6 lg:divide-x lg:divide-border">
          {TRUST_PILLARS.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div
                key={item.id}
                className={`flex items-center gap-3.5 ${idx > 0 ? 'lg:pl-7' : ''}`}
              >
                <Icon
                  className="w-6 h-6 text-muted-foreground stroke-[1.5] shrink-0"
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold text-foreground leading-snug">
                    {item.title}
                  </div>
                  <div className="text-xs text-muted-foreground leading-snug mt-0.5">
                    {item.subtitle}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

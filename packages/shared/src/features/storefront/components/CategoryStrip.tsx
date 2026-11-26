import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import ringFallbackImg from '../../../assets/images/se009_white_main_1795533192415.jpg';
import necklaceFallbackImg from '../../../assets/images/kl022_necklace_main_1795533193295.jpg';
import earringFallbackImg from '../../../assets/images/kp018_emerald_main_1795533193415.jpg';
import braceletFallbackImg from '../../../assets/images/bl031_bracelet_main_1795533193007.jpg';
import type { ProductState } from '../../catalog/types';
import { resolveProductThumbnail } from '../../../data/productMedia';

interface CategoryConfig {
  key: 'Yüzük' | 'Kolye' | 'Küpe' | 'Bileklik';
  label: string;
  href: string;
  fallbackImg: string;
  alt: string;
}

const CATEGORY_CARDS: CategoryConfig[] = [
  {
    key: 'Yüzük',
    label: 'Yüzük',
    href: '/koleksiyon?category=Y%C3%BCz%C3%BCk',
    fallbackImg: ringFallbackImg,
    alt: 'TARA DIAMOND pırlanta ve altın yüzük kategorisi',
  },
  {
    key: 'Kolye',
    label: 'Kolye',
    href: '/koleksiyon?category=Kolye',
    fallbackImg: necklaceFallbackImg,
    alt: 'TARA DIAMOND pırlanta kolye kategorisi',
  },
  {
    key: 'Küpe',
    label: 'Küpe',
    href: '/koleksiyon?category=K%C3%BCpe',
    fallbackImg: earringFallbackImg,
    alt: 'TARA DIAMOND değerli taşlı ve pırlanta küpe kategorisi',
  },
  {
    key: 'Bileklik',
    label: 'Bileklik',
    href: '/koleksiyon?category=Bileklik',
    fallbackImg: braceletFallbackImg,
    alt: 'TARA DIAMOND suyolu ve pırlanta bileklik kategorisi',
  },
];

interface CategoryStripProps {
  products: ProductState[];
}

export function CategoryStrip({ products }: CategoryStripProps) {
  const categoryStats = CATEGORY_CARDS.map((card) => {
    const matching = products.filter((p) => p.category === card.key);
    const firstCustom = matching.find((p) => (p.galleryImages?.length ?? 0) > 0);
    const imageUrl = firstCustom
      ? resolveProductThumbnail(firstCustom)
      : matching[0]
        ? resolveProductThumbnail(matching[0])
        : card.fallbackImg;

    return {
      ...card,
      count: matching.length,
      imageUrl: imageUrl || card.fallbackImg,
    };
  });

  return (
    <section
      aria-label="Mücevher kategorileri"
      className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
        {categoryStats.map((cat) => (
          <Link
            key={cat.key}
            to={cat.href}
            className="group relative aspect-[4/3] sm:aspect-[16/10] rounded-[6px] overflow-hidden bg-[#EDE3D5] border border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <img
              src={cat.imageUrl}
              alt={cat.alt}
              loading="lazy"
              decoding="async"
              referrerPolicy="no-referrer"
              className="w-full h-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.04]"
            />

            {/* Soft Warm Scrim for Clean Label Readability */}
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-gradient-to-t from-primary/72 via-primary/18 to-transparent"
            />

            <div className="absolute inset-x-0 bottom-0 p-3 sm:p-4 flex items-end justify-between gap-2 text-primary-foreground">
              <div className="min-w-0">
                <h2 className="font-serif text-lg sm:text-xl font-medium leading-tight tracking-[0.01em] inline-flex items-center gap-1.5">
                  <span>{cat.label}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 group-hover:translate-x-1 shrink-0" />
                </h2>
                {cat.count > 0 && (
                  <div className="text-[11px] text-muted-foreground mt-0.5 tabular-nums">
                    {cat.count} tasarım
                  </div>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

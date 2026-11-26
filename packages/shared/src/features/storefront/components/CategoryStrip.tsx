import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import ringFallbackImg from '../../../assets/images/se009_white_main_1795533192415.jpg';
import necklaceFallbackImg from '../../../assets/images/kl022_necklace_main_1795533193295.jpg';
import earringFallbackImg from '../../../assets/images/category-earrings.jpg';
import braceletFallbackImg from '../../../assets/images/bl031_bracelet_main_1795533193007.jpg';
import type { ProductState } from '../../catalog/types';
import { resolveProductThumbnail } from '../../../data/productMedia';
import {
  matchesDefinitionValue,
  usePublicDefinitionOptions,
} from '../../definitions/hooks/useDefinitionsQuery';
import {
  LEGACY_STOREFRONT_CATEGORY_CODES,
  metaString,
  pickStorefrontCategories,
} from '../../definitions/storefrontCategories';

const FALLBACK_BY_CODE: Record<string, { img: string; alt: string }> = {
  YUZUK: {
    img: ringFallbackImg,
    alt: 'TARA DIAMOND pırlanta ve altın yüzük kategorisi',
  },
  KOLYE: {
    img: necklaceFallbackImg,
    alt: 'TARA DIAMOND pırlanta kolye kategorisi',
  },
  KUPE: {
    img: earringFallbackImg,
    alt: 'TARA DIAMOND sarı altın küpe kategorisi',
  },
  BILEKLIK: {
    img: braceletFallbackImg,
    alt: 'TARA DIAMOND suyolu ve pırlanta bileklik kategorisi',
  },
};

function isRenderableUrl(url: string): boolean {
  return (
    url.startsWith('http://') ||
    url.startsWith('https://') ||
    url.startsWith('/') ||
    url.startsWith('data:image/')
  );
}

interface CategoryStripProps {
  products: ProductState[];
}

export function CategoryStrip({ products }: CategoryStripProps) {
  const { options } = usePublicDefinitionOptions('kategori');

  const cards = useMemo(() => {
    if (options.length === 0) {
      return LEGACY_STOREFRONT_CATEGORY_CODES.map((code) => {
        const fb = FALLBACK_BY_CODE[code];
        const label =
          code === 'YUZUK'
            ? 'Yüzük'
            : code === 'KOLYE'
              ? 'Kolye'
              : code === 'KUPE'
                ? 'Küpe'
                : 'Bileklik';
        return {
          key: code,
          label,
          href: `/koleksiyon?category=${encodeURIComponent(code)}`,
          count: 0,
          imageUrl: fb.img,
          alt: fb.alt,
        };
      });
    }

    return pickStorefrontCategories(options).map((opt) => {
      const matching = products.filter((p) =>
        matchesDefinitionValue(p.category, opt.value, options)
      );
      const configuredUrl = metaString(opt.meta, 'storefrontImageUrl');
      const configuredAlt = metaString(opt.meta, 'storefrontImageAlt');
      const fallback = FALLBACK_BY_CODE[opt.code] ?? {
        img: ringFallbackImg,
        alt: `TARA DIAMOND ${opt.label} kategorisi`,
      };

      let imageUrl = fallback.img;
      if (configuredUrl && isRenderableUrl(configuredUrl)) {
        imageUrl = configuredUrl;
      } else {
        const firstCustom = matching.find((p) => (p.galleryImages?.length ?? 0) > 0);
        if (firstCustom) imageUrl = resolveProductThumbnail(firstCustom) || fallback.img;
        else if (matching[0]) imageUrl = resolveProductThumbnail(matching[0]) || fallback.img;
      }

      return {
        key: opt.code,
        label: opt.label,
        href: `/koleksiyon?category=${encodeURIComponent(opt.value)}`,
        count: matching.length,
        imageUrl,
        alt: configuredAlt || fallback.alt,
      };
    });
  }, [options, products]);

  if (cards.length === 0) return null;

  const colClass =
    cards.length === 1
      ? 'grid-cols-1'
      : cards.length === 2
        ? 'grid-cols-2'
        : cards.length === 3
          ? 'grid-cols-2 lg:grid-cols-3'
          : 'grid-cols-2 lg:grid-cols-4';

  return (
    <section
      aria-label="Mücevher kategorileri"
      className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"
    >
      <div className={`grid ${colClass} gap-3 sm:gap-5`}>
        {cards.map((cat) => (
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

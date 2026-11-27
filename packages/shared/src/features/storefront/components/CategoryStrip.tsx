import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import ringFallbackImg from '../../../assets/images/se009_yellow_main_1795533192654.jpg';
import setFallbackImg from '../../../assets/images/se009_rose_main_1795533193180.jpg';
import necklaceFallbackImg from '../../../assets/images/kl022_necklace_main_1795533193295.jpg';
import earringFallbackImg from '../../../assets/images/category-earrings.jpg';
import braceletFallbackImg from '../../../assets/images/bl031_bracelet_main_1795533193007.jpg';
import eternityFallbackImg from '../../../assets/images/yz045_eternity_main_1795533194179.jpg';
import baguetteFallbackImg from '../../../assets/images/se014_baguette_main_1795533192126.jpg';
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

const FALLBACK_LABELS: Record<string, string> = {
  YUZUK: 'Yüzük',
  SET: 'Set',
  KUPE: 'Küpe',
  KOLYE: 'Kolye',
  BILEZIK: 'Bilezik',
  ALYANS: 'Alyans',
  BILEKLIK: 'Bileklik',
};

const FALLBACK_BY_CODE: Record<string, { img: string; alt: string }> = {
  YUZUK: {
    img: ringFallbackImg,
    alt: 'TARA DIAMOND pırlanta ve altın yüzük kategorisi',
  },
  SET: {
    img: setFallbackImg,
    alt: 'TARA DIAMOND altın ve pırlanta set kategorisi',
  },
  KUPE: {
    img: earringFallbackImg,
    alt: 'TARA DIAMOND sarı altın küpe kategorisi',
  },
  KOLYE: {
    img: necklaceFallbackImg,
    alt: 'TARA DIAMOND pırlanta kolye kategorisi',
  },
  BILEZIK: {
    img: baguetteFallbackImg,
    alt: 'TARA DIAMOND kelepçe ve bilezik kategorisi',
  },
  ALYANS: {
    img: eternityFallbackImg,
    alt: 'TARA DIAMOND alyans ve tamtur kategorisi',
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

interface CategoryCardItem {
  key: string;
  label: string;
  href: string;
  count: number;
  imageUrl: string;
  alt: string;
}

function EditorialCategoryCard({ cat }: { cat: CategoryCardItem }) {
  return (
    <Link
      to={cat.href}
      className="group relative block aspect-[16/9] w-full overflow-hidden rounded-[6px] bg-card border border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <img
        src={cat.imageUrl}
        alt={cat.alt}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        className="w-full h-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-gradient-to-tr from-white/85 via-white/25 via-40% to-transparent pointer-events-none"
      />
      <span className="absolute bottom-3 left-3.5 z-10 inline-flex items-center gap-1.5 font-sans text-[13px] sm:text-sm font-medium text-foreground leading-none">
        <span>{cat.label}</span>
        <ArrowRight
          className="w-3.5 h-3.5 transition-transform duration-300 group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </span>
    </Link>
  );
}

export function CategoryStrip({ products }: CategoryStripProps) {
  const { options } = usePublicDefinitionOptions('kategori');

  const cards = useMemo<CategoryCardItem[]>(() => {
    if (options.length === 0) {
      return LEGACY_STOREFRONT_CATEGORY_CODES.map((code) => {
        const fb = FALLBACK_BY_CODE[code];
        return {
          key: code,
          label: FALLBACK_LABELS[code] ?? code,
          href: `/koleksiyon?category=${encodeURIComponent(code)}`,
          count: 0,
          imageUrl: fb.img,
          alt: fb.alt,
        };
      });
    }

    const selected = pickStorefrontCategories(options);

    return selected.map((opt) => {
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
        label: opt.label || FALLBACK_LABELS[opt.code] || opt.code,
        href: `/koleksiyon?category=${encodeURIComponent(opt.value)}`,
        count: matching.length,
        imageUrl,
        alt: configuredAlt || fallback.alt,
      };
    });
  }, [options, products]);

  if (cards.length === 0) return null;

  return (
    <section
      aria-labelledby="storefront-categories-heading"
      className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"
    >
      <h2 id="storefront-categories-heading" className="sr-only">
        Mücevher kategorileri
      </h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {cards.map((cat) => (
          <EditorialCategoryCard key={cat.key} cat={cat} />
        ))}
      </div>
    </section>
  );
}

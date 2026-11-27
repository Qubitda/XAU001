import { useMemo } from 'react';
import { Link } from 'react-router-dom';
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
  metaFlag,
  metaString,
} from '../../definitions/storefrontCategories';

const EDITORIAL_MOSAIC_ORDER = [
  'YUZUK',
  'SET',
  'KUPE',
  'KOLYE',
  'BILEZIK',
  'ALYANS',
  'BILEKLIK',
] as const;

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
      className="group block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-[4px]"
    >
      <div className="relative aspect-[4/5] w-full overflow-hidden rounded-[4px] bg-card">
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
          className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-white/75 via-white/35 to-transparent backdrop-blur-md pointer-events-none"
          style={{
            maskImage: 'linear-gradient(to top, black 45%, transparent 100%)',
            WebkitMaskImage: 'linear-gradient(to top, black 45%, transparent 100%)',
          }}
        />
        <div className="relative z-10 mt-auto" />
        <span className="absolute bottom-3.5 left-3.5 z-10 text-left font-serif text-lg sm:text-xl font-medium tracking-tight text-foreground leading-none">
          {cat.label}
        </span>
      </div>
    </Link>
  );
}

export function CategoryStrip({ products }: CategoryStripProps) {
  const { options } = usePublicDefinitionOptions('kategori');

  const cards = useMemo<CategoryCardItem[]>(() => {
    if (options.length === 0) {
      return EDITORIAL_MOSAIC_ORDER.map((code) => {
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

    const flagged = options.filter((o) => metaFlag(o.meta, 'showOnStorefront') === true);
    const orderedCodes = new Map<string, typeof options[number]>();
    for (const code of EDITORIAL_MOSAIC_ORDER) {
      const found = options.find((o) => o.code === code);
      if (found) orderedCodes.set(code, found);
    }
    for (const opt of flagged) {
      if (!orderedCodes.has(opt.code)) orderedCodes.set(opt.code, opt);
    }

    const selected = Array.from(orderedCodes.values()).slice(0, 7);

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
        label: FALLBACK_LABELS[opt.code] ?? opt.label,
        href: `/koleksiyon?category=${encodeURIComponent(opt.value)}`,
        count: matching.length,
        imageUrl,
        alt: configuredAlt || fallback.alt,
      };
    });
  }, [options, products]);

  if (cards.length === 0) return null;

  const visibleCards = cards.slice(0, 6);

  return (
    <section
      aria-labelledby="storefront-categories-heading"
      className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-12 space-y-5 sm:space-y-6"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h2
          id="storefront-categories-heading"
          className="font-serif text-2xl sm:text-3xl font-normal text-foreground"
        >
          Kategoriler
        </h2>
        <Link
          to="/koleksiyon"
          className="text-xs font-medium tracking-[0.08em] uppercase text-muted-foreground hover:text-foreground transition-colors"
        >
          Tüm Koleksiyon
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-5">
        {visibleCards.map((cat) => (
          <EditorialCategoryCard key={cat.key} cat={cat} />
        ))}
      </div>
    </section>
  );
}

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
  BILEZIK: 'Kelepçe',
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

function EditorialCategoryCard({
  cat,
  aspectClass,
}: {
  cat: CategoryCardItem;
  aspectClass: string;
}) {
  return (
    <Link
      to={cat.href}
      className={`group relative ${aspectClass} rounded-[2px] overflow-hidden bg-[#EFECE8] border border-stone-200/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background`}
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
        className="absolute inset-x-0 bottom-0 h-2/5 bg-gradient-to-t from-white/75 via-white/25 to-transparent pointer-events-none"
      />
      <div className="absolute inset-x-0 bottom-0 p-3 sm:p-4 flex items-end justify-between gap-2">
        <span
          className="text-2xl sm:text-3xl leading-none text-stone-900 select-none drop-shadow-[0_1px_2px_rgba(255,255,255,0.9)]"
          style={{ fontFamily: "'Alex Brush', 'Cormorant Garamond', Georgia, serif" }}
        >
          {cat.label}
        </span>
        <span className="shrink-0 px-3 py-1 bg-stone-200/90 backdrop-blur-xs text-stone-800 text-[10px] font-medium tracking-[0.16em] uppercase transition-colors group-hover:bg-stone-900 group-hover:text-white">
          İNCELE
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
        label: opt.label,
        href: `/koleksiyon?category=${encodeURIComponent(opt.value)}`,
        count: matching.length,
        imageUrl,
        alt: configuredAlt || fallback.alt,
      };
    });
  }, [options, products]);

  if (cards.length === 0) return null;

  const topRow = cards.slice(0, 3);
  const bottomRow = cards.slice(3, 7);

  return (
    <section
      aria-labelledby="storefront-categories-heading"
      className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-3 sm:space-y-4"
    >
      <h2 id="storefront-categories-heading" className="sr-only">
        Mücevher kategorileri
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        {topRow.map((cat) => (
          <EditorialCategoryCard key={cat.key} cat={cat} aspectClass="aspect-[4/3] sm:aspect-square" />
        ))}
      </div>

      {bottomRow.length > 0 && (
        <div
          className={`grid grid-cols-2 ${
            bottomRow.length <= 2
              ? 'lg:grid-cols-2'
              : bottomRow.length === 3
                ? 'lg:grid-cols-3'
                : 'lg:grid-cols-4'
          } gap-3 sm:gap-4`}
        >
          {bottomRow.map((cat) => (
            <EditorialCategoryCard key={cat.key} cat={cat} aspectClass="aspect-square" />
          ))}
        </div>
      )}
    </section>
  );
}

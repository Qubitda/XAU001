import { MetalColor, ProductState } from '../types/jewelry';

import se009WhiteMain from '../assets/images/se009_white_main_1795533192415.jpg';
import se009YellowMain from '../assets/images/se009_yellow_main_1795533192654.jpg';
import se009RoseMain from '../assets/images/se009_rose_main_1795533193180.jpg';
import se009WhiteHand from '../assets/images/se009_white_hand_1795533193888.jpg';
import se014BaguetteMain from '../assets/images/se014_baguette_main_1795533192126.jpg';
import se014BaguetteHand from '../assets/images/se014_baguette_hand_1795533194181.jpg';
import kl022NecklaceMain from '../assets/images/kl022_necklace_main_1795533193295.jpg';
import kl022NecklaceModel from '../assets/images/kl022_necklace_model_1795533194072.jpg';
import bl031BraceletMain from '../assets/images/bl031_bracelet_main_1795533193007.jpg';
import bl031BraceletWrist from '../assets/images/bl031_bracelet_wrist_1795533193416.jpg';
import kp018EmeraldMain from '../assets/images/kp018_emerald_main_1795533193415.jpg';
import kp018EmeraldSide from '../assets/images/kp018_emerald_side_1795533194252.jpg';
import yz045EternityMain from '../assets/images/yz045_eternity_main_1795533194179.jpg';
import yz045EternityHand from '../assets/images/yz045_eternity_hand_1795533193354.jpg';

export type MediaAssetKind = 'photo' | 'video' | 'spin360' | 'document' | 'blueprint';

export type MediaBindingLevel = 'VARYANT' | 'RENK' | 'PARENT';

export interface ProductMediaItem {
  id: string;
  kind: MediaAssetKind;
  role: string;
  label: string;
  aspectHint: '4:3' | '1:1' | '9:16' | '16:9';
  url: string;
  posterUrl?: string;
  durationSec?: number;
  binding: MediaBindingLevel;
  sortOrder: number;
  b2cVisible: boolean;
  b2bVisible: boolean;
  toneFilter?: string;
  zoomScale?: number;
  focalPosition?: string;
  description?: string;
}

export interface ResolvedProductMedia {
  mainUrl: string;
  hoverUrl: string;
  hoverLabel: string;
  binding: MediaBindingLevel;
  toneFilter?: string;
}

const MEDIA_REGISTRY: Record<
  string,
  {
    defaultColor: MetalColor;
    hoverLabel: string;
    hoverUrl: string;
    byColor: Partial<Record<MetalColor, string>>;
  }
> = {
  SE009: {
    defaultColor: 'Beyaz',
    hoverLabel: 'Elde Görünüm',
    hoverUrl: se009WhiteHand,
    byColor: {
      Beyaz: se009WhiteMain,
      Sarı: se009YellowMain,
      Rose: se009RoseMain,
    },
  },
  SE014: {
    defaultColor: 'Beyaz',
    hoverLabel: 'Elde Yan Açı',
    hoverUrl: se014BaguetteHand,
    byColor: {
      Beyaz: se014BaguetteMain,
    },
  },
  KL022: {
    defaultColor: 'Sarı',
    hoverLabel: 'Model Üzerinde',
    hoverUrl: kl022NecklaceModel,
    byColor: {
      Sarı: kl022NecklaceMain,
    },
  },
  BL031: {
    defaultColor: 'Beyaz',
    hoverLabel: 'Bilekte Görünüm',
    hoverUrl: bl031BraceletWrist,
    byColor: {
      Beyaz: bl031BraceletMain,
    },
  },
  KP018: {
    defaultColor: 'Sarı',
    hoverLabel: 'Kulakta Yan Açı',
    hoverUrl: kp018EmeraldSide,
    byColor: {
      Sarı: kp018EmeraldMain,
    },
  },
  YZ045: {
    defaultColor: 'Rose',
    hoverLabel: 'Elde Görünüm',
    hoverUrl: yz045EternityHand,
    byColor: {
      Rose: yz045EternityMain,
    },
  },
};

/** Canonical media-registry keys for metal_rengi codes + legacy labels. */
export function canonicalizeMetalColor(color: string): MetalColor {
  const raw = (color || '').trim();
  const upper = raw.toLocaleUpperCase('tr-TR');
  if (upper === 'BEYAZ' || raw === 'Beyaz') return 'Beyaz';
  if (upper === 'SARI' || raw === 'Sarı') return 'Sarı';
  if (upper === 'ROSE' || raw === 'Rose' || raw.startsWith('Rose')) return 'Rose';
  return raw as MetalColor;
}

function computeToneFallbackFilter(
  baseColor: MetalColor,
  targetColor: MetalColor
): string | undefined {
  const base = canonicalizeMetalColor(baseColor);
  const target = canonicalizeMetalColor(targetColor);
  if (base === target) return undefined;
  if (target === 'Beyaz') return 'saturate(0.32) brightness(1.04) contrast(1.03)';
  if (target === 'Sarı') return 'sepia(0.38) saturate(1.45) hue-rotate(-6deg) brightness(1.02)';
  if (target === 'Rose') return 'sepia(0.36) saturate(1.35) hue-rotate(-24deg) brightness(1.01)';
  return undefined;
}

export function resolveProductMedia(
  parentSku: string,
  metalColor: MetalColor,
  galleryImages?: string[]
): ResolvedProductMedia {
  const customPhotos = (galleryImages ?? []).filter((u) => isRenderableMediaUrl(u));
  const entry = MEDIA_REGISTRY[parentSku];
  const tone = canonicalizeMetalColor(metalColor);

  // Prefer color-accurate registry shots so home + collection share the same metal look.
  if (entry) {
    const nativeColorUrl = entry.byColor[tone] ?? entry.byColor[metalColor];
    if (nativeColorUrl) {
      return {
        mainUrl: nativeColorUrl,
        hoverUrl: entry.hoverUrl,
        hoverLabel: entry.hoverLabel,
        binding: 'RENK',
        toneFilter: undefined,
      };
    }

    const fallbackMainUrl =
      customPhotos[0] ??
      entry.byColor[entry.defaultColor] ??
      Object.values(entry.byColor)[0] ??
      '';

    return {
      mainUrl: fallbackMainUrl,
      hoverUrl: customPhotos[1] ?? entry.hoverUrl,
      hoverLabel:
        customPhotos.length > 1 ? 'Galeri Görseli' : entry.hoverLabel,
      binding: customPhotos.length > 0 ? 'RENK' : 'PARENT',
      toneFilter: computeToneFallbackFilter(entry.defaultColor, tone),
    };
  }

  if (customPhotos.length > 0) {
    return {
      mainUrl: customPhotos[0],
      hoverUrl: customPhotos[1] ?? customPhotos[0],
      hoverLabel: customPhotos.length > 1 ? 'Galeri Görseli' : 'Ürün Görseli',
      binding: 'RENK',
      toneFilter: undefined,
    };
  }

  return {
    mainUrl: '',
    hoverUrl: '',
    hoverLabel: '',
    binding: 'PARENT',
    toneFilter: undefined,
  };
}

export function isRenderableMediaUrl(url: string | undefined | null): boolean {
  if (!url) return false;
  const trimmed = url.trim();
  // Reject Vite source paths that resolve to SPA HTML in the browser.
  if (trimmed.startsWith('/src/')) return false;
  return (
    trimmed.startsWith('http://') ||
    trimmed.startsWith('https://') ||
    trimmed.startsWith('/') ||
    trimmed.startsWith('data:image/') ||
    trimmed.startsWith('data:video/')
  );
}

export function resolveProductThumbnail(product: ProductState): string {
  const customMain = (product.galleryImages ?? []).find((u) => isRenderableMediaUrl(u));
  if (customMain) return customMain;
  return resolveProductMedia(product.parentSku, product.metalColor).mainUrl;
}

/**
 * Builds the ordered multi-asset gallery (variant_media rows sorted by sort_order)
 * supporting custom uploaded/URL photos, videos (16:9 sparkle + 9:16 Reels + 360°),
 * and rich content blocks (Certificate Dossier + Technical Dimensions Blueprint).
 */
export function resolveProductGallery(product: ProductState): ProductMediaItem[] {
  const isRegistryProduct = Boolean(MEDIA_REGISTRY[product.parentSku]);
  const base = resolveProductMedia(product.parentSku, product.metalColor, product.galleryImages);
  const tone = canonicalizeMetalColor(product.metalColor);
  const code = tone === 'Beyaz' ? 'BYZ' : tone === 'Sarı' ? 'SRY' : 'RSE';

  const customPhotos = (product.galleryImages ?? []).filter((u) => isRenderableMediaUrl(u));
  const items: ProductMediaItem[] = [];
  let sortOrder = 1;

  if (customPhotos.length > 0) {
    customPhotos.forEach((url, index) => {
      items.push({
        id: `${product.parentSku}-${code}-custom-${index}`,
        kind: 'photo',
        role: index === 0 ? 'GALLERY_MAIN' : `GALLERY_EXTRA_${index}`,
        label: index === 0 ? 'Ana Görsel' : `Galeri Görseli ${index + 1}`,
        aspectHint: '4:3',
        url,
        binding: 'RENK',
        sortOrder: sortOrder++,
        b2cVisible: true,
        b2bVisible: true,
        description: `${product.purityCode} ${product.metalColor} Altın ürün görseli`,
      });
    });
  } else if (isRegistryProduct && base.mainUrl) {
    items.push(
      {
        id: `${product.parentSku}-${code}-main`,
        kind: 'photo',
        role: 'GALLERY_MAIN',
        label: 'Stüdyo Ana Açı',
        aspectHint: '4:3',
        url: base.mainUrl,
        binding: base.binding,
        sortOrder: sortOrder++,
        b2cVisible: true,
        b2bVisible: true,
        toneFilter: base.toneFilter,
        description: `${product.purityCode} ${product.metalColor} Altın stüdyo çekimi`,
      },
      {
        id: `${product.parentSku}-${code}-onhand`,
        kind: 'photo',
        role: 'GALLERY_ON_MODEL',
        label: base.hoverLabel,
        aspectHint: '4:3',
        url: base.hoverUrl,
        binding: base.binding,
        sortOrder: sortOrder++,
        b2cVisible: true,
        b2bVisible: true,
        toneFilter: base.toneFilter,
        description: 'Gerçek ölçek ve duruş referansı',
      },
      {
        id: `${product.parentSku}-${code}-macro`,
        kind: 'photo',
        role: 'GALLERY_MACRO_DETAIL',
        label: 'Taş & Mıhlama Makro',
        aspectHint: '4:3',
        url: base.mainUrl,
        binding: base.binding,
        sortOrder: sortOrder++,
        b2cVisible: true,
        b2bVisible: true,
        toneFilter: base.toneFilter,
        zoomScale: 1.72,
        focalPosition: 'center 52%',
        description: `${product.settingType} mıhlama ve ${product.stoneCutShape} kesim yakın çekim`,
      }
    );
  }

  const posterPrimary = customPhotos[0] ?? base.mainUrl;
  const posterSecondary = customPhotos[1] ?? base.hoverUrl ?? posterPrimary;

  if (isRegistryProduct && posterPrimary) {
    items.push({
      id: `${product.parentSku}-${code}-video-sparkle`,
      kind: 'video',
      role: 'VIDEO_DAYLIGHT_SPARKLE',
      label: 'Gün Işığı Videosu',
      aspectHint: '16:9',
      url: `${product.parentSku}-${code}_daylight_16x9.mp4`,
      posterUrl: posterPrimary,
      durationSec: 12,
      binding: 'RENK',
      sortOrder: sortOrder++,
      b2cVisible: true,
      b2bVisible: true,
      toneFilter: customPhotos.length > 0 ? undefined : base.toneFilter,
      description: 'Doğal gün ışığında taş ateş ve parıltı hareketi (MP4 / HLS)',
    });
  }

  if (product.reelsVideoUrl && product.reelsVideoUrl.trim()) {
    items.push({
      id: `${product.parentSku}-${code}-reels`,
      kind: 'video',
      role: 'REELS_VIDEO_9X16',
      label: 'Reels / Kutu Açılışı',
      aspectHint: '9:16',
      url: product.reelsVideoUrl.trim(),
      posterUrl: posterSecondary,
      durationSec: 18,
      binding: 'RENK',
      sortOrder: sortOrder++,
      b2cVisible: true,
      b2bVisible: true,
      description: 'Dikey 9:16 sosyal medya ve WhatsApp paylaşım videosu',
    });
  }

  if (product.spin360Url && product.spin360Url.trim()) {
    items.push({
      id: `${product.parentSku}-${code}-spin360`,
      kind: 'spin360',
      role: 'SPIN_360',
      label: '360° Dönen Tabla',
      aspectHint: '4:3',
      url: product.spin360Url.trim(),
      binding: 'RENK',
      sortOrder: sortOrder++,
      b2cVisible: true,
      b2bVisible: true,
      description: 'Etkileşimli 360 derece açı incelemesi',
    });
  }

  if (product.certificateFileUrl && product.certificateFileUrl.trim()) {
    items.push({
      id: `${product.parentSku}-cert`,
      kind: 'document',
      role: 'CERTIFICATE_DOSSIER',
      label: `${product.certificateAgency || 'Sertifika'} Sertifika`,
      aspectHint: '4:3',
      url: product.certificateFileUrl.trim(),
      binding: 'VARYANT',
      sortOrder: sortOrder++,
      b2cVisible: true,
      b2bVisible: true,
      description: `Sertifika No: ${product.certificateNumber || '—'} — PDF & Doğrulama`,
    });
  }

  if (isRegistryProduct) {
    items.push({
      id: `${product.parentSku}-blueprint`,
      kind: 'blueprint',
      role: 'TECHNICAL_DIMENSIONS',
      label: 'Ölçü & Mıhlama Şeması',
      aspectHint: '4:3',
      url: `${product.parentSku}_cad_spec.svg`,
      binding: 'PARENT',
      sortOrder: sortOrder++,
      b2cVisible: true,
      b2bVisible: true,
      description: 'Milimetrik genişlik, et kalınlığı ve taç yüksekliği',
    });
  }

  return items;
}

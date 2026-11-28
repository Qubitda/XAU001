import { ApiClientError } from '../../../lib/api/client';

const MISSING_PUBLISH_REASON_LABELS: Record<string, string> = {
  TITLE_REQUIRED: 'Ürün başlığı (en az 4 karakter) gerekli',
  CATEGORY_REQUIRED: 'Kategori seçimi gerekli',
  GROSS_WEIGHT_REQUIRED: 'Brüt ağırlık (en az 0,01 gr) gerekli',
  PUBLISHED_RECIPE_REQUIRED: 'Yayınlanmış fiyat reçetesi gerekli',
  ACTIVE_VARIANT_REQUIRED: 'En az 1 aktif varyant gerekli',
  SALES_CHANNEL_REQUIRED: 'En az 1 satış kanalı seçili olmalı',
  GALLERY_MAIN_MEDIA_REQUIRED: 'En az 1 ana galeri görseli gerekli',
};

export function formatPublishError(err: unknown): string {
  if (!(err instanceof ApiClientError)) {
    return 'Ürün yayınlanırken beklenmeyen bir hata oluştu.';
  }
  if (err.status === 403 || err.code === 'PERMISSION_DENIED') {
    return 'Bu ürünü yayınlama veya yayından kaldırma yetkiniz bulunmuyor.';
  }
  if (err.code === 'USE_PUBLISH_ENDPOINT') {
    return 'Ürünü yayına almak için satırdaki veya modaldaki Yayınla butonunu kullanın.';
  }
  const missing = err.details?.missing;
  if (err.code === 'NOT_PUBLISHABLE' && Array.isArray(missing) && missing.length > 0) {
    const labels = missing.map((code) => MISSING_PUBLISH_REASON_LABELS[code] ?? code);
    return `Ürün yayınlanamadı: ${labels.join(' · ')}.`;
  }
  return err.message || 'Ürün yayınlanırken bir hata oluştu.';
}

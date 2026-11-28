import { Sparkles } from 'lucide-react';
import { Input, Label } from '../../../components/ui';
import type { ProductState } from '../../../types/jewelry';

const FIELD_SELECT_CLASS =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1';

const FIELD_TEXTAREA_CLASS =
  'flex min-h-[76px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1';

function slugifyTurkish(input: string): string {
  const map: Record<string, string> = {
    ç: 'c',
    Ç: 'c',
    ğ: 'g',
    Ğ: 'g',
    ı: 'i',
    İ: 'i',
    ö: 'o',
    Ö: 'o',
    ş: 's',
    Ş: 's',
    ü: 'u',
    Ü: 'u',
  };
  return input
    .split('')
    .map((ch) => map[ch] ?? ch)
    .join('')
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

export function ProductSeoPanel({
  draft,
  fieldErrors,
  onPatchField,
}: {
  draft: ProductState;
  fieldErrors: Record<string, string>;
  onPatchField: <K extends keyof ProductState>(key: K, value: ProductState[K]) => void;
}) {
  const siteOrigin =
    typeof window !== 'undefined' && window.location?.origin
      ? window.location.origin
      : 'https://taradiamond.com.tr';
  const previewSlug = draft.seoSlug || slugifyTurkish(draft.title || draft.parentSku || 'urun');
  const previewUrl = draft.canonicalUrl?.trim() || `${siteOrigin}/urun/${previewSlug}`;
  const metaDesc = draft.metaDescription ?? '';

  return (
    <div className="space-y-5">
      <div className="p-4 border border-border rounded-lg bg-muted/50 space-y-1">
        <div className="text-[11px] font-medium text-muted-foreground">
          Arama Motoru (Google) Canlı Önizleme
        </div>
        <div className="text-xs text-emerald-800 font-mono truncate">{previewUrl}</div>
        <div className="text-base font-medium text-blue-800 leading-snug">
          {draft.metaTitle || draft.title || 'Ürün Meta Başlığı'}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
          {metaDesc ||
            draft.description ||
            'Meta açıklaması burada arama sonucu özeti (meta description) olarak görüntülenir.'}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label className="font-medium">SEO URL Slug</Label>
            <button
              type="button"
              onClick={() =>
                onPatchField(
                  'seoSlug',
                  slugifyTurkish(
                    `${draft.title || draft.parentSku}-${draft.purityCode}-${draft.metalColor}`
                  )
                )
              }
              className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-600 hover:text-foreground cursor-pointer"
            >
              <Sparkles className="w-3 h-3" />
              Başlıktan Üret
            </button>
          </div>
          <Input
            type="text"
            value={draft.seoSlug}
            onChange={(e) => onPatchField('seoSlug', e.target.value)}
            placeholder="0-60-karat-pirlanta-tektas-yuzuk-14k-beyaz"
            className={`${FIELD_SELECT_CLASS} font-mono`}
          />
          {fieldErrors.seoSlug && (
            <p className="text-[11px] text-red-700">{fieldErrors.seoSlug}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label className="font-medium">Meta Başlık (Title Tag)</Label>
            <span
              className={`font-mono text-[11px] ${
                draft.metaTitle.length > 65 ? 'text-warning' : 'text-muted-foreground'
              }`}
            >
              {draft.metaTitle.length} / 60 karakter
            </span>
          </div>
          <Input
            type="text"
            value={draft.metaTitle}
            onChange={(e) => onPatchField('metaTitle', e.target.value)}
            placeholder="0.60 Karat GIA Sertifikalı Pırlanta Tektaş Yüzük"
          />
          {fieldErrors.metaTitle && (
            <p className="text-[11px] text-red-700">{fieldErrors.metaTitle}</p>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="font-medium">Meta Açıklama (Meta Description)</Label>
          <span
            className={`font-mono text-[11px] ${
              metaDesc.length > 160 ? 'text-warning' : 'text-muted-foreground'
            }`}
          >
            {metaDesc.length} / 160 karakter
          </span>
        </div>
        <textarea
          rows={2}
          value={metaDesc}
          onChange={(e) => onPatchField('metaDescription', e.target.value)}
          placeholder="Arama sonuçlarında görünecek kısa, ikna edici ürün özeti..."
          className={FIELD_TEXTAREA_CLASS}
        />
        {fieldErrors.metaDescription && (
          <p className="text-[11px] text-red-700">{fieldErrors.metaDescription}</p>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label className="font-medium block">Pazaryeri / Google Shopping Kategorisi</Label>
          <Input
            type="text"
            value={draft.marketplaceCategory}
            onChange={(e) => onPatchField('marketplaceCategory', e.target.value)}
            placeholder="Takı & Mücevher > Pırlanta > Pırlanta Yüzük"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="font-medium block">Ölçü Rehberi URL</Label>
          <Input
            type="text"
            value={draft.sizeGuideUrl}
            onChange={(e) => onPatchField('sizeGuideUrl', e.target.value)}
            placeholder="/olcu-rehberi veya https://..."
            className={`${FIELD_SELECT_CLASS} font-mono`}
          />
          {fieldErrors.sizeGuideUrl && (
            <p className="text-[11px] text-red-700">{fieldErrors.sizeGuideUrl}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label className="font-medium block">OpenGraph Görsel URL (og:image)</Label>
          <Input
            type="text"
            value={draft.ogImage ?? ''}
            onChange={(e) => onPatchField('ogImage', e.target.value)}
            placeholder="/media/catalog/... veya https://..."
            className={`${FIELD_SELECT_CLASS} font-mono`}
          />
          {fieldErrors.ogImage && (
            <p className="text-[11px] text-red-700">{fieldErrors.ogImage}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label className="font-medium block">Canonical URL</Label>
          <Input
            type="text"
            value={draft.canonicalUrl ?? ''}
            onChange={(e) => onPatchField('canonicalUrl', e.target.value)}
            placeholder="Boş bırakılırsa otomatik ürün URL'si kullanılır"
            className={`${FIELD_SELECT_CLASS} font-mono`}
          />
          {fieldErrors.canonicalUrl && (
            <p className="text-[11px] text-red-700">{fieldErrors.canonicalUrl}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label className="font-medium block">Robots Direktifi</Label>
          <select
            value={draft.robots || 'index,follow'}
            onChange={(e) => onPatchField('robots', e.target.value)}
            className={FIELD_SELECT_CLASS}
          >
            <option value="index,follow">index, follow (Arama motorlarına açık)</option>
            <option value="noindex,follow">noindex, follow (Dizinleme kapalı)</option>
            <option value="noindex,nofollow">noindex, nofollow (Tam gizli)</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <Label className="font-medium block">Anahtar Kelimeler (Keywords)</Label>
          <Input
            type="text"
            value={draft.keywords ?? ''}
            onChange={(e) => onPatchField('keywords', e.target.value)}
            placeholder="pırlanta tektaş, 14 ayar yüzük, gia sertifikalı"
          />
        </div>
      </div>
    </div>
  );
}

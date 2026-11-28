import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  Film,
  Image as ImageIcon,
  Loader2,
  Plus,
  Star,
  Trash2,
  Upload,
} from 'lucide-react';
import { Input, Label } from '../../../components/ui';
import { isRenderableMediaUrl } from '../../../data/productMedia';
import { ApiClientError } from '../../../lib/api/client';
import type { ProductMediaEntry, ProductMediaRole, ProductState } from '../../../types/jewelry';
import { catalogService } from '../services/catalogService';

const GALLERY_ROLE_OPTIONS: { value: ProductMediaRole; label: string }[] = [
  { value: 'GALLERY_MAIN', label: 'Ana Vitrin (GALLERY_MAIN)' },
  { value: 'GALLERY', label: 'Galeri (GALLERY)' },
  { value: 'ON_HAND', label: 'Elde / Model (ON_HAND)' },
  { value: 'MACRO', label: 'Makro Detay (MACRO)' },
  { value: 'DETAIL', label: 'Detay (DETAIL)' },
];

const GALLERY_ROLES_SET = new Set<ProductMediaRole>([
  'GALLERY_MAIN',
  'GALLERY',
  'ON_HAND',
  'MACRO',
  'DETAIL',
]);

function normalizeGalleryEntries(draft: ProductState): ProductMediaEntry[] {
  const fromApi = (draft.mediaItems ?? []).filter((m) => GALLERY_ROLES_SET.has(m.role));
  if (fromApi.length > 0) {
    return [...fromApi].sort((a, b) => a.sortOrder - b.sortOrder);
  }
  return (draft.galleryImages ?? []).map((url, idx) => ({
    url,
    metalColor: draft.metalColor || 'Beyaz',
    role: idx === 0 ? 'GALLERY_MAIN' : 'GALLERY',
    sortOrder: idx + 1,
  }));
}

export function ProductMediaPanel({
  draft,
  colorOptions,
  onSyncGallery,
  onPatchField,
}: {
  draft: ProductState;
  colorOptions: string[];
  onSyncGallery: (entries: ProductMediaEntry[]) => void;
  onPatchField: <K extends keyof ProductState>(key: K, value: ProductState[K]) => void;
}) {
  const [newImageUrl, setNewImageUrl] = useState('');
  const [mediaNotice, setMediaNotice] = useState<string | null>(null);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [uploadingSlot, setUploadingSlot] = useState<string | null>(null);
  const [brokenUrls, setBrokenUrls] = useState<Record<string, boolean>>({});
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const reelsInputRef = useRef<HTMLInputElement | null>(null);
  const spin360InputRef = useRef<HTMLInputElement | null>(null);
  const cleanImgInputRef = useRef<HTMLInputElement | null>(null);
  const certFileInputRef = useRef<HTMLInputElement | null>(null);

  const entries = normalizeGalleryEntries(draft);
  const colors = Array.from(
    new Set([
      ...(colorOptions.length ? colorOptions : ['Beyaz', 'Sarı', 'Rose']),
      ...(draft.availableColors ?? []),
      ...(draft.metalColor ? [draft.metalColor] : []),
    ])
  );

  const commitEntries = (next: ProductMediaEntry[]) => {
    const ordered = next.map((item, idx) => ({
      ...item,
      sortOrder: idx + 1,
    }));
    onSyncGallery(ordered);
  };

  const uploadGalleryFileList = async (files: FileList | File[]) => {
    const arr = Array.from(files);
    if (arr.length === 0) return;
    setMediaNotice(null);
    setMediaError(null);
    setUploadingSlot('gallery');
    const added: ProductMediaEntry[] = [];
    try {
      for (const file of arr) {
        if (!file.type.startsWith('image/')) continue;
        if (file.size > 10 * 1024 * 1024) {
          setMediaError(`"${file.name}" 10 MB sınırını aşıyor.`);
          continue;
        }
        const uploaded = await catalogService.uploadMedia(file, 'image');
        const nextUrl = uploaded.path || uploaded.url;
        added.push({
          url: nextUrl,
          metalColor: draft.metalColor || colors[0] || 'Beyaz',
          role: entries.length === 0 && added.length === 0 ? 'GALLERY_MAIN' : 'GALLERY',
          sortOrder: entries.length + added.length + 1,
        });
      }
      if (added.length > 0) {
        setBrokenUrls((prev) => {
          const copy = { ...prev };
          for (const item of added) delete copy[item.url];
          return copy;
        });
        commitEntries([...entries, ...added]);
        setMediaNotice(`${added.length} görsel sunucuya yüklendi ve galeriye eklendi.`);
      } else if (!mediaError) {
        setMediaError('Lütfen geçerli bir görsel dosyası seçin (JPG, PNG, WEBP, max 10 MB).');
      }
    } catch (err) {
      setMediaError(
        err instanceof ApiClientError ? err.message : 'Görsel yüklenirken bir hata oluştu.'
      );
    } finally {
      setUploadingSlot(null);
    }
  };

  const handleUploadFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      await uploadGalleryFileList(event.target.files);
    }
    event.target.value = '';
  };

  const handleDropZone = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDraggingFiles(false);
    if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
      await uploadGalleryFileList(event.dataTransfer.files);
    }
  };

  const handleAddGalleryUrl = () => {
    const trimmed = newImageUrl.trim();
    if (!trimmed) return;
    setMediaError(null);
    const isValidUrl =
      trimmed.startsWith('https://') ||
      trimmed.startsWith('/media/') ||
      trimmed.startsWith('http://localhost') ||
      trimmed.startsWith('http://127.0.0.1');
    if (!isValidUrl) {
      setMediaError("Görsel URL'si geçerli bir https:// adresi veya /media/ yolu olmalıdır.");
      return;
    }
    if (entries.some((e) => e.url === trimmed)) {
      setMediaNotice('Bu görsel zaten galeride mevcut.');
      return;
    }
    setBrokenUrls((prev) => {
      const copy = { ...prev };
      delete copy[trimmed];
      return copy;
    });
    commitEntries([
      ...entries,
      {
        url: trimmed,
        metalColor: draft.metalColor || colors[0] || 'Beyaz',
        role: entries.length === 0 ? 'GALLERY_MAIN' : 'GALLERY',
        sortOrder: entries.length + 1,
      },
    ]);
    setNewImageUrl('');
    setMediaNotice(null);
  };

  const handleUploadSingleMedia = async (
    field: 'reelsVideoUrl' | 'spin360Url' | 'catalogCleanImageUrl' | 'certificateFileUrl',
    kind: 'image' | 'video' | 'certificate' | 'any',
    event: ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setMediaNotice(null);
    setMediaError(null);
    setUploadingSlot(field);
    try {
      const uploaded = await catalogService.uploadMedia(file, kind);
      const nextUrl = uploaded.path || uploaded.url;
      setBrokenUrls((prev) => {
        const copy = { ...prev };
        delete copy[nextUrl];
        return copy;
      });
      onPatchField(field, nextUrl);
      setMediaNotice(`"${uploaded.filename}" yüklendi.`);
    } catch (err) {
      setMediaError(
        err instanceof ApiClientError ? err.message : 'Dosya yüklenirken bir hata oluştu.'
      );
    } finally {
      setUploadingSlot(null);
      event.target.value = '';
    }
  };

  const handleMove = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= entries.length) return;
    const copy = [...entries];
    const [item] = copy.splice(index, 1);
    copy.splice(target, 0, item);
    commitEntries(copy);
  };

  const handleReorderDrop = (targetIndex: number) => {
    if (dragIndex === null || dragIndex === targetIndex) {
      setDragIndex(null);
      return;
    }
    const copy = [...entries];
    const [item] = copy.splice(dragIndex, 1);
    copy.splice(targetIndex, 0, item);
    setDragIndex(null);
    commitEntries(copy);
  };

  const handleSetMain = (index: number) => {
    const copy = entries.map((item, idx) => ({
      ...item,
      role: idx === index ? ('GALLERY_MAIN' as ProductMediaRole) : item.role === 'GALLERY_MAIN' ? ('GALLERY' as ProductMediaRole) : item.role,
    }));
    const [chosen] = copy.splice(index, 1);
    copy.unshift(chosen);
    commitEntries(copy);
  };

  const isVideoUrl = (u: string) => /\.(mp4|webm|mov)(\?.*)?$/i.test(u) || u.startsWith('data:video/');

  return (
    <div className="space-y-6">
      {/* Gallery Photos + Drag & Drop */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              Ürün Fotoğrafları, Renk Eşleştirme &amp; Sıralama
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Görselleri sürükleyip bırakarak yükleyin, sıralayın ve her görsel için maden rengi / rol seçin.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              multiple
              onChange={(e) => void handleUploadFiles(e)}
              className="hidden"
            />
            <button
              type="button"
              disabled={uploadingSlot === 'gallery'}
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-foreground text-white hover:bg-slate-800 disabled:opacity-60 font-medium cursor-pointer"
            >
              {uploadingSlot === 'gallery' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Upload className="w-3.5 h-3.5" />
              )}
              {uploadingSlot === 'gallery' ? 'Yükleniyor...' : 'Bilgisayardan Görsel Yükle'}
            </button>
          </div>
        </div>

        {/* Drag & Drop Upload Zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDraggingFiles(true);
          }}
          onDragLeave={() => setIsDraggingFiles(false)}
          onDrop={(e) => void handleDropZone(e)}
          className={`rounded-lg border-2 border-dashed p-4 text-center transition-colors ${
            isDraggingFiles
              ? 'border-primary bg-primary/5'
              : 'border-border bg-muted/30 hover:border-muted-foreground/40'
          }`}
        >
          <p className="text-xs text-muted-foreground">
            Görselleri buraya sürükleyip bırakın (JPG, PNG, WEBP, GIF · max 10 MB) veya yukarıdan seçin.
          </p>
        </div>

        {/* Add by URL */}
        <div className="flex flex-col sm:flex-row gap-2">
          <Input
            type="url"
            value={newImageUrl}
            onChange={(e) => setNewImageUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddGalleryUrl();
              }
            }}
            placeholder="/media/catalog/... veya https://..."
            className="flex-1 px-3 py-2 border border-input rounded-md bg-card text-foreground font-mono text-xs"
          />
          <button
            type="button"
            onClick={handleAddGalleryUrl}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 font-medium whitespace-nowrap cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            URL Ekle
          </button>
        </div>

        {mediaError && <p className="text-[11px] font-medium text-destructive">{mediaError}</p>}
        {mediaNotice && <p className="text-[11px] font-medium text-emerald-700">{mediaNotice}</p>}

        {entries.length === 0 ? (
          <div className="p-5 border border-dashed border-input rounded-lg bg-muted/40 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-md border border-border bg-card flex items-center justify-center text-muted-foreground shrink-0">
                <ImageIcon className="w-5 h-5" />
              </div>
              <div>
                <div className="font-medium text-foreground">Henüz ürün fotoğrafı eklenmemiş</div>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Ürünü yayınlamak için en az 1 ana galeri görseli (GALLERY_MAIN) gereklidir.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {entries.map((item, idx) => {
              const renderable = isRenderableMediaUrl(item.url);
              const isBroken = Boolean(brokenUrls[item.url]);
              const isMain = item.role === 'GALLERY_MAIN' || idx === 0;
              return (
                <div
                  key={`${idx}-${item.url.slice(0, 32)}`}
                  draggable
                  onDragStart={() => setDragIndex(idx)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleReorderDrop(idx)}
                  className={`border rounded-lg bg-card overflow-hidden flex flex-col cursor-grab active:cursor-grabbing ${
                    isMain ? 'border-emerald-500/60 ring-1 ring-emerald-500/20' : 'border-border'
                  }`}
                >
                  <div className="aspect-[4/3] bg-muted relative overflow-hidden flex items-center justify-center">
                    {renderable && !isBroken ? (
                      <img
                        src={item.url}
                        alt={`Galeri görseli ${idx + 1}`}
                        referrerPolicy="no-referrer"
                        onError={() => setBrokenUrls((prev) => ({ ...prev, [item.url]: true }))}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="text-center p-4 text-muted-foreground space-y-1.5">
                        <ImageIcon className="w-6 h-6 mx-auto text-muted-foreground" />
                        <div className="text-[11px] font-medium text-foreground">
                          {isBroken ? 'Görsel yüklenemedi' : 'Önizlenemeyen medya'}
                        </div>
                        <div className="font-mono text-[10px] break-all line-clamp-2">{item.url}</div>
                        {isBroken && (
                          <button
                            type="button"
                            onClick={() =>
                              setBrokenUrls((prev) => {
                                const copy = { ...prev };
                                delete copy[item.url];
                                return copy;
                              })
                            }
                            className="inline-flex items-center px-2 py-0.5 rounded border border-input bg-card text-[10px] font-medium text-foreground hover:bg-muted cursor-pointer"
                          >
                            Tekrar Dene
                          </button>
                        )}
                      </div>
                    )}
                    {isMain && (
                      <span className="absolute top-2 left-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-600 text-white text-[10px] font-medium shadow-xs">
                        <Star className="w-2.5 h-2.5 fill-current" />
                        Ana Görsel
                      </span>
                    )}
                  </div>

                  <div className="p-2.5 border-t border-border space-y-2">
                    <div className="grid grid-cols-2 gap-1.5">
                      <select
                        value={item.metalColor}
                        onChange={(e) => {
                          const copy = entries.map((x, i) =>
                            i === idx ? { ...x, metalColor: e.target.value } : x
                          );
                          commitEntries(copy);
                        }}
                        className="h-7 rounded border border-input bg-background px-1.5 text-[11px]"
                        title="Renk eşleştirmesi"
                      >
                        {colors.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                      <select
                        value={item.role}
                        onChange={(e) => {
                          const copy = entries.map((x, i) =>
                            i === idx ? { ...x, role: e.target.value as ProductMediaRole } : x
                          );
                          commitEntries(copy);
                        }}
                        className="h-7 rounded border border-input bg-background px-1.5 text-[11px]"
                        title="Görsel rolü"
                      >
                        {GALLERY_ROLE_OPTIONS.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <div className="font-mono text-[10px] text-muted-foreground truncate">
                        #{idx + 1} · {item.url.startsWith('data:') ? 'Yerel Dosya' : item.url}
                      </div>
                      <div className="flex items-center gap-0.5 shrink-0">
                        {!isMain && (
                          <button
                            type="button"
                            onClick={() => handleSetMain(idx)}
                            title="Ana görsel yap"
                            className="p-1 text-amber-600 hover:bg-amber-50 rounded cursor-pointer"
                          >
                            <Star className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={idx === 0}
                          onClick={() => handleMove(idx, -1)}
                          title="Yukarı taşı"
                          className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-30 cursor-pointer"
                        >
                          <ArrowUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={idx === entries.length - 1}
                          onClick={() => handleMove(idx, 1)}
                          title="Aşağı taşı"
                          className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-30 cursor-pointer"
                        >
                          <ArrowDown className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => commitEntries(entries.filter((_, i) => i !== idx))}
                          title="Görseli çıkar"
                          className="p-1 text-destructive hover:bg-destructive/10 cursor-pointer rounded-md"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Video, 360 Spin, Clean Catalog PNG & Certificate PDF */}
      <div className="pt-4 border-t border-border space-y-3">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">
            Video, 360° Görünüm ve Diğer Görsel Materyaller
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {(
            [
              {
                field: 'reelsVideoUrl',
                label: 'Reels / Ürün Videosu (9:16 MP4 / URL)',
                accept: 'video/mp4,video/webm,video/quicktime',
                kind: 'video',
                inputRef: reelsInputRef,
                clearTitle: 'Videoyu kaldır',
                isImage: false,
                canPreviewVideo: true,
              },
              {
                field: 'spin360Url',
                label: '360° Dönen Tabla Video / Görsel',
                accept: 'video/mp4,video/webm,image/gif,image/png,image/jpeg,image/webp',
                kind: 'any',
                inputRef: spin360InputRef,
                clearTitle: '360° materyali kaldır',
                isImage: true,
                canPreviewVideo: true,
              },
              {
                field: 'catalogCleanImageUrl',
                label: 'Filigransız Katalog Görseli (PNG / Beyaz Fon)',
                accept: 'image/png,image/webp,image/jpeg',
                kind: 'image',
                inputRef: cleanImgInputRef,
                clearTitle: 'Temiz görseli kaldır',
                isImage: true,
                canPreviewVideo: false,
              },
              {
                field: 'certificateFileUrl',
                label: 'Sertifika Dosyası (PDF / Görsel)',
                accept: 'application/pdf,image/jpeg,image/png,image/webp',
                kind: 'certificate',
                inputRef: certFileInputRef,
                clearTitle: 'Sertifika dosyasını kaldır',
                isImage: false,
                canPreviewVideo: false,
              },
            ] as const
          ).map((slot) => {
            const val = draft[slot.field];
            const isBusy = uploadingSlot === slot.field;
            const showVideoPreview = slot.canPreviewVideo && val && isVideoUrl(val);
            const showImgPreview = slot.isImage && val && !isVideoUrl(val) && isRenderableMediaUrl(val);
            return (
              <div key={slot.field} className="space-y-2">
                <Label className="font-medium block">{slot.label}</Label>
                <input
                  ref={slot.inputRef}
                  type="file"
                  accept={slot.accept}
                  onChange={(e) => void handleUploadSingleMedia(slot.field, slot.kind, e)}
                  className="hidden"
                />
                <div className="flex items-center gap-1.5">
                  <Input
                    type="text"
                    value={val}
                    onChange={(e) => onPatchField(slot.field, e.target.value)}
                    placeholder="/media/catalog/... veya https://..."
                    className="flex-1 px-3 py-2 font-mono text-xs border border-input rounded-md bg-card text-foreground"
                  />
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => slot.inputRef.current?.click()}
                    title="Bilgisayardan dosya yükle"
                    className="inline-flex items-center gap-1 px-2.5 py-2 border border-input rounded-md bg-muted/60 hover:bg-muted text-xs font-medium text-foreground shrink-0 cursor-pointer disabled:opacity-60"
                  >
                    {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                    <span>{isBusy ? '...' : 'Yükle'}</span>
                  </button>
                  {val && (
                    <>
                      <a
                        href={val}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Dosyayı yeni sekmede aç"
                        className="p-2 border border-input rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/60"
                      >
                        <ArrowUpRight className="w-3.5 h-3.5" />
                      </a>
                      <button
                        type="button"
                        onClick={() => onPatchField(slot.field, '')}
                        title={slot.clearTitle}
                        className="p-2 border border-input rounded-md text-destructive hover:bg-destructive/10 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                </div>

                {showVideoPreview && (
                  <video
                    src={val}
                    controls
                    muted
                    playsInline
                    className="w-full max-h-40 rounded-md border border-border bg-black"
                  />
                )}
                {showImgPreview && (
                  <img
                    src={val}
                    alt={slot.label}
                    className="h-24 rounded-md border border-border object-contain bg-muted p-1"
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

import { Ruler } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../../components/ui';

interface SizeGuideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  category: string;
}

const TR_RING_SIZES = [
  { tr: 10, diameterMm: '15,9', circumferenceMm: '50,0', note: 'İnce parmak' },
  { tr: 11, diameterMm: '16,2', circumferenceMm: '51,0', note: 'İnce parmak' },
  { tr: 12, diameterMm: '16,5', circumferenceMm: '51,9', note: 'Kadın standart alt' },
  { tr: 13, diameterMm: '16,9', circumferenceMm: '53,1', note: 'Kadın standart' },
  { tr: 14, diameterMm: '17,2', circumferenceMm: '54,0', note: 'En yaygın kadın ölçüsü' },
  { tr: 15, diameterMm: '17,5', circumferenceMm: '55,0', note: 'Kadın standart' },
  { tr: 16, diameterMm: '17,8', circumferenceMm: '56,0', note: 'Orta ölçü' },
  { tr: 17, diameterMm: '18,2', circumferenceMm: '57,2', note: 'Orta / üst ölçü' },
  { tr: 18, diameterMm: '18,5', circumferenceMm: '58,1', note: 'Geniş ölçü' },
];

const CHAIN_LENGTHS = [
  { cm: 40, fit: 'Köprücük kemiği üstü (Choker yakın)' },
  { cm: 42, fit: 'Boyun tabanı klasik oturuş' },
  { cm: 45, fit: 'En çok tercih edilen standart kolye boyu' },
  { cm: 50, fit: 'Göğüs üstü rahat döküm' },
];

export function SizeGuideDialog({ open, onOpenChange, category }: SizeGuideDialogProps) {
  const isRing =
    category === 'YUZUK' || category.toLocaleLowerCase('tr-TR') === 'yüzük';
  const displayCategory =
    category === 'YUZUK'
      ? 'Yüzük'
      : category === 'KOLYE'
        ? 'Kolye'
        : category === 'BILEKLIK'
          ? 'Bileklik'
          : category === 'KUPE'
            ? 'Küpe'
            : category;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showGlow={false}
        className="max-w-lg"
        innerClassName="bg-card border border-border"
      >
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Ruler className="w-4 h-4 text-muted-foreground" />
            <DialogTitle className="font-serif text-xl font-normal text-foreground">
              {isRing ? 'Yüzük Ölçü Rehberi (TR)' : `${displayCategory} Boy Rehberi`}
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            {isRing
              ? 'Mevcut bir yüzüğünüzün iç çapını cetvel ile ölçerek en doğru Türkiye yüzük numarasını belirleyebilirsiniz.'
              : 'Kullanım tercihinize göre en uygun uzunluk ve oturuş bilgisini inceleyin.'}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4 text-xs">
          {isRing ? (
            <>
              <div className="border border-border rounded-[6px] overflow-x-auto bg-white">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-muted border-b border-border text-[11px] text-muted-foreground">
                      <th className="py-2.5 px-3 font-medium">TR Ölçü</th>
                      <th className="py-2.5 px-3 font-medium">İç Çap (mm)</th>
                      <th className="py-2.5 px-3 font-medium">Çevre (mm)</th>
                      <th className="py-2.5 px-3 font-medium">Kullanım Notu</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {TR_RING_SIZES.map((row) => (
                      <tr key={row.tr} className="hover:bg-card">
                        <td className="py-2 px-3 font-mono font-semibold text-foreground tabular-nums">
                          No {row.tr}
                        </td>
                        <td className="py-2 px-3 font-mono text-muted-foreground tabular-nums">
                          {row.diameterMm} mm
                        </td>
                        <td className="py-2 px-3 font-mono text-muted-foreground tabular-nums">
                          {row.circumferenceMm} mm
                        </td>
                        <td className="py-2 px-3 text-muted-foreground">{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                İki ölçü arasında kalıyorsanız büyük olan ölçüyü seçmeniz önerilir. Tektaş ve
                baget yüzüklerde teslimattan sonra ilk 1 yıl içerisinde ±2 numara ücretsiz ölçü
                tadilatı yapılmaktadır.
              </p>
            </>
          ) : (
            <div className="border border-border rounded-[6px] divide-y divide-border bg-white">
              {CHAIN_LENGTHS.map((row) => (
                <div key={row.cm} className="flex items-center justify-between gap-3 px-3.5 py-2.5">
                  <span className="font-mono font-semibold text-foreground tabular-nums shrink-0">
                    {row.cm} cm
                  </span>
                  <span className="text-muted-foreground text-right">{row.fit}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

import { z } from 'zod';

export const productFormSchema = z.object({
  parentSku: z
    .string()
    .trim()
    .min(3, 'Ana model kodu en az 3 karakter olmalıdır.')
    .max(24, 'Ana model kodu en fazla 24 karakter olabilir.')
    .regex(/^[A-Za-z0-9_-]+$/, 'Yalnızca harf, rakam, tire veya alt çizgi kullanabilirsiniz.'),
  title: z
    .string()
    .trim()
    .min(4, 'Ürün başlığı en az 4 karakter olmalıdır.')
    .max(120, 'Ürün başlığı en fazla 120 karakter olabilir.'),
  category: z.string().trim().min(2, 'Kategori zorunludur.'),
  subCategory: z.string().trim().min(2, 'Alt kategori zorunludur.'),
  collection: z.string().trim().min(2, 'Koleksiyon zorunludur.'),
  purityCode: z.enum(['8K', '14K', '18K', '22K', '925']),
  metalColor: z.enum(['Beyaz', 'Sarı', 'Rose']),
  stoneType: z.enum([
    'Pırlanta',
    'Safir',
    'Yakut',
    'Zümrüt',
    'Doğal Zirkon',
    'Turkuaz',
    'Kehribar',
    'Diğer taşlar',
    'Zirkon',
    'Taşsız',
  ]),
  grossWeightGram: z.number().min(0.1, 'Brüt ağırlık 0,10 gr ve üzeri olmalıdır.').max(500),
  centerStoneCarat: z.number().min(0, 'Taş karatı negatif olamaz.').max(100),
  sideStoneCarat: z.number().min(0, 'Yan taş karatı negatif olamaz.').max(100),
  fireRatePct: z.number().min(0, 'Fire oranı negatif olamaz.').max(30),
  stockStatus: z.enum(['Stokta', 'Tükendi', 'Siparişe Özel']),
  stockQty: z.number().int().min(0, 'Stok adedi negatif olamaz.'),
  ownershipType: z.enum(['Öz Mal', 'Konsinye (Emanet)']),
  visualType: z.enum([
    'solitaire_ring',
    'baguette_ring',
    'pendant_necklace',
    'tennis_bracelet',
    'emerald_earring',
    'eternity_ring',
  ]),
  description: z.string().trim().min(6, 'Kısa ürün açıklaması en az 6 karakter olmalıdır.'),
});

export type ProductFormSchemaValues = z.infer<typeof productFormSchema>;

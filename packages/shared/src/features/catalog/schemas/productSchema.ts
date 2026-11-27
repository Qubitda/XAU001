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
  purityCode: z.string().trim().min(1, 'Maden ayarı seçilmelidir.'),
  metalColor: z.string().trim().min(1, 'Varsayılan maden rengi seçilmelidir.'),
  stoneType: z.string().default('Taşsız'),
  grossWeightGram: z
    .number({ message: 'Brüt ağırlık sayısal bir değer olmalıdır.' })
    .min(0.01, 'Brüt ağırlık 0,01 gr ve üzeri olmalıdır.')
    .max(500, 'Brüt ağırlık en fazla 500 gr olabilir.'),
  centerStoneCarat: z.number().min(0, 'Taş karatı negatif olamaz.').max(100).default(0),
  sideStoneCarat: z.number().min(0, 'Yan taş karatı negatif olamaz.').max(100).default(0),
  fireRatePct: z.number().min(0, 'Fire oranı negatif olamaz.').max(30).default(0),
  stockStatus: z.string().default('Stokta'),
  stockQty: z.number().int().min(0, 'Stok adedi negatif olamaz.').default(0),
  ownershipType: z.string().default('Öz Mal'),
  visualType: z.string().default('solitaire_ring'),
  description: z.string().optional().default(''),
  salesChannels: z.array(z.string()).min(1, 'En az bir satış kanalı seçilmelidir.'),
});

export type ProductFormSchemaValues = z.infer<typeof productFormSchema>;

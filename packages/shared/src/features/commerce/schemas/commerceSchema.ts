import { z } from 'zod';

function refineTurkishIdentity(
  data: { isTurkishCitizen: boolean; identityNumber?: string },
  ctx: z.RefinementCtx
) {
  const tckn = (data.identityNumber ?? '').trim();
  if (data.isTurkishCitizen) {
    if (!/^\d{11}$/.test(tckn)) {
      ctx.addIssue({
        code: 'custom',
        path: ['identityNumber'],
        message: 'Türk vatandaşları için 11 haneli TC Kimlik No zorunludur.',
      });
    }
    return;
  }
  if (tckn && !/^\d{11}$/.test(tckn)) {
    ctx.addIssue({
      code: 'custom',
      path: ['identityNumber'],
      message: 'TC Kimlik No girildiyse 11 haneli rakam olmalıdır.',
    });
  }
}

const b2cCheckoutFields = z.object({
  customerName: z.string().trim().min(3, 'Ad Soyad en az 3 karakter olmalıdır.'),
  customerPhone: z
    .string()
    .trim()
    .min(10, 'Sigortalı kurye teslimatı için geçerli telefon numarası giriniz.'),
  customerEmail: z.string().trim().email('Geçerli bir e-posta adresi giriniz.'),
  shippingCity: z.string().trim().min(2, 'Teslimat ili seçiniz.'),
  shippingAddress: z.string().trim().min(10, 'Açık teslimat adresi en az 10 karakter olmalıdır.'),
  isTurkishCitizen: z.boolean().default(true),
  identityNumber: z.string().trim().optional().default(''),
  paymentMethod: z.enum(['CREDIT_CARD', 'BANK_TRANSFER']),
  acceptedCustomPolicy: z.boolean(),
});

export const b2cCheckoutSchema = b2cCheckoutFields.superRefine(refineTurkishIdentity);

export const b2cDeliveryStepSchema = b2cCheckoutFields
  .pick({
    customerName: true,
    customerPhone: true,
    customerEmail: true,
    shippingCity: true,
    shippingAddress: true,
    isTurkishCitizen: true,
    identityNumber: true,
  })
  .superRefine(refineTurkishIdentity);

export type B2cCheckoutFormValues = z.infer<typeof b2cCheckoutSchema>;

export const b2bOrderSchema = z.object({
  dealerName: z.string().trim().min(3, 'Bayi unvanı zorunludur.'),
  taxOfficeAndNo: z.string().trim().min(6, 'Vergi dairesi ve VKN bilgisi zorunludur.'),
  contactPerson: z.string().trim().min(3, 'Sipariş yetkilisi adı zorunludur.'),
  settlementMethod: z.enum([
    'HAS_PLUS_CURRENCY',
    'FX_CASH',
    'CONSIGNMENT',
    'OPEN_ACCOUNT',
  ]),
  rateLockMode: z.enum(['LOCK_ON_ORDER', 'SETTLE_ON_DELIVERY']),
  consignmentDays: z.number().int().min(15).max(90).optional(),
  deliveryMethod: z.enum(['BRINKS_INSURED', 'KAPALICARSI_HANDOVER', 'FACTORY_PICKUP']),
  orderNote: z.string().trim().max(300, 'Sipariş notu en fazla 300 karakter olabilir.').optional(),
  acceptedWeightTolerance: z.boolean().refine((val) => val === true, {
    message: 'Üretim ve terazi ±%5 gramaj tolerans koşulunu onaylamalısınız.',
  }),
});

export type B2bOrderFormValues = z.infer<typeof b2bOrderSchema>;

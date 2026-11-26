import type { MetalColor, PricingCurrency, PurityCode } from '../../../types/jewelry';

export type B2cPaymentMethod = 'CREDIT_CARD' | 'BANK_TRANSFER';

export interface B2cCartItem {
  id: string;
  variantId?: string | null;
  bundleId?: string | null;
  bundleRole?: 'MOUNTING' | 'STONE' | '' | null;
  sku: string;
  parentSku: string;
  title: string;
  category: string;
  metalColor: MetalColor;
  purityCode: PurityCode;
  size: number;
  sizeUnitLabel: string;
  qty: number;
  engravingText: string;
  giftWrap: boolean;
  giftNote: string;
  certificateLabel: string;
  stockStatus: 'Stokta' | 'Tükendi' | 'Siparişe Özel';
  leadTimeText: string;
  grossWeightGram: number;
  unitListPriceTry: number;
  unitFinalPriceTry: number;
  snapshotId: string;
  addedAt: string;
}

export interface PaymentBankAccountRecord {
  id: string;
  bankName: string;
  accountHolder: string;
  iban: string;
  branchCode?: string;
  accountNumber?: string;
  currency: string;
  logoUrl?: string;
}

export interface B2cOrderRecord {
  orderNo: string;
  createdAt: string;
  snapshotId: string;
  goldRateTryPerGram: number;
  customerName: string;
  customerPhone: string;
  customerEmail: string;
  shippingCity: string;
  shippingAddress: string;
  /** Default true — TC Kimlik No required when true */
  isTurkishCitizen?: boolean;
  identityNumber?: string;
  paymentMethod: B2cPaymentMethod;
  acceptedCustomPolicy: boolean;
  items: B2cCartItem[];
  subtotalListTry: number;
  campaignDiscountTry: number;
  transferDiscountTry: number;
  insuredShippingTry: number;
  vatIncludedTry: number;
  grandTotalTry: number;
  status:
    | 'ODEME_BEKLIYOR'
    | 'ONAYLANDI'
    | 'ATOLYE_URETIMDE'
    | 'SIGORTALI_KARGODA'
    | 'IPTAL_EDILDI'
    | 'IADE_EDILDI';
  /** Havale sonrası backend ek alanları */
  transferReference?: string;
  bankAccounts?: PaymentBankAccountRecord[];
  selectedBankAccountId?: string;
  payment?: {
    id: string;
    provider: string;
    status: string;
    transferReference?: string;
    installment?: number;
    cardFamily?: string;
    lastFourDigits?: string;
    basePrice?: string;
    paidPrice?: string;
    bankName?: string;
    iban?: string;
    accountHolder?: string;
  };
}

export interface IyzicoCheckoutInitializeResult {
  orderNo: string;
  conversationId: string;
  token: string;
  paymentPageUrl: string;
  checkoutFormContent?: string;
  tokenExpireTime?: number;
}

export type B2bSettlementMethod =
  | 'HAS_PLUS_CURRENCY'
  | 'FX_CASH'
  | 'CONSIGNMENT'
  | 'OPEN_ACCOUNT';

export type B2bRateLockMode = 'LOCK_ON_ORDER' | 'SETTLE_ON_DELIVERY';

export type B2bSupplyType = 'STOCK' | 'PRODUCTION';

export interface B2bOrderLine {
  id: string;
  variantId?: string | null;
  sku: string;
  parentSku: string;
  title: string;
  category: string;
  metalColor: MetalColor;
  purityCode: PurityCode;
  size: number;
  sizeUnitLabel: string;
  qty: number;
  supplyType: B2bSupplyType;
  dealerStampNote: string;
  unitGrossGram: number;
  /** OPS-only blind-pool internals — absent on dealer API responses. */
  unitNetMetalGram?: number;
  unitFireIncludedFineGram?: number;
  unitLaborAndStoneUsd?: number;
  unitWholesaleUsd: number;
  unitWholesaleTry: number;
  pricingCurrency: PricingCurrency;
  snapshotId: string;
  addedAt: string;
}

export interface DealerAccountProfile {
  organizationId: string;
  dealerCode: string;
  companyName: string;
  taxOfficeAndNo: string;
  contactName: string;
  city: string;
  branchId: string;
  branchName: string;
  creditLimitUsd: number;
  usedCreditUsd: number;
  hasLimitGram: number;
  usedHasGram: number;
  defaultConsignmentDays: number;
}

export interface B2bOrderRecord {
  orderNo: string;
  createdAt: string;
  snapshotId: string;
  usdTryRate: number;
  goldRateTryPerGram: number;
  organizationId: string;
  branchId: string;
  branchName: string;
  createdByUserId: string;
  createdByUserName: string;
  dealerCode: string;
  dealerName: string;
  taxOfficeAndNo: string;
  contactPerson: string;
  settlementMethod: B2bSettlementMethod;
  rateLockMode: B2bRateLockMode;
  consignmentDays?: number;
  deliveryMethod: 'BRINKS_INSURED' | 'KAPALICARSI_HANDOVER' | 'FACTORY_PICKUP';
  orderNote: string;
  acceptedWeightTolerance: boolean;
  lines: B2bOrderLine[];
  totalPieces: number;
  totalGrossGram: number;
  /** OPS-only settlement internals */
  totalHasGoldGram?: number;
  totalLaborAndStoneUsd?: number;
  totalWholesaleUsd: number;
  totalWholesaleTry: number;
  status:
    | 'PROFORMA_ONAYLANDI'
    | 'ATOLYE_PLANLANDI'
    | 'SEVK_HAZIR'
    | 'IPTAL_EDILDI'
    | 'IADE_EDILDI';
}

export interface B2cCartSnapshot {
  items: B2cCartItem[];
  priceLockedUntil: string;
  snapshotId: string;
}

export interface B2bDraftSnapshot {
  lines: B2bOrderLine[];
  dealer: DealerAccountProfile;
  snapshotId: string;
}

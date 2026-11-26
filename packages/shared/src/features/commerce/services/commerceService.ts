import { apiFetch } from '../../../lib/api/client';
import type { ComputedJewelryMetrics, LiveRates, ProductState } from '../../../types/jewelry';
import type {
  B2bDraftSnapshot,
  B2bOrderLine,
  B2bOrderRecord,
  B2bSupplyType,
  B2cCartItem,
  B2cCartSnapshot,
  B2cOrderRecord,
  IyzicoCheckoutInitializeResult,
} from '../types';

export function getSizeUnitLabel(category: ProductState['category']): string {
  const key = (category || '').trim().toLocaleUpperCase('tr-TR');
  if (key === 'KOLYE' || category === 'Kolye') return 'Zincir Boyu';
  if (key === 'BILEKLIK' || category === 'Bileklik') return 'Bileklik Boyu';
  if (key === 'KUPE' || category === 'Küpe') return 'Çap / Boy';
  return 'Yüzük Ölçüsü';
}

function isRingCategoryValue(category: string): boolean {
  return category === 'YUZUK' || category.toLocaleLowerCase('tr-TR') === 'yüzük';
}

function resolveMatchingVariantId(
  product: ProductState,
  targetSize?: number
): string | null {
  const variants = product.variants;
  if (!variants || variants.length === 0) return null;
  const size = targetSize ?? product.variantSize;
  const exact = variants.find(
    (v) =>
      v.purityCode === product.purityCode &&
      v.metalColor === product.metalColor &&
      v.size === size
  );
  if (exact) return exact.id;
  const byPurityAndColor = variants.find(
    (v) => v.purityCode === product.purityCode && v.metalColor === product.metalColor
  );
  if (byPurityAndColor) return byPurityAndColor.id;
  const def = variants.find((v) => v.isDefault);
  return def ? def.id : variants[0].id;
}

export function buildB2cCartItemFromProduct(params: {
  product: ProductState;
  computed: ComputedJewelryMetrics;
  rates: LiveRates;
  qty?: number;
  engravingText?: string;
  giftWrap?: boolean;
  giftNote?: string;
}): Omit<B2cCartItem, 'id' | 'addedAt'> {
  const { product, computed, rates } = params;
  const engravingText = (params.engravingText ?? '').trim().slice(0, 20);
  const isCustomOrOrder = product.stockStatus === 'Siparişe Özel' || engravingText.length > 0;
  return {
    variantId: resolveMatchingVariantId(product, product.variantSize),
    sku: computed.sku,
    parentSku: product.parentSku,
    title: product.title,
    category: product.category,
    metalColor: product.metalColor,
    purityCode: product.purityCode,
    size: product.variantSize,
    sizeUnitLabel: getSizeUnitLabel(product.category),
    qty: Math.max(1, params.qty ?? 1),
    engravingText,
    giftWrap: Boolean(params.giftWrap),
    giftNote: (params.giftNote ?? '').trim().slice(0, 140),
    certificateLabel: `${product.certificateAgency} · ${product.certificateNumber}`,
    stockStatus: product.stockStatus,
    leadTimeText: isCustomOrOrder
      ? '5–7 iş günü atölye üretim + sigortalı teslimat'
      : '1–2 iş günü sigortalı kurye teslimatı',
    grossWeightGram: product.grossWeightGram,
    unitListPriceTry: computed.finalB2cPriceTry,
    unitFinalPriceTry: computed.discountedB2cPriceTry,
    snapshotId: rates.snapshotId,
  };
}

export function buildB2bOrderLineFromProduct(params: {
  product: ProductState;
  computed: ComputedJewelryMetrics;
  rates: LiveRates;
  qty?: number;
  sizeOverride?: number;
  supplyType?: B2bSupplyType;
  dealerStampNote?: string;
}): Omit<B2bOrderLine, 'id' | 'addedAt'> {
  const { product, computed, rates } = params;
  const targetSize = params.sizeOverride ?? product.variantSize;
  const sizeDiff = targetSize - product.variantSize;
  const weightDelta = isRingCategoryValue(product.category)
    ? sizeDiff * 0.07
    : sizeDiff * 0.04;
  const adjustedGross = Math.max(1.0, Number((product.grossWeightGram + weightDelta).toFixed(2)));
  const grossRatio =
    product.grossWeightGram > 0 ? adjustedGross / product.grossWeightGram : 1;

  const adjustedNetMetal = Number((computed.netMetalGram * grossRatio).toFixed(4));
  const adjustedFireIncludedFine = Number(
    (computed.fireIncludedFineMetalGram * grossRatio).toFixed(4)
  );

  // Separate metal value from labor + stone + setting + wholesale margin in USD
  // so HAS_PLUS_CURRENCY settlement charges exact Has Gold (gr) + Labor/Stone USD.
  const usdTry = rates.liveUsdSell > 0 ? rates.liveUsdSell : 42;
  const hasGoldTry = rates.liveHasGoldTrySell > 0 ? rates.liveHasGoldTrySell : 5401.32;
  const metalCostTry = adjustedFireIncludedFine * hasGoldTry;
  const wholesaleTry =
    computed.finalB2bPriceTry +
    (adjustedFireIncludedFine - computed.fireIncludedFineMetalGram) * hasGoldTry;
  const wholesaleUsd = Number((wholesaleTry / usdTry).toFixed(2));
  const laborAndStoneTry = Math.max(0, wholesaleTry - metalCostTry);
  const laborAndStoneUsd = Number((laborAndStoneTry / usdTry).toFixed(2));

  const skuSuffix = targetSize !== product.variantSize ? `-${targetSize}` : '';
  const defaultSupply: B2bSupplyType =
    params.supplyType ?? (product.stockStatus === 'Stokta' ? 'STOCK' : 'PRODUCTION');

  return {
    variantId: resolveMatchingVariantId(product, targetSize),
    sku: `${computed.sku}${skuSuffix}`,
    parentSku: product.parentSku,
    title: product.title,
    category: product.category,
    metalColor: product.metalColor,
    purityCode: product.purityCode,
    size: targetSize,
    sizeUnitLabel: getSizeUnitLabel(product.category),
    qty: Math.max(1, params.qty ?? 1),
    supplyType: defaultSupply,
    dealerStampNote: (params.dealerStampNote ?? '').trim().slice(0, 60),
    unitGrossGram: adjustedGross,
    unitNetMetalGram: adjustedNetMetal,
    unitFireIncludedFineGram: adjustedFireIncludedFine,
    unitLaborAndStoneUsd: laborAndStoneUsd,
    unitWholesaleUsd: wholesaleUsd,
    unitWholesaleTry: Number(wholesaleTry.toFixed(2)),
    pricingCurrency: product.pricingCurrency,
    snapshotId: rates.snapshotId,
  };
}

export const commerceService = {
  // B2C Storefront (/api/v1/storefront/*)
  async getB2cCart(): Promise<B2cCartSnapshot> {
    const res = await apiFetch<B2cCartSnapshot>('/api/v1/storefront/cart');
    return res.data;
  },
  async addB2cCartItem(item: Omit<B2cCartItem, 'id' | 'addedAt'>): Promise<B2cCartSnapshot> {
    const res = await apiFetch<B2cCartSnapshot>('/api/v1/storefront/cart/items', {
      method: 'POST',
      body: item,
    });
    return res.data;
  },
  async updateB2cCartItem(
    id: string,
    patch: Partial<B2cCartItem>
  ): Promise<B2cCartSnapshot> {
    const res = await apiFetch<B2cCartSnapshot>(
      `/api/v1/storefront/cart/items/${encodeURIComponent(id)}`,
      { method: 'PATCH', body: patch }
    );
    return res.data;
  },
  async removeB2cCartItem(id: string): Promise<B2cCartSnapshot> {
    const res = await apiFetch<B2cCartSnapshot>(
      `/api/v1/storefront/cart/items/${encodeURIComponent(id)}`,
      { method: 'DELETE' }
    );
    return res.data;
  },
  async clearB2cCart(): Promise<B2cCartSnapshot> {
    const res = await apiFetch<B2cCartSnapshot>('/api/v1/storefront/cart', {
      method: 'DELETE',
    });
    return res.data;
  },
  async refreshB2cPriceLock(): Promise<B2cCartSnapshot> {
    const res = await apiFetch<B2cCartSnapshot>('/api/v1/storefront/cart/refresh-lock', {
      method: 'POST',
    });
    return res.data;
  },
  async listB2cOrders(): Promise<B2cOrderRecord[]> {
    const res = await apiFetch<B2cOrderRecord[]>('/api/v1/storefront/orders');
    return res.data;
  },
  async submitB2cOrder(
    payload: Omit<B2cOrderRecord, 'orderNo' | 'createdAt' | 'items' | 'status'>
  ): Promise<B2cOrderRecord> {
    const res = await apiFetch<B2cOrderRecord>('/api/v1/storefront/orders', {
      method: 'POST',
      body: payload,
    });
    return res.data;
  },
  async initializeIyzicoCheckout(
    payload: Omit<B2cOrderRecord, 'orderNo' | 'createdAt' | 'items' | 'status'>
  ): Promise<IyzicoCheckoutInitializeResult> {
    const res = await apiFetch<IyzicoCheckoutInitializeResult>(
      '/api/v1/storefront/payments/checkout-form/initialize',
      { method: 'POST', body: { ...payload, paymentMethod: 'CREDIT_CARD' } }
    );
    return res.data;
  },

  // B2B Organization-Isolated Portal (/api/v1/b2b/*)
  async getB2bDraft(): Promise<B2bDraftSnapshot> {
    const res = await apiFetch<B2bDraftSnapshot>('/api/v1/b2b/draft');
    return res.data;
  },
  async addB2bDraftLines(
    lines: Omit<B2bOrderLine, 'id' | 'addedAt'> | Array<Omit<B2bOrderLine, 'id' | 'addedAt'>>
  ): Promise<B2bDraftSnapshot> {
    const res = await apiFetch<B2bDraftSnapshot>('/api/v1/b2b/draft/lines', {
      method: 'POST',
      body: lines,
    });
    return res.data;
  },
  async updateB2bDraftLine(
    id: string,
    patch: Partial<B2bOrderLine>
  ): Promise<B2bDraftSnapshot> {
    const res = await apiFetch<B2bDraftSnapshot>(
      `/api/v1/b2b/draft/lines/${encodeURIComponent(id)}`,
      { method: 'PATCH', body: patch }
    );
    return res.data;
  },
  async removeB2bDraftLine(id: string): Promise<B2bDraftSnapshot> {
    const res = await apiFetch<B2bDraftSnapshot>(
      `/api/v1/b2b/draft/lines/${encodeURIComponent(id)}`,
      { method: 'DELETE' }
    );
    return res.data;
  },
  async clearB2bDraft(): Promise<B2bDraftSnapshot> {
    const res = await apiFetch<B2bDraftSnapshot>('/api/v1/b2b/draft', {
      method: 'DELETE',
    });
    return res.data;
  },
  async listB2bOrders(): Promise<B2bOrderRecord[]> {
    const res = await apiFetch<B2bOrderRecord[]>('/api/v1/b2b/orders');
    return res.data;
  },
  async submitB2bOrder(
    payload: Omit<B2bOrderRecord, 'orderNo' | 'createdAt' | 'lines' | 'status'>
  ): Promise<B2bOrderRecord> {
    const res = await apiFetch<B2bOrderRecord>('/api/v1/b2b/orders', {
      method: 'POST',
      body: payload,
    });
    return res.data;
  },
  async reorderB2bOrder(orderNo: string): Promise<B2bDraftSnapshot> {
    const res = await apiFetch<B2bDraftSnapshot>(
      `/api/v1/b2b/orders/${encodeURIComponent(orderNo)}/reorder`,
      { method: 'POST' }
    );
    return res.data;
  },

  // OPS Fulfillment Status Controls (/api/v1/ops/*)
  async updateB2cOrderStatus(
    orderNo: string,
    status: B2cOrderRecord['status']
  ): Promise<B2cOrderRecord[]> {
    const res = await apiFetch<B2cOrderRecord[]>(
      `/api/v1/ops/b2c-orders/${encodeURIComponent(orderNo)}/status`,
      { method: 'PATCH', body: { status } }
    );
    return res.data;
  },
  async updateB2bOrderStatus(
    orderNo: string,
    status: B2bOrderRecord['status']
  ): Promise<B2bOrderRecord[]> {
    const res = await apiFetch<B2bOrderRecord[]>(
      `/api/v1/ops/b2b-orders/${encodeURIComponent(orderNo)}/status`,
      { method: 'PATCH', body: { status } }
    );
    return res.data;
  },

  // Storefront Favorites (/api/v1/storefront/favorites)
  async listFavorites(): Promise<string[]> {
    const res = await apiFetch<string[]>('/api/v1/storefront/favorites');
    return res.data;
  },
  async toggleFavorite(parentSku: string): Promise<string[]> {
    const res = await apiFetch<string[]>('/api/v1/storefront/favorites/toggle', {
      method: 'POST',
      body: { parentSku },
    });
    return res.data;
  },
};

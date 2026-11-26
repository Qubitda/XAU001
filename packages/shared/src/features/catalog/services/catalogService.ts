import { apiFetch } from '../../../lib/api/client';
import type { AudienceRole } from '../../../types/jewelry';
import type {
  BuyerQuoteDto,
  LiveRatesDto,
  ProductDto,
  UpdateProductRequest,
  UpdateRatesRequest,
} from '../../../lib/api/openapi';

function resolveProductsNamespace(role: AudienceRole): string {
  if (role === 'erp') return '/api/v1/ops/products';
  if (role === 'b2b') return '/api/v1/b2b/products';
  return '/api/v1/storefront/products';
}

export const catalogService = {
  async listProducts(role: AudienceRole = 'b2c'): Promise<ProductDto[]> {
    const res = await apiFetch<ProductDto[]>(resolveProductsNamespace(role));
    return res.data;
  },

  async getProduct(parentSku: string, role: AudienceRole = 'b2c'): Promise<ProductDto> {
    const res = await apiFetch<ProductDto>(
      `${resolveProductsNamespace(role)}/${encodeURIComponent(parentSku)}`
    );
    return res.data;
  },

  async requestQuote(params: {
    parentSku: string;
    channel: 'B2B' | 'B2C';
    variantId?: string;
    variantSku?: string;
    purityCode?: string;
    metalColor?: string;
    size?: number;
  }): Promise<BuyerQuoteDto> {
    const endpoint =
      params.channel === 'B2B' ? '/api/v1/b2b/quotes' : '/api/v1/storefront/quotes';
    const res = await apiFetch<BuyerQuoteDto>(endpoint, {
      method: 'POST',
      body: params,
    });
    return res.data;
  },

  async createProduct(payload: ProductDto): Promise<ProductDto> {
    const res = await apiFetch<ProductDto>('/api/v1/ops/products', {
      method: 'POST',
      body: payload,
    });
    return res.data;
  },

  async updateProduct(parentSku: string, patch: UpdateProductRequest): Promise<ProductDto> {
    const res = await apiFetch<ProductDto>(
      `/api/v1/ops/products/${encodeURIComponent(parentSku)}`,
      {
        method: 'PATCH',
        body: patch,
      }
    );
    return res.data;
  },

  async deleteProduct(parentSku: string): Promise<{ parentSku: string; deleted: boolean }> {
    const res = await apiFetch<{ parentSku: string; deleted: boolean }>(
      `/api/v1/ops/products/${encodeURIComponent(parentSku)}`,
      {
        method: 'DELETE',
      }
    );
    return res.data;
  },

  async getLiveRates(): Promise<LiveRatesDto> {
    const res = await apiFetch<LiveRatesDto>('/api/v1/market/rates');
    return res.data;
  },

  async updateLiveRates(patch: UpdateRatesRequest): Promise<LiveRatesDto> {
    const res = await apiFetch<LiveRatesDto>('/api/v1/ops/rates', {
      method: 'PATCH',
      body: patch,
    });
    return res.data;
  },
};

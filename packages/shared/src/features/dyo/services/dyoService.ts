import { apiFetch } from '../../../lib/api/client';
import type {
  CompatibleStonesQuery,
  CompatibleStonesResponse,
  CreateDyoBundleInput,
  DyoAudience,
  DyoBundleDto,
  DyoValidateResponse,
} from '../types';

function dyoBase(audience: DyoAudience = 'b2c'): string {
  return audience === 'b2b' ? '/api/v1/b2b/dyo' : '/api/v1/storefront/dyo';
}

function stonesPath(query: CompatibleStonesQuery, audience: DyoAudience = 'b2c'): string {
  const params = new URLSearchParams();
  params.set('mountingSku', query.mountingSku);
  if (query.color) params.set('color', query.color);
  if (query.clarity) params.set('clarity', query.clarity);
  if (query.limit) params.set('limit', String(query.limit));
  return `${dyoBase(audience)}/compatible-stones?${params.toString()}`;
}

export const dyoService = {
  async getCompatibleStones(
    query: CompatibleStonesQuery,
    audience: DyoAudience = 'b2c'
  ): Promise<CompatibleStonesResponse> {
    const res = await apiFetch<CompatibleStonesResponse>(stonesPath(query, audience));
    return res.data;
  },

  async validate(
    mountingSku: string,
    stoneSku: string,
    audience: DyoAudience = 'b2c'
  ): Promise<DyoValidateResponse> {
    const res = await apiFetch<DyoValidateResponse>(`${dyoBase(audience)}/validate`, {
      method: 'POST',
      body: { mountingSku, stoneSku },
    });
    return res.data;
  },

  async createBundle(input: CreateDyoBundleInput): Promise<DyoBundleDto> {
    const audience = input.audience ?? 'b2c';
    const res = await apiFetch<DyoBundleDto>(`${dyoBase(audience)}/bundles`, {
      method: 'POST',
      body: {
        mountingSku: input.mountingSku,
        stoneSku: input.stoneSku,
        addToCart: input.addToCart ?? true,
      },
    });
    return res.data;
  },

  async getBundle(bundleId: string, audience: DyoAudience = 'b2c'): Promise<DyoBundleDto> {
    const res = await apiFetch<DyoBundleDto>(
      `${dyoBase(audience)}/bundles/${encodeURIComponent(bundleId)}`
    );
    return res.data;
  },

  async extendBundle(bundleId: string, audience: DyoAudience = 'b2c'): Promise<DyoBundleDto> {
    const res = await apiFetch<DyoBundleDto>(
      `${dyoBase(audience)}/bundles/${encodeURIComponent(bundleId)}`,
      { method: 'POST' }
    );
    return res.data;
  },

  async deleteBundle(
    bundleId: string,
    audience: DyoAudience = 'b2c'
  ): Promise<{ id: string; deleted: boolean }> {
    const res = await apiFetch<{ id: string; deleted: boolean }>(
      `${dyoBase(audience)}/bundles/${encodeURIComponent(bundleId)}`,
      { method: 'DELETE' }
    );
    return res.data;
  },
};

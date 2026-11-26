import { apiFetch } from '../../../lib/api/client';
import type { DefinitionItem, DefinitionTable, DefinitionsPayload } from '../types';

const EMPTY_PAYLOAD: DefinitionsPayload = {
  tables: [],
  salesChannels: [],
};

export const STOREFRONT_DEFINITION_TABLES = ['kategori', 'alt_kategori', 'metal_rengi'] as const;

export const definitionsService = {
  /** OPS-authenticated full catalog (includes inactive + all tables). */
  async listAll(): Promise<DefinitionsPayload> {
    const res = await apiFetch<DefinitionsPayload>('/api/v1/ops/definitions?includeItems=true');
    return res.data ?? EMPTY_PAYLOAD;
  },

  /**
   * Public storefront definitions (AllowAny).
   * Defaults to kategori / alt_kategori / metal_rengi — code saklama SSOT.
   */
  async listPublic(
    tables: readonly string[] = STOREFRONT_DEFINITION_TABLES
  ): Promise<DefinitionsPayload> {
    const qs =
      tables.length > 0 ? `?tables=${tables.map(encodeURIComponent).join(',')}` : '';
    const res = await apiFetch<DefinitionsPayload>(`/api/v1/storefront/definitions${qs}`);
    return res.data ?? EMPTY_PAYLOAD;
  },

  async listTable(tableCode: string): Promise<DefinitionTable | null> {
    const res = await apiFetch<DefinitionTable>(`/api/v1/ops/definitions/${encodeURIComponent(tableCode)}`);
    return res.data ?? null;
  },

  async createItem(
    tableCode: string,
    payload: { code: string; label: string; meta?: Record<string, unknown> }
  ): Promise<DefinitionItem> {
    const res = await apiFetch<DefinitionItem>(
      `/api/v1/ops/definitions/${encodeURIComponent(tableCode)}/items`,
      { method: 'POST', body: payload }
    );
    return res.data;
  },
};

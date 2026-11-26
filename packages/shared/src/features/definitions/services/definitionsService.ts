import { apiFetch } from '../../../lib/api/client';
import type { DefinitionItem, DefinitionTable, DefinitionsPayload } from '../types';

export const definitionsService = {
  async listAll(): Promise<DefinitionsPayload> {
    const res = await apiFetch<DefinitionsPayload>('/api/v1/ops/definitions?includeItems=true');
    return (
      res.data ?? {
        tables: [],
        salesChannels: [],
      }
    );
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

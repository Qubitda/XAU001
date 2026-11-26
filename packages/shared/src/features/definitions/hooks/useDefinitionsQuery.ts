import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getActiveSalesChannels } from '../../../constants/salesChannels';
import { isSalesChannelEnabled } from '../../../config/commercialModules';
import { definitionsService } from '../services/definitionsService';
import type { DefinitionItem, DefinitionTable } from '../types';

export const definitionsQueryKeys = {
  all: ['definitions'] as const,
};

export type DefinitionOption = {
  value: string;
  label: string;
  code: string;
  id: string;
  meta: Record<string, unknown>;
  parentCodes: string[];
  parentLabels: string[];
};

function valueStrategyFor(table: DefinitionTable | undefined, tableCode: string): string {
  if (table?.usage?.valueStrategy) return table.usage.valueStrategy;
  // Legacy fallback only when usage catalog not yet loaded.
  return tableCode === 'ayar_kodu' ? 'code' : 'label';
}

function toOption(table: DefinitionTable | undefined, tableCode: string, item: DefinitionItem): DefinitionOption {
  const strategy = valueStrategyFor(table, tableCode);
  return {
    value: strategy === 'code' ? item.code : item.label,
    label: item.label,
    code: item.code,
    id: item.id,
    meta: item.meta ?? {},
    parentCodes: item.parentCodes ?? [],
    parentLabels: item.parentLabels ?? [],
  };
}

export function matchesParent(option: DefinitionOption, parentValue: string): boolean {
  const value = (parentValue || '').trim();
  if (!value) return false;
  return option.parentCodes.includes(value) || option.parentLabels.includes(value);
}

export function filterOptionsByParent(
  options: DefinitionOption[],
  parentValue: string
): DefinitionOption[] {
  const value = (parentValue || '').trim();
  if (!value) return [];
  return options.filter((o) => matchesParent(o, value));
}

export function useDefinitionsQuery(enabled = true) {
  return useQuery({
    queryKey: definitionsQueryKeys.all,
    queryFn: () => definitionsService.listAll(),
    enabled,
    staleTime: 60_000,
  });
}

export function useDefinitionOptions(tableCode: string, enabled = true) {
  const query = useDefinitionsQuery(enabled);

  const table = useMemo(
    () => query.data?.tables.find((t) => t.code === tableCode),
    [query.data, tableCode]
  );

  const items = useMemo(() => {
    return (table?.items ?? []).filter((i) => i.isActive);
  }, [table]);

  const options = useMemo(
    () => items.map((item) => toOption(table, tableCode, item)),
    [items, table, tableCode]
  );

  return {
    ...query,
    table,
    items,
    options,
  };
}

/** Build purity → fineness map from ayar_kodu definition meta (SSOT). */
export function usePurityFinenessMap(enabled = true) {
  const { items, isLoading, isError } = useDefinitionOptions('ayar_kodu', enabled);
  const map = useMemo(() => {
    const out: Record<string, number> = {};
    for (const item of items) {
      const raw = item.meta?.fineness;
      if (raw == null) continue;
      const n = Number(raw);
      if (Number.isFinite(n)) {
        out[item.code] = n;
        out[item.label] = n;
      }
    }
    return out;
  }, [items]);
  return { map, isLoading, isError };
}

/**
 * Child options filtered by parent relation.
 * parentValue may be parent label or code.
 */
export function useRelatedDefinitionOptions(
  childTableCode: string,
  parentValue: string,
  enabled = true
) {
  const query = useDefinitionOptions(childTableCode, enabled);

  const options = useMemo(
    () => filterOptionsByParent(query.options, parentValue),
    [query.options, parentValue]
  );

  return {
    ...query,
    options,
  };
}

export function useDefinitionTablesMap(enabled = true) {
  const query = useDefinitionsQuery(enabled);
  const byCode = useMemo(() => {
    const map = new Map<string, DefinitionTable>();
    for (const t of query.data?.tables ?? []) map.set(t.code, t);
    return map;
  }, [query.data]);

  const salesChannels = (
    query.data?.salesChannels?.length
      ? query.data.salesChannels
      : getActiveSalesChannels().map((c) => ({ ...c, isSystem: true }))
  ).filter((c) => isSalesChannelEnabled(c.code));

  return { ...query, byCode, salesChannels };
}

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getActiveSalesChannels } from '../../../constants/salesChannels';
import { isSalesChannelEnabled } from '../../../config/commercialModules';
import {
  STOREFRONT_DEFINITION_TABLES,
  definitionsService,
} from '../services/definitionsService';
import type { DefinitionItem, DefinitionTable } from '../types';

export const definitionsQueryKeys = {
  all: ['definitions'] as const,
  public: ['definitions', 'public'] as const,
};

/** Tables that persist product field values as definition codes (not display labels). */
const CODE_STRATEGY_TABLES = new Set([
  'ayar_kodu',
  'kategori',
  'alt_kategori',
  'metal_rengi',
]);

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
  return CODE_STRATEGY_TABLES.has(tableCode) ? 'code' : 'label';
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

/** All aliases for a definition option (value + code + label). */
export function definitionAliases(option: Pick<DefinitionOption, 'value' | 'code' | 'label'>): string[] {
  return Array.from(
    new Set([option.value, option.code, option.label].map((s) => s.trim()).filter(Boolean))
  );
}

export function findDefinitionOption(
  options: DefinitionOption[],
  storedOrFilter: string
): DefinitionOption | undefined {
  const needle = (storedOrFilter || '').trim();
  if (!needle) return undefined;
  return options.find((o) => definitionAliases(o).includes(needle));
}

/**
 * Match a stored product field (code or legacy label) against a filter value
 * (option.value / code / label). Bridges pre-code-strategy catalog rows.
 */
export function matchesDefinitionValue(
  stored: string,
  filterValue: string,
  options: DefinitionOption[] = []
): boolean {
  const s = (stored || '').trim();
  const f = (filterValue || '').trim();
  if (!s || !f) return false;
  if (s === f) return true;
  if (options.length === 0) {
    return s.toLocaleLowerCase('tr-TR') === f.toLocaleLowerCase('tr-TR');
  }
  const filterOpt = findDefinitionOption(options, f);
  if (filterOpt) return definitionAliases(filterOpt).includes(s);
  const storedOpt = findDefinitionOption(options, s);
  if (storedOpt) return definitionAliases(storedOpt).includes(f);
  return s.toLocaleLowerCase('tr-TR') === f.toLocaleLowerCase('tr-TR');
}

export function resolveDefinitionLabel(
  stored: string,
  options: DefinitionOption[]
): string {
  const s = (stored || '').trim();
  if (!s) return '';
  return findDefinitionOption(options, s)?.label ?? s;
}

/** Ring category detection for size guides / media (code or legacy label). */
export function isRingCategory(stored: string): boolean {
  const s = (stored || '').trim();
  if (!s) return false;
  if (s === 'YUZUK') return true;
  return s.toLocaleLowerCase('tr-TR') === 'yüzük';
}

export function useDefinitionsQuery(enabled = true) {
  return useQuery({
    queryKey: definitionsQueryKeys.all,
    queryFn: () => definitionsService.listAll(),
    enabled,
    staleTime: 60_000,
  });
}

/** Public (unauthenticated) definitions for B2C/B2B storefront nav & filters. */
export function usePublicDefinitionsQuery(enabled = true) {
  return useQuery({
    queryKey: definitionsQueryKeys.public,
    queryFn: () => definitionsService.listPublic(STOREFRONT_DEFINITION_TABLES),
    enabled,
    staleTime: 60_000,
  });
}

function useOptionsFromQuery(
  query: ReturnType<typeof useDefinitionsQuery>,
  tableCode: string
) {
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

export function useDefinitionOptions(tableCode: string, enabled = true) {
  return useOptionsFromQuery(useDefinitionsQuery(enabled), tableCode);
}

export function usePublicDefinitionOptions(tableCode: string, enabled = true) {
  return useOptionsFromQuery(usePublicDefinitionsQuery(enabled), tableCode);
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

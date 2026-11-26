/**
 * Storefront category helpers — driven by kategori definition meta:
 * - showOnStorefront: include in CategoryStrip / nav / footer
 * - storefrontImageUrl / storefrontImageAlt: optional card media
 */

import type { DefinitionOption } from './hooks/useDefinitionsQuery';

export const LEGACY_STOREFRONT_CATEGORY_CODES = [
  'YUZUK',
  'KOLYE',
  'KUPE',
  'BILEKLIK',
] as const;

export function metaFlag(meta: Record<string, unknown>, key: string): boolean | undefined {
  if (!(key in meta)) return undefined;
  const v = meta[key];
  if (typeof v === 'boolean') return v;
  if (v === 1 || v === '1' || v === 'true' || v === 'True') return true;
  if (v === 0 || v === '0' || v === 'false' || v === 'False') return false;
  return undefined;
}

export function metaString(meta: Record<string, unknown>, key: string): string {
  const v = meta[key];
  return typeof v === 'string' ? v.trim() : '';
}

/**
 * Categories visible on B2C (strip, filter tabs, footer).
 * Prefer meta.showOnStorefront === true; until any flag exists, fall back to legacy codes.
 */
export function pickStorefrontCategories(options: DefinitionOption[]): DefinitionOption[] {
  if (options.length === 0) return [];

  const flagged = options.filter((o) => metaFlag(o.meta, 'showOnStorefront') === true);
  if (flagged.length > 0) {
    return [...flagged].sort((a, b) => options.indexOf(a) - options.indexOf(b));
  }

  const legacy = LEGACY_STOREFRONT_CATEGORY_CODES.map((code) =>
    options.find((o) => o.code === code)
  ).filter((o): o is DefinitionOption => Boolean(o));

  return legacy.length > 0 ? legacy : options.slice(0, 4);
}

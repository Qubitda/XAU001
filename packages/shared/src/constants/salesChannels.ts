/**
 * Hardcoded product sales channels — operational flow depends on these codes.
 * Not editable via OPS Tanım Tabloları.
 * Deployment entitlement filters via VITE_ENABLED_SALES_CHANNELS.
 */
import { getEnabledSalesChannels, isSalesChannelEnabled } from '../config/commercialModules';

export const SALES_CHANNELS = [
  { code: 'B2B', label: 'B2B (Bayi Portalı)' },
  { code: 'B2B_API', label: 'B2B API' },
  { code: 'B2C_API', label: 'B2C API' },
] as const;

export type SalesChannelCode = (typeof SALES_CHANNELS)[number]['code'];

export const SALES_CHANNEL_CODES: SalesChannelCode[] = SALES_CHANNELS.map((c) => c.code);

/** Channels enabled for this customer deployment (purchased modules). */
export function getActiveSalesChannels(): Array<{ code: SalesChannelCode; label: string }> {
  const enabled = new Set(getEnabledSalesChannels());
  return SALES_CHANNELS.filter((c) => enabled.has(c.code)).map((c) => ({ ...c }));
}

export function salesChannelLabel(code: string): string {
  return SALES_CHANNELS.find((c) => c.code === code)?.label ?? code;
}

/** Legacy B2C → B2C_API */
export function normalizeSalesChannel(code: string): SalesChannelCode | null {
  const raw = (code || '').trim().toUpperCase().replace(/[-\s]/g, '_');
  if (raw === 'B2C') return isSalesChannelEnabled('B2C_API') ? 'B2C_API' : null;
  if ((SALES_CHANNEL_CODES as string[]).includes(raw)) {
    return isSalesChannelEnabled(raw) ? (raw as SalesChannelCode) : null;
  }
  return null;
}

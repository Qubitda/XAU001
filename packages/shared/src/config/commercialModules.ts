/**
 * Deployment-level commercial modules (what the customer purchased).
 *
 * B2C storefront and B2C API are separate products:
 * - Storefront off → hide "B2C Vitrin / Mağazaya Dön" cross-links
 * - B2C_API off → hide B2C_API from product sales-channel pickers
 *
 * Defaults keep all modules on for local monorepo development.
 */

function envFlag(name: string, defaultValue = true): boolean {
  const raw = (import.meta.env[name] as string | undefined)?.trim().toLowerCase();
  if (raw == null || raw === '') return defaultValue;
  return !['0', 'false', 'off', 'no'].includes(raw);
}

function parseChannelList(raw: string | undefined): string[] | null {
  if (raw == null || !raw.trim()) return null;
  return raw
    .split(',')
    .map((c) => c.trim().toUpperCase())
    .filter(Boolean);
}

/** Optional B2C reference storefront UI (apps/frontend/storefront). */
export function isB2cStorefrontEnabled(): boolean {
  return envFlag('VITE_ENABLE_B2C_STOREFRONT', true);
}

/** Optional B2B dealer portal UI (apps/frontend/b2b). */
export function isB2bPortalEnabled(): boolean {
  return envFlag('VITE_ENABLE_B2B_PORTAL', true);
}

/** Optional OPS console UI (apps/frontend/ops). */
export function isOpsPortalEnabled(): boolean {
  return envFlag('VITE_ENABLE_OPS_PORTAL', true);
}

/**
 * Optional B2C card payments via iyzico Checkout Form (apps/backend/apps/payments).
 * Pair with backend ENABLE_IYZICO_PAYMENTS=1. Off → storefront only offers bank transfer.
 */
export function isIyzicoPaymentsEnabled(): boolean {
  return envFlag('VITE_ENABLE_IYZICO_PAYMENTS', true);
}

/**
 * Enabled product sales channels for this deployment.
 * Env: VITE_ENABLED_SALES_CHANNELS=B2B,B2B_API  (omit B2C_API if not purchased)
 */
export function getEnabledSalesChannels(): string[] {
  const parsed = parseChannelList(import.meta.env.VITE_ENABLED_SALES_CHANNELS as string | undefined);
  if (parsed?.length) return parsed;
  return ['B2B', 'B2B_API', 'B2C_API'];
}

export function isSalesChannelEnabled(code: string): boolean {
  const normalized = (code || '').trim().toUpperCase().replace(/[-\s]/g, '_');
  const key = normalized === 'B2C' ? 'B2C_API' : normalized;
  return getEnabledSalesChannels().includes(key);
}

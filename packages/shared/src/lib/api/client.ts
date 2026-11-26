import type {
  ApiEnvelope,
  ApiErrorPayload,
  SessionUserDto,
} from './openapi';

export class ApiClientError extends Error {
  status: number;
  code: string;
  details?: Record<string, string[]>;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

export interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

interface RemoteSessionContextState {
  csrfToken: string;
  membershipId: string | null;
  organizationId: string | null;
  branchId: string | null;
}

let remoteSessionContext: RemoteSessionContextState = {
  csrfToken: '',
  membershipId: null,
  organizationId: null,
  branchId: null,
};

/**
 * Known financial/rate/weight keys serialized as lossless Decimal strings by Django.
 * Parsed at the HTTP client boundary so existing UI formatters & calculations receive numbers
 * while keeping wire payloads 100% Decimal-string accurate.
 */
const WIRE_DECIMAL_KEYS = new Set<string>([
  'creditLimitUsd',
  'usedCreditUsd',
  'hasLimitGram',
  'usedHasGram',
  'entryUsdRate',
  'entryHasGoldTry',
  'liveUsdSell',
  'liveEurSell',
  'liveHasGoldTrySell',
  'usdTryRate',
  'goldRateTryPerGram',
  'grossWeightGram',
  'centerStoneCarat',
  'sideStoneCarat',
  'fireRatePct',
  'allowedCaratMin',
  'allowedCaratMax',
  'headWeightGram',
  'bandWeightGram',
  'widthMm',
  'thicknessMm',
  'heightMm',
  'carat',
  'netMetalGram',
  'fineMetalGram',
  'fireIncludedFineMetalGram',
  'fineness',
  'listPriceTry',
  'finalPriceTry',
  'finalPriceLc',
  'effectiveDiscountPct',
  'unitListPriceTry',
  'unitFinalPriceTry',
  'subtotalListTry',
  'campaignDiscountTry',
  'transferDiscountTry',
  'insuredShippingTry',
  'vatIncludedTry',
  'grandTotalTry',
  'unitGrossGram',
  'unitNetMetalGram',
  'unitFireIncludedFineGram',
  'unitLaborAndStoneUsd',
  'unitWholesaleUsd',
  'unitWholesaleTry',
  'totalGrossGram',
  'totalHasGoldGram',
  'totalLaborAndStoneUsd',
  'totalWholesaleUsd',
  'totalWholesaleTry',
  'metalFcManual',
  'metalRateOverride',
  'laborFcPrice',
  'laborUnitFee',
  'laborRateOverride',
  'stoneFcPrice',
  'stoneRateOverride',
  'mountingFcPrice',
  'mountingRateOverride',
  'otherCostFcPrice',
  'otherCostRateOverride',
  'supplierFcPrice',
  'supplierRateOverride',
  'remainingCreditUsd',
  'remainingHasGram',
  'amountUsd',
  'hasGoldGram',
  'cachedTotalCostLc',
  'cachedB2bTry',
  'cachedB2cTry',
  'cachedB2cListTry',
  'fcPrice',
  'fcPriceManual',
  'rateOverride',
  'profitValue',
  'discountValue',
  'servisBedeliValue',
  'value',
  'baseCostTry',
  'settingLaborUsd',
  'mountLaborUsd',
  'stoneUsd',
  'pureGoldEquivalent',
  'netCostUsd',
  'minCarat',
  'maxCarat',
  'minLengthMm',
  'maxLengthMm',
  'minWidthMm',
  'maxWidthMm',
  'lengthMm',
  'widthMm',
  'depthMm',
  'netWeightGr',
  'laborCostValue',
]);

const NUMERIC_STRING_RE = /^-?\d+(?:\.\d+)?$/;

function normalizeWireDecimals<T>(value: T, parentKey?: string): T {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeWireDecimals(item)) as unknown as T;
  }
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (
        typeof v === 'string' &&
        NUMERIC_STRING_RE.test(v) &&
        (WIRE_DECIMAL_KEYS.has(k) || parentKey === 'fxBaseRates')
      ) {
        out[k] = Number(v);
      } else {
        out[k] = normalizeWireDecimals(v, k);
      }
    }
    return out as T;
  }
  return value;
}

function getRemoteApiBaseUrl(): string {
  // Strip accidental surrounding quotes from shell/.env inheritance
  // (e.g. process.env keeps `"http://..."` and Vite prefers that over loadEnv).
  return ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '')
    .trim()
    .replace(/^['"]+|['"]+$/g, '');
}

export function isRemoteBackendConfigured(): boolean {
  return getRemoteApiBaseUrl().length > 0;
}

/**
 * Demo mode is strictly isolated from real backend mode and NEVER enabled
 * implicitly in production builds (`import.meta.env.PROD`).
 */
export function isDemoModeEnabled(): boolean {
  if (isRemoteBackendConfigured()) {
    return false;
  }
  // Opt-in only — never silently fall back to mock catalog/rates in any environment.
  const explicitFlag = ((import.meta.env.VITE_ENABLE_DEMO_MODE as string | undefined) ?? '')
    .trim()
    .toLowerCase();
  return explicitFlag === 'true';
}

export function syncRemoteSessionContext(ctx: Partial<RemoteSessionContextState>) {
  remoteSessionContext = {
    ...remoteSessionContext,
    ...ctx,
  };
}

function readBrowserCookie(name: string): string {
  if (typeof document === 'undefined') return '';
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : '';
}

/**
 * Session, CSRF, Membership, Organization & Branch tenant-aware API client.
 * - Routes directly to VITE_API_BASE_URL in real backend mode with ZERO demo data imports.
 * - Backend Session API is the sole authority for user capabilities.
 * - Parses backend Decimal string wire payloads cleanly at the client boundary.
 */
export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<ApiEnvelope<T>> {
  const method = options.method ?? 'GET';
  const remoteBase = getRemoteApiBaseUrl();

  if (remoteBase) {
    const djangoCsrf = remoteSessionContext.csrfToken || readBrowserCookie('csrftoken');
    const isFormData =
      typeof FormData !== 'undefined' && options.body instanceof FormData;
    const remoteHeaders: Record<string, string> = {
      Accept: 'application/json',
      ...(options.body !== undefined && !isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...(method !== 'GET' && djangoCsrf ? { 'X-CSRF-Token': djangoCsrf } : {}),
      ...(remoteSessionContext.membershipId
        ? { 'X-Membership-Id': remoteSessionContext.membershipId }
        : {}),
      ...(remoteSessionContext.organizationId
        ? { 'X-Organization-Id': remoteSessionContext.organizationId }
        : {}),
      ...(remoteSessionContext.branchId
        ? { 'X-Branch-Id': remoteSessionContext.branchId }
        : {}),
      ...options.headers,
    };

    const res = await fetch(`${remoteBase.replace(/\/$/, '')}${path}`, {
      method,
      credentials: 'include',
      headers: remoteHeaders,
      body:
        options.body === undefined
          ? undefined
          : isFormData
            ? (options.body as FormData)
            : JSON.stringify(options.body),
      signal: options.signal,
    });
    if (!res.ok) {
      let errPayload: ApiErrorPayload = {
        code: 'HTTP_ERROR',
        message: `İstek başarısız oldu (${res.status})`,
      };
      try {
        errPayload = (await res.json()) as ApiErrorPayload;
      } catch {
        // non-JSON HTTP error fallback
      }
      throw new ApiClientError(res.status, errPayload);
    }
    const rawEnvelope = (await res.json()) as ApiEnvelope<T>;
    const envelope: ApiEnvelope<T> = {
      ...rawEnvelope,
      data: normalizeWireDecimals(rawEnvelope.data),
    };
    if (
      (path.startsWith('/api/v1/session') || path === '/api/v1/auth/register') &&
      envelope?.data &&
      typeof envelope.data === 'object'
    ) {
      const s = envelope.data as unknown as Partial<SessionUserDto>;
      if (s.csrfToken !== undefined || s.activeMembershipId !== undefined) {
        syncRemoteSessionContext({
          csrfToken: s.csrfToken ?? remoteSessionContext.csrfToken,
          membershipId: s.activeMembershipId ? String(s.activeMembershipId) : null,
          organizationId: s.activeOrganizationId ?? null,
          branchId: s.activeBranchId ?? null,
        });
      }
    }
    return envelope;
  }

  if (!isDemoModeEnabled()) {
    throw new ApiClientError(503, {
      code: 'BACKEND_URL_NOT_CONFIGURED',
      message:
        'Production ortamında VITE_API_BASE_URL yapılandırılmadan yerel demo moduna geçilemez.',
    });
  }

  const { demoApiFetch } = await import('./demoMockHandler');
  return demoApiFetch<T>(path, options);
}

/** Authenticated binary download (PDF etc.) using the same session cookies as apiFetch. */
export async function apiDownloadBlob(path: string, filename: string): Promise<void> {
  const remoteBase = getRemoteApiBaseUrl();
  if (!remoteBase) {
    throw new ApiClientError(503, {
      code: 'BACKEND_URL_NOT_CONFIGURED',
      message: 'Dosya indirmek için API adresi gerekli.',
    });
  }
  const djangoCsrf = remoteSessionContext.csrfToken || readBrowserCookie('csrftoken');
  const headers: Record<string, string> = {
    Accept: 'application/pdf,application/octet-stream',
    ...(djangoCsrf ? { 'X-CSRF-Token': djangoCsrf } : {}),
    ...(remoteSessionContext.membershipId
      ? { 'X-Membership-Id': remoteSessionContext.membershipId }
      : {}),
    ...(remoteSessionContext.organizationId
      ? { 'X-Organization-Id': remoteSessionContext.organizationId }
      : {}),
    ...(remoteSessionContext.branchId
      ? { 'X-Branch-Id': remoteSessionContext.branchId }
      : {}),
  };
  const res = await fetch(`${remoteBase.replace(/\/$/, '')}${path}`, {
    method: 'GET',
    credentials: 'include',
    headers,
  });
  if (!res.ok) {
    throw new ApiClientError(res.status, {
      code: 'DOWNLOAD_FAILED',
      message: `İndirme başarısız (${res.status})`,
    });
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

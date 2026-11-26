function trimUrl(value: string | undefined, fallback: string): string {
  const trimmed = value?.trim().replace(/^['"]+|['"]+$/g, '') ?? '';
  return trimmed.length > 0 ? trimmed : fallback;
}

export function getStorefrontUrl(): string {
  return trimUrl(import.meta.env.VITE_STOREFRONT_URL as string | undefined, 'http://localhost:3000/');
}

export function getB2bLoginUrl(): string {
  return trimUrl(
    import.meta.env.VITE_B2B_URL as string | undefined,
    'http://localhost:3001/b2b/giris'
  );
}

export function getB2bPanelUrl(): string {
  const login = getB2bLoginUrl();
  return login.replace(/\/giris\/?$/, '/panel');
}

export function getOpsLoginUrl(): string {
  return trimUrl(import.meta.env.VITE_OPS_URL as string | undefined, 'http://localhost:3002/ops/giris');
}

export function getOpsPanelUrl(): string {
  const login = getOpsLoginUrl();
  return login.replace(/\/giris\/?$/, '/panel');
}
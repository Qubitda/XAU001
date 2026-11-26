import type { B2cCartItem, B2cCartSnapshot } from '../types';

const STORAGE_KEY = 'tara-guest-b2c-cart';
const LOCK_MS = 15 * 60 * 1000;

function emptySnapshot(snapshotId = 'guest'): B2cCartSnapshot {
  return {
    items: [],
    priceLockedUntil: new Date(Date.now() + LOCK_MS).toISOString(),
    snapshotId,
  };
}

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function readGuestB2cCart(): B2cCartSnapshot {
  if (!canUseStorage()) return emptySnapshot();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptySnapshot();
    const parsed = JSON.parse(raw) as B2cCartSnapshot;
    if (!parsed || !Array.isArray(parsed.items)) return emptySnapshot();
    return {
      items: parsed.items,
      priceLockedUntil:
        parsed.priceLockedUntil || new Date(Date.now() + LOCK_MS).toISOString(),
      snapshotId: parsed.snapshotId || 'guest',
    };
  } catch {
    return emptySnapshot();
  }
}

export function writeGuestB2cCart(snapshot: B2cCartSnapshot): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // ignore quota / private mode
  }
}

export function clearGuestB2cCart(): B2cCartSnapshot {
  const next = emptySnapshot();
  writeGuestB2cCart(next);
  return next;
}

/** Read guest items and clear local storage (for post-login sync). */
export function takeGuestB2cCartItems(): B2cCartItem[] {
  const snap = readGuestB2cCart();
  clearGuestB2cCart();
  return snap.items;
}

export function addGuestB2cCartItem(
  incoming: Omit<B2cCartItem, 'id' | 'addedAt'>
): B2cCartSnapshot {
  const current = readGuestB2cCart();
  const normEngraving = (incoming.engravingText ?? '').trim();
  const existingIdx = current.items.findIndex(
    (i) =>
      i.sku === incoming.sku &&
      i.size === incoming.size &&
      i.engravingText.trim().toLowerCase() === normEngraving.toLowerCase() &&
      i.giftWrap === Boolean(incoming.giftWrap)
  );

  const nextItems =
    existingIdx >= 0
      ? current.items.map((item, idx) =>
          idx === existingIdx
            ? {
                ...item,
                qty: Math.min(10, item.qty + Math.max(1, incoming.qty || 1)),
              }
            : item
        )
      : [
          ...current.items,
          {
            ...incoming,
            engravingText: normEngraving,
            giftWrap: Boolean(incoming.giftWrap),
            giftNote: (incoming.giftNote ?? '').trim(),
            id: `guest-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            addedAt: new Date().toISOString(),
          },
        ];

  const next: B2cCartSnapshot = {
    items: nextItems,
    priceLockedUntil: new Date(Date.now() + LOCK_MS).toISOString(),
    snapshotId: incoming.snapshotId || current.snapshotId || 'guest',
  };
  writeGuestB2cCart(next);
  return next;
}

export function updateGuestB2cCartItem(
  id: string,
  patch: Partial<B2cCartItem>
): B2cCartSnapshot {
  const current = readGuestB2cCart();
  const next: B2cCartSnapshot = {
    ...current,
    items: current.items.map((item) =>
      item.id === id
        ? {
            ...item,
            ...patch,
            qty:
              patch.qty !== undefined
                ? Math.max(1, Math.min(10, patch.qty))
                : item.qty,
          }
        : item
    ),
  };
  writeGuestB2cCart(next);
  return next;
}

export function removeGuestB2cCartItem(id: string): B2cCartSnapshot {
  const current = readGuestB2cCart();
  const next: B2cCartSnapshot = {
    ...current,
    items: current.items.filter((item) => item.id !== id),
  };
  writeGuestB2cCart(next);
  return next;
}

export function refreshGuestB2cCartLock(): B2cCartSnapshot {
  const current = readGuestB2cCart();
  const next: B2cCartSnapshot = {
    ...current,
    priceLockedUntil: new Date(Date.now() + LOCK_MS).toISOString(),
  };
  writeGuestB2cCart(next);
  return next;
}

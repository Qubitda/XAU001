import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '../../../providers/AuthProvider';
import { commerceService } from '../services/commerceService';
import {
  addGuestB2cCartItem,
  clearGuestB2cCart,
  readGuestB2cCart,
  refreshGuestB2cCartLock,
  removeGuestB2cCartItem,
  takeGuestB2cCartItems,
  updateGuestB2cCartItem,
} from '../services/guestB2cCart';
import { opsKeys } from '../../ops/hooks/useOpsQueries';
import type {
  B2bOrderLine,
  B2bOrderRecord,
  B2cCartItem,
  B2cOrderRecord,
} from '../types';

export const commerceKeys = {
  all: ['commerce'] as const,
  b2cCart: () => [...commerceKeys.all, 'b2c-cart'] as const,
  b2cOrders: () => [...commerceKeys.all, 'b2c-orders'] as const,
  b2bDraft: () => [...commerceKeys.all, 'b2b-draft'] as const,
  b2bOrders: () => [...commerceKeys.all, 'b2b-orders'] as const,
  favorites: () => [...commerceKeys.all, 'favorites'] as const,
};

const GUEST_FAVORITES_KEY = 'taragold_guest_favorites_v1';

function readGuestFavorites(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(GUEST_FAVORITES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function toggleGuestFavorite(parentSku: string): string[] {
  const current = readGuestFavorites();
  const exists = current.includes(parentSku);
  const next = exists ? current.filter((sku) => sku !== parentSku) : [...current, parentSku];
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(GUEST_FAVORITES_KEY, JSON.stringify(next));
    } catch {
      // ignore storage quota errors
    }
  }
  return next;
}

export function useFavoritesQuery() {
  const { authenticated } = useAuth();
  return useQuery({
    queryKey: [...commerceKeys.favorites(), authenticated ? 'auth' : 'guest'],
    queryFn: () =>
      authenticated ? commerceService.listFavorites() : Promise.resolve(readGuestFavorites()),
  });
}

export function useToggleFavoriteMutation() {
  const qc = useQueryClient();
  const { authenticated } = useAuth();
  return useMutation({
    mutationFn: (parentSku: string) =>
      authenticated
        ? commerceService.toggleFavorite(parentSku)
        : Promise.resolve(toggleGuestFavorite(parentSku)),
    onSuccess: (next) => {
      qc.setQueryData(
        [...commerceKeys.favorites(), authenticated ? 'auth' : 'guest'],
        next
      );
      qc.setQueryData(commerceKeys.favorites(), next);
    },
    onError: () => {
      toast.error('Favori güncellenemedi. Lütfen tekrar deneyin.');
    },
  });
}

export function useB2cCartQuery() {
  const { authenticated } = useAuth();
  return useQuery({
    queryKey: [...commerceKeys.b2cCart(), authenticated ? 'auth' : 'guest'],
    queryFn: () =>
      authenticated ? commerceService.getB2cCart() : Promise.resolve(readGuestB2cCart()),
  });
}

export function useB2cOrdersQuery() {
  const { authenticated } = useAuth();
  return useQuery({
    queryKey: commerceKeys.b2cOrders(),
    queryFn: commerceService.listB2cOrders,
    enabled: authenticated,
  });
}

function setB2cCartCache(
  qc: ReturnType<typeof useQueryClient>,
  authenticated: boolean,
  snap: Awaited<ReturnType<typeof commerceService.getB2cCart>>
) {
  qc.setQueryData([...commerceKeys.b2cCart(), authenticated ? 'auth' : 'guest'], snap);
  qc.setQueryData(commerceKeys.b2cCart(), snap);
}

export function useAddToB2cCartMutation() {
  const qc = useQueryClient();
  const { authenticated } = useAuth();
  return useMutation({
    mutationFn: (item: Omit<B2cCartItem, 'id' | 'addedAt'>) =>
      authenticated
        ? commerceService.addB2cCartItem(item)
        : Promise.resolve(addGuestB2cCartItem(item)),
    onSuccess: (snap) => {
      setB2cCartCache(qc, authenticated, snap);
    },
    onError: () => {
      toast.error('Sepete eklenemedi. Lütfen tekrar deneyin.');
    },
  });
}

export function useUpdateB2cCartItemMutation() {
  const qc = useQueryClient();
  const { authenticated } = useAuth();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<B2cCartItem> }) =>
      authenticated
        ? commerceService.updateB2cCartItem(id, patch)
        : Promise.resolve(updateGuestB2cCartItem(id, patch)),
    onSuccess: (snap) => {
      setB2cCartCache(qc, authenticated, snap);
    },
  });
}

export function useRemoveB2cCartItemMutation() {
  const qc = useQueryClient();
  const { authenticated } = useAuth();
  return useMutation({
    mutationFn: (id: string) =>
      authenticated
        ? commerceService.removeB2cCartItem(id)
        : Promise.resolve(removeGuestB2cCartItem(id)),
    onSuccess: (snap) => {
      setB2cCartCache(qc, authenticated, snap);
    },
  });
}

export function useClearB2cCartMutation() {
  const qc = useQueryClient();
  const { authenticated } = useAuth();
  return useMutation({
    mutationFn: () =>
      authenticated
        ? commerceService.clearB2cCart()
        : Promise.resolve(clearGuestB2cCart()),
    onSuccess: (snap) => {
      setB2cCartCache(qc, authenticated, snap);
    },
  });
}

export function useRefreshB2cPriceLockMutation() {
  const qc = useQueryClient();
  const { authenticated } = useAuth();
  return useMutation({
    mutationFn: () =>
      authenticated
        ? commerceService.refreshB2cPriceLock()
        : Promise.resolve(refreshGuestB2cCartLock()),
    onSuccess: (snap) => {
      setB2cCartCache(qc, authenticated, snap);
    },
  });
}

export function useSubmitB2cOrderMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (
      payload: Omit<B2cOrderRecord, 'orderNo' | 'createdAt' | 'items' | 'status'>
    ) => commerceService.submitB2cOrder(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: commerceKeys.b2cCart() });
      void qc.invalidateQueries({ queryKey: commerceKeys.b2cOrders() });
      void qc.invalidateQueries({ queryKey: ['catalog'] });
    },
  });
}

export function useInitializeIyzicoCheckoutMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (
      payload: Omit<B2cOrderRecord, 'orderNo' | 'createdAt' | 'items' | 'status'>
    ) => commerceService.initializeIyzicoCheckout(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: commerceKeys.b2cCart() });
      void qc.invalidateQueries({ queryKey: commerceKeys.b2cOrders() });
      void qc.invalidateQueries({ queryKey: ['catalog'] });
    },
  });
}

export function useB2bDraftQuery() {
  const { authenticated, hasCapability, activeOrganization } = useAuth();
  return useQuery({
    queryKey: [...commerceKeys.b2bDraft(), activeOrganization?.id ?? 'none'],
    queryFn: commerceService.getB2bDraft,
    enabled: authenticated && hasCapability('b2b:order') && Boolean(activeOrganization),
  });
}

export function useB2bOrdersQuery() {
  const { authenticated, hasCapability, activeOrganization } = useAuth();
  return useQuery({
    queryKey: [...commerceKeys.b2bOrders(), activeOrganization?.id ?? 'none'],
    queryFn: commerceService.listB2bOrders,
    enabled: authenticated && hasCapability('b2b:order') && Boolean(activeOrganization),
  });
}

export function useAddToB2bDraftMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (
      lines:
        | Omit<B2bOrderLine, 'id' | 'addedAt'>
        | Array<Omit<B2bOrderLine, 'id' | 'addedAt'>>
    ) => commerceService.addB2bDraftLines(lines),
    onSuccess: (snap) => {
      qc.setQueriesData({ queryKey: commerceKeys.b2bDraft() }, snap);
      const pieces = snap.lines.reduce((s, l) => s + l.qty, 0);
      toast.success('Sipariş fişine eklendi', {
        description: `Fişte toplam ${pieces} adet · Taslağı düzenlemek için sipariş fişine gidebilirsiniz.`,
      });
    },
  });
}

export function useUpdateB2bDraftLineMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<B2bOrderLine> }) =>
      commerceService.updateB2bDraftLine(id, patch),
    onSuccess: (snap) => {
      qc.setQueriesData({ queryKey: commerceKeys.b2bDraft() }, snap);
    },
  });
}

export function useRemoveB2bDraftLineMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => commerceService.removeB2bDraftLine(id),
    onSuccess: (snap) => {
      qc.setQueriesData({ queryKey: commerceKeys.b2bDraft() }, snap);
    },
  });
}

export function useClearB2bDraftMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => commerceService.clearB2bDraft(),
    onSuccess: (snap) => {
      qc.setQueriesData({ queryKey: commerceKeys.b2bDraft() }, snap);
    },
  });
}

export function useSubmitB2bOrderMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (
      payload: Omit<B2bOrderRecord, 'orderNo' | 'createdAt' | 'lines' | 'status'>
    ) => commerceService.submitB2bOrder(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: commerceKeys.b2bDraft() });
      void qc.invalidateQueries({ queryKey: commerceKeys.b2bOrders() });
      void qc.invalidateQueries({ queryKey: ['portal', 'session'] });
      void qc.invalidateQueries({ queryKey: ['catalog'] });
    },
  });
}

export function useUpdateB2cOrderStatusMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orderNo,
      status,
    }: {
      orderNo: string;
      status: B2cOrderRecord['status'];
    }) => commerceService.updateB2cOrderStatus(orderNo, status),
    onSuccess: (orders) => {
      qc.setQueryData(commerceKeys.b2cOrders(), orders);
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'b2c-orders'] });
    },
  });
}

export function useUpdateB2bOrderStatusMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      orderNo,
      status,
    }: {
      orderNo: string;
      status: B2bOrderRecord['status'];
    }) => commerceService.updateB2bOrderStatus(orderNo, status),
    onSuccess: (orders) => {
      qc.setQueriesData({ queryKey: commerceKeys.b2bOrders() }, orders);
      void qc.invalidateQueries({ queryKey: [...opsKeys.all, 'b2b-orders'] });
    },
  });
}

export function useReorderB2bOrderMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (orderNo: string) => commerceService.reorderB2bOrder(orderNo),
    onSuccess: (snap) => {
      qc.setQueriesData({ queryKey: commerceKeys.b2bDraft() }, snap);
    },
  });
}

interface CommerceUIContextValue {
  b2cCartOpen: boolean;
  setB2cCartOpen: (open: boolean) => void;
  b2bOrderOpen: boolean;
  setB2bOrderOpen: (open: boolean) => void;
}

const CommerceUIContext = createContext<CommerceUIContextValue | null>(null);

export function CommerceProvider({ children }: { children: ReactNode }) {
  const [b2cCartOpen, setB2cCartOpen] = useState(false);
  const [b2bOrderOpen, setB2bOrderOpen] = useState(false);
  const { authenticated } = useAuth();
  const qc = useQueryClient();
  const wasAuthenticated = useRef(authenticated);

  // Misafir sepetini giriş sonrası sunucu sepetine aktar
  useEffect(() => {
    const justLoggedIn = !wasAuthenticated.current && authenticated;
    wasAuthenticated.current = authenticated;
    if (!justLoggedIn) return;

    const guestItems = takeGuestB2cCartItems();
    if (guestItems.length === 0) {
      void qc.invalidateQueries({ queryKey: commerceKeys.b2cCart() });
      return;
    }

    void (async () => {
      try {
        for (const item of guestItems) {
          const { id: _id, addedAt: _addedAt, ...payload } = item;
          await commerceService.addB2cCartItem(payload);
        }
      } catch {
        toast.error('Misafir sepeti aktarılamadı. Ürünleri tekrar ekleyebilirsiniz.');
      } finally {
        void qc.invalidateQueries({ queryKey: commerceKeys.b2cCart() });
      }
    })();
  }, [authenticated, qc]);

  return (
    <CommerceUIContext.Provider
      value={{
        b2cCartOpen,
        setB2cCartOpen,
        b2bOrderOpen,
        setB2bOrderOpen,
      }}
    >
      {children}
    </CommerceUIContext.Provider>
  );
}

export function useCommerceUI() {
  const ctx = useContext(CommerceUIContext);
  if (!ctx) {
    throw new Error('useCommerceUI must be used inside CommerceProvider');
  }
  return ctx;
}

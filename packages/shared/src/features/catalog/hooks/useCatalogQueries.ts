import {
  createContext,
  createElement,
  ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createBlankProduct, createEmptyRates } from '../../../data/productDefaults';
import { isRemoteBackendConfigured } from '../../../lib/api/client';
import { useAuth } from '../../../providers/AuthProvider';
import { AudienceRole, LiveRates, ProductState } from '../../../types/jewelry';
import { computeJewelryMetrics } from '../../../utils/pricingEngine';
import { catalogService } from '../services/catalogService';

export const catalogQueryKeys = {
  all: ['catalog'] as const,
  products: (role?: AudienceRole, organizationId?: string | null) =>
    [...catalogQueryKeys.all, 'products', role ?? 'b2c', organizationId ?? 'public'] as const,
  rates: () => [...catalogQueryKeys.all, 'rates'] as const,
};

export function useCatalogQuery() {
  const { role, activeOrganization, authenticated } = useAuth();
  const isRemote = isRemoteBackendConfigured();
  // Anonymous visitors on remote backend always fetch public storefront products
  const effectiveRole: AudienceRole = isRemote && !authenticated ? 'b2c' : role;

  return useQuery({
    queryKey: catalogQueryKeys.products(effectiveRole, activeOrganization?.id ?? null),
    queryFn: () => catalogService.listProducts(effectiveRole),
    retry: 1,
  });
}

export function useLiveRatesQuery() {
  return useQuery({
    queryKey: catalogQueryKeys.rates(),
    queryFn: () => catalogService.getLiveRates(),
    retry: 1,
  });
}

export function useBuyerQuoteMutation() {
  return useMutation({
    mutationFn: (params: { parentSku: string; channel: 'B2B' | 'B2C'; size?: number }) =>
      catalogService.requestQuote(params),
  });
}

export function useCreateProductMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductState) => catalogService.createProduct(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: catalogQueryKeys.all });
    },
  });
}

export function useUpdateProductMutation() {
  const queryClient = useQueryClient();
  const { role, activeOrganization } = useAuth();
  const currentKey = catalogQueryKeys.products(role, activeOrganization?.id ?? null);

  return useMutation({
    mutationFn: ({ parentSku, patch }: { parentSku: string; patch: Partial<ProductState> }) =>
      catalogService.updateProduct(parentSku, patch),
    onSuccess: (updated) => {
      queryClient.setQueryData<ProductState[]>(currentKey, (items = []) =>
        items.map((item) => (item.parentSku === updated.parentSku ? updated : item))
      );
      void queryClient.invalidateQueries({ queryKey: catalogQueryKeys.all });
    },
  });
}

export function useDeleteProductMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (parentSku: string) => catalogService.deleteProduct(parentSku),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: catalogQueryKeys.all });
    },
  });
}

export function usePublishProductMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (parentSku: string) => catalogService.publishProduct(parentSku),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: catalogQueryKeys.all });
    },
  });
}

export function useUnpublishProductMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (parentSku: string) => catalogService.unpublishProduct(parentSku),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: catalogQueryKeys.all });
    },
  });
}

export function useUpdateRatesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<LiveRates>) => catalogService.updateLiveRates(patch),
    onMutate: async (patch) => {
      await queryClient.cancelQueries({ queryKey: catalogQueryKeys.rates() });
      const prev = queryClient.getQueryData<LiveRates>(catalogQueryKeys.rates());
      queryClient.setQueryData<LiveRates>(catalogQueryKeys.rates(), (current) => {
        const base = current ?? createEmptyRates();
        return {
          ...base,
          ...patch,
          fxBaseRates: patch.fxBaseRates
            ? { ...base.fxBaseRates, ...patch.fxBaseRates }
            : base.fxBaseRates,
        };
      });
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(catalogQueryKeys.rates(), ctx.prev);
      }
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(catalogQueryKeys.rates(), updated);
      // Re-fetch server-calculated product prices after live rates change
      void queryClient.invalidateQueries({ queryKey: catalogQueryKeys.all });
    },
  });
}

interface PortalSelectionContextValue {
  selectedParentSku: string;
  setSelectedParentSku: (sku: string) => void;
}

const PortalSelectionContext = createContext<PortalSelectionContextValue | null>(null);

export function PortalSelectionProvider({ children }: { children: ReactNode }) {
  const [selectedParentSku, setSelectedParentSku] = useState<string>('');
  const value = useMemo(
    () => ({ selectedParentSku, setSelectedParentSku }),
    [selectedParentSku]
  );
  return createElement(PortalSelectionContext.Provider, { value }, children);
}

export function usePortalSelection() {
  const ctx = useContext(PortalSelectionContext);
  if (!ctx) {
    throw new Error('usePortalSelection must be used inside <PortalSelectionProvider>');
  }
  return ctx;
}

export function useActiveProductMetrics(overrideParentSku?: string) {
  const catalogQuery = useCatalogQuery();
  const ratesQuery = useLiveRatesQuery();
  const products = catalogQuery.data ?? [];
  const rates = ratesQuery.data ?? createEmptyRates();
  const { selectedParentSku, setSelectedParentSku } = usePortalSelection();

  const targetSku = overrideParentSku ?? selectedParentSku;
  const product = useMemo(() => {
    if (!products.length) return null;
    return products.find((p) => p.parentSku === targetSku) ?? products[0] ?? null;
  }, [products, targetSku]);

  // Keep selection in sync when catalog loads / selected SKU missing
  useEffect(() => {
    if (product && !overrideParentSku && selectedParentSku !== product.parentSku) {
      setSelectedParentSku(product.parentSku);
    }
  }, [product, overrideParentSku, selectedParentSku, setSelectedParentSku]);

  const computed = useMemo(() => {
    if (!product || !ratesQuery.data) return null;
    return computeJewelryMetrics(product, rates);
  }, [product, rates, ratesQuery.data]);

  const isLoading = catalogQuery.isLoading || ratesQuery.isLoading;
  const isError = catalogQuery.isError || ratesQuery.isError;
  const isEmpty = !isLoading && !isError && products.length === 0;

  const refetch = () => {
    void catalogQuery.refetch();
    void ratesQuery.refetch();
  };

  // Compatibility: callers that always expect a ProductState get a blank shell only when empty.
  const productOrBlank = product ?? createBlankProduct({ parentSku: '', title: '' });
  const computedOrBlank = computed ?? computeJewelryMetrics(productOrBlank, rates);

  return {
    products,
    product: productOrBlank,
    activeProduct: product,
    rates,
    computed: computedOrBlank,
    isLoading,
    isError,
    isEmpty,
    hasLiveRates: Boolean(ratesQuery.data),
    refetch,
    catalogQuery,
    ratesQuery,
  };
}

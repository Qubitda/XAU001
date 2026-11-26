import {
  useActiveProductMetrics,
  useUpdateProductMutation,
  useUpdateRatesMutation,
} from '../../catalog/hooks/useCatalogQueries';

export function usePricingFeature() {
  const active = useActiveProductMetrics();
  const updateProduct = useUpdateProductMutation();
  const updateRates = useUpdateRatesMutation();

  return {
    ...active,
    updateProduct,
    updateRates,
  };
}

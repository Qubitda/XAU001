import { catalogService } from '../../catalog/services/catalogService';
import type { LiveRates, ProductState } from '../../../types/jewelry';

export const pricingService = {
  updateProductLedger(parentSku: string, patch: Partial<ProductState>) {
    return catalogService.updateProduct(parentSku, patch);
  },
  updateLiveRates(patch: Partial<LiveRates>) {
    return catalogService.updateLiveRates(patch);
  },
};

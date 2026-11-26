import type { ProductState } from '../../../types/jewelry';

export interface DyoChannelPrice {
  finalPriceTry: number;
  listPriceTry: number;
  profitLc?: number;
  discountLc?: number;
  serviceFeeLc?: number;
}

/** Buyer-facing DYO pricing (blind-pool). Cost internals are OPS-only. */
export interface DyoPricingDto {
  snapshotCode: string;
  channels: Record<string, DyoChannelPrice>;
  /** @deprecated OPS-only — absent on buyer APIs */
  pureGoldEquivalent?: number;
  mountLaborUsd?: number;
  stoneUsd?: number;
  settingLaborUsd?: number;
  baseCostTry?: number;
  breakdownTry?: {
    metal: number;
    labor: number;
    stone: number;
    setting: number;
  };
}

export interface DyoCompatibleStoneItem extends ProductState {
  looseStoneDetail?: ProductState['looseStoneDetail'];
  compatible?: boolean;
}

export interface CompatibleStonesResponse {
  mountingSku: string;
  filters: {
    compatibleShapes: string[];
    minCarat: number | null;
    maxCarat: number | null;
  };
  items: DyoCompatibleStoneItem[];
  count: number;
}

export interface DyoValidateResponse {
  compatible: boolean;
  mountingSku: string;
  stoneSku: string;
  pricing: DyoPricingDto;
}

export interface DyoBundleDto {
  id: string;
  status: string;
  audience: string;
  mountingSku: string;
  stoneSku: string;
  settingLaborUsd?: number;
  expiresAt: string | null;
  pricing?: DyoPricingDto | null;
}

export type DyoAudience = 'b2c' | 'b2b';

export interface CreateDyoBundleInput {
  mountingSku: string;
  stoneSku: string;
  addToCart?: boolean;
  audience?: DyoAudience;
}

export interface CompatibleStonesQuery {
  mountingSku: string;
  color?: string;
  clarity?: string;
  limit?: number;
}

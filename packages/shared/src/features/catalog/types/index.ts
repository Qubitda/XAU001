export type {
  AudienceRole,
  ComputedJewelryMetrics,
  JewelryVisualType,
  LiveRates,
  MetalColor,
  PricingMode,
  ProductState,
  PurityCode,
  StoneMeasureUnit,
  StoneType,
} from '../../../types/jewelry';

export interface ProductQuickFormValues {
  parentSku: string;
  title: string;
  category: string;
  subCategory: string;
  collection: string;
  purityCode: '8K' | '14K' | '18K' | '22K' | '925';
  metalColor: 'Beyaz' | 'Sarı' | 'Rose';
  stoneType:
    | 'Pırlanta'
    | 'Safir'
    | 'Yakut'
    | 'Zümrüt'
    | 'Doğal Zirkon'
    | 'Turkuaz'
    | 'Kehribar'
    | 'Diğer taşlar'
    | 'Zirkon'
    | 'Taşsız';
  grossWeightGram: number;
  centerStoneCarat: number;
  sideStoneCarat: number;
  fireRatePct: number;
  stockStatus: 'Stokta' | 'Tükendi' | 'Siparişe Özel';
  stockQty: number;
  ownershipType: 'Öz Mal' | 'Konsinye (Emanet)';
  visualType:
    | 'solitaire_ring'
    | 'baguette_ring'
    | 'pendant_necklace'
    | 'tennis_bracelet'
    | 'emerald_earring'
    | 'eternity_ring';
  description: string;
}

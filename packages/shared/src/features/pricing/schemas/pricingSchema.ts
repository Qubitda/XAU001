import { z } from 'zod';

export const pricingLedgerSchema = z.object({
  fireRatePct: z.number().min(0).max(30),
  grossWeightGram: z.number().min(0),
  laborFcPrice: z.number().min(0),
  stoneFcPrice: z.number().min(0),
  mountingFcPrice: z.number().min(0),
  otherCostFcPrice: z.number().min(0),
  supplierFcPrice: z.number().min(0),
});

export type PricingLedgerSchemaValues = z.infer<typeof pricingLedgerSchema>;

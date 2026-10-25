import type { PaymentMethod } from "../api/payments";

export type FxRoundingPolicy = "round_up" | "round_down" | "nearest_ten" | "exact" | "keep_remainder";

export type FxTenderSettlementSuggestion = {
  exactTenderAmount: number;
  tenderAmount: number;
  suggestedTenderAmount: number;
  appliedAmount: number;
  remainingDue: number;
  creditAmount: number;
  isPartial: boolean;
};

export function roundFxAmount(amount: number, policy?: FxRoundingPolicy): number;
export function resolveFxRoundingPolicy(
  paymentMethod: PaymentMethod,
  hotelPolicy?: FxRoundingPolicy
): FxRoundingPolicy;
export function suggestFxTenderSettlement(
  balance: number,
  reservationUnitsPerTenderUnit: number,
  policy?: FxRoundingPolicy
): FxTenderSettlementSuggestion | null;

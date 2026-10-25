import { apiFetch, type SessionLike } from "./client";
import type { PaymentMethod } from "./payments";

export type PaymentSurchargeType = "fixed" | "percentage";

export type PaymentSurcharge = {
  id: number;
  hotel_id: number;
  payment_method: string;
  surcharge_type: PaymentSurchargeType;
  amount: string | number;
  currency_code: string;
  is_active: boolean;
  created_at: string;
};

export type PaymentSurchargeCreatePayload = {
  payment_method: string;
  surcharge_type: PaymentSurchargeType;
  amount: number;
  currency_code?: string;
};

export type PaymentSurchargeQuoteRequest = {
  reservation_id: number;
  payment_method: PaymentMethod;
  currency_code: string;
  /** Tender-currency amount before surcharge; omit to quote the exact balance tender. */
  base_amount?: number;
};

export type PaymentSurchargeQuote = {
  reservation_id: number;
  reservation_currency_code: string;
  reservation_balance: number | string;
  applied_amount: number | string;
  remaining_balance: number | string;
  payment_method: PaymentMethod;
  currency_code: string;
  base_amount: number | string;
  surcharge_type: PaymentSurchargeType | null;
  surcharge_value: number | string | null;
  surcharge_currency_code: string;
  surcharge_amount: number | string;
  final_amount: number | string;
  surcharge_fx_rate: number | string | null;
  surcharge_fx_quote_details: Record<string, unknown> | null;
  fx_rate_snapshot: number | string | null;
  fx_quote_details: Record<string, unknown> | null;
  cash_tender_rounding_policy: string | null;
  cash_tender_suggestion: number | string | null;
  cash_tender_suggestion_difference: number | string;
  payment_quote_token: string;
};

export const listPaymentSurcharges = (session?: SessionLike) =>
  apiFetch<PaymentSurcharge[]>("/api/payment-surcharges", { session });

export const createPaymentSurcharge = (payload: PaymentSurchargeCreatePayload, session?: SessionLike) =>
  apiFetch<PaymentSurcharge>("/api/payment-surcharges", { method: "POST", data: payload, session });

export const deactivatePaymentSurcharge = (id: number, session?: SessionLike) =>
  apiFetch<PaymentSurcharge>(`/api/payment-surcharges/${id}`, { method: "DELETE", session });

export const quotePaymentSurcharge = (
  payload: PaymentSurchargeQuoteRequest,
  session?: SessionLike
) => apiFetch<PaymentSurchargeQuote>("/api/payment-surcharges/quote", {
  method: "POST",
  data: payload,
  session
});

/** Compute the gross amount (base + surcharge) for a base amount and an active surcharge. */
export const grossWithSurcharge = (base: number, surcharge?: PaymentSurcharge | null): number => {
  if (!surcharge || !surcharge.is_active || base <= 0) return base;
  const amount = Number(surcharge.amount);
  const fee =
    surcharge.surcharge_type === "fixed"
      ? amount
      : base * (amount / 100);
  return Math.round((base + fee) * 100) / 100;
};

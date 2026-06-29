import { apiFetch, type SessionLike } from "./client";

export type PaymentSurchargeType = "fixed" | "percentage";

export type PaymentSurcharge = {
  id: number;
  hotel_id: number;
  payment_method: string;
  surcharge_type: PaymentSurchargeType;
  amount: number;
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

export const listPaymentSurcharges = (session?: SessionLike) =>
  apiFetch<PaymentSurcharge[]>("/api/payment-surcharges", { session });

export const createPaymentSurcharge = (payload: PaymentSurchargeCreatePayload, session?: SessionLike) =>
  apiFetch<PaymentSurcharge>("/api/payment-surcharges", { method: "POST", data: payload, session });

export const deactivatePaymentSurcharge = (id: number, session?: SessionLike) =>
  apiFetch<PaymentSurcharge>(`/api/payment-surcharges/${id}`, { method: "DELETE", session });

/** Compute the gross amount (base + surcharge) for a base amount and an active surcharge. */
export const grossWithSurcharge = (base: number, surcharge?: PaymentSurcharge | null): number => {
  if (!surcharge || !surcharge.is_active || base <= 0) return base;
  const fee =
    surcharge.surcharge_type === "fixed"
      ? surcharge.amount
      : base * (surcharge.amount / 100);
  return Math.round((base + fee) * 100) / 100;
};

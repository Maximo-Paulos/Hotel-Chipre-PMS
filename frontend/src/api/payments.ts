import { apiFetch, type SessionLike } from "./client";

export type PaymentMethod = "cash" | "mercado_pago" | "paypal" | "credit_card" | "debit_card" | "bank_transfer";

export type TransactionType = "deposit" | "full_payment" | "partial_payment" | "balance_payment" | "refund";

export type PaymentRequest = {
  reservation_id: number;
  amount: number;
  payment_method: PaymentMethod;
  transaction_type: TransactionType;
  currency?: string;
  description?: string;
};

export type PaymentSummary = {
  reservation_id: number;
  confirmation_code: string;
  status: string;
  currency_code: string;
  total_amount: number;
  deposit_required: number;
  amount_paid: number;
  balance_due: number;
  // total_amount/balance_due only reflect the reservation's base price; they
  // ignore consumption charges (BillingAdjustment). operational_* includes
  // them and is the amount actually owed -- use it for collecting payment.
  operational_total_amount?: number;
  operational_balance_due?: number;
  billing_adjustment_total?: number;
  completed_payments: number;
  transactions: Array<{
    id: number;
    amount: number;
    gross_amount?: number;
    fee_amount?: number;
    currency: string;
    method: string;
    type: string;
    status: string;
    created_at: string;
  }>;
};

export const getPaymentSummary = (reservationId: number, session?: SessionLike) =>
  apiFetch<PaymentSummary>(`/api/payments/summary/${reservationId}`, { session });

export const newPaymentIdempotencyKey = (reservationId: number) => {
  const requestId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `ui-payment-${reservationId}-${requestId}`;
};

export const makePayment = (
  payload: PaymentRequest,
  session?: SessionLike,
  idempotencyKey: string = newPaymentIdempotencyKey(payload.reservation_id)
) =>
  apiFetch(`/api/payments`, {
    method: "POST",
    data: payload,
    session,
    headers: {
      // The caller reuses this key when retrying the same operator intent;
      // a new intent passes a new key.
      "Idempotency-Key": idempotencyKey
    }
  });

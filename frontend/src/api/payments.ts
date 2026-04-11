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
  completed_payments: number;
  transactions: Array<{
    id: number;
    amount: number;
    currency: string;
    method: string;
    type: string;
    status: string;
    created_at: string;
  }>;
};

export const getPaymentSummary = (reservationId: number, session?: SessionLike) =>
  apiFetch<PaymentSummary>(`/api/payments/summary/${reservationId}`, { session });

export const makePayment = (payload: PaymentRequest, session?: SessionLike) =>
  apiFetch(`/api/payments`, { method: "POST", data: payload, session });

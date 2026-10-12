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
  manual_reference?: string;
  refund_of_transaction_id?: number;
  refund_reason?: string;
  company_night_charge_refund_allocations?: Array<{
    charge_id: number;
    amount: number;
  }>;
  collected_before?: boolean;
  collected_on?: string;
  prior_receipt_note?: string;
  company_night_charge_ids?: number[];
};

export type PaymentSummary = {
  reservation_id: number;
  confirmation_code: string;
  status: string;
  currency_code: string;
  total_amount: number | null;
  deposit_required: number | null;
  amount_paid: number | null;
  /** Hotel-collected completed payments; excludes OTA amounts paid elsewhere. */
  hotel_received_amount?: number | null;
  /** Confirmed OTA prepayment; shown for revenue context and never cash. */
  ota_prepaid_amount?: number | null;
  balance_due: number | null;
  // total_amount/balance_due only reflect the reservation's base price; they
  // ignore consumption charges (BillingAdjustment). operational_* includes
  // them and is the amount actually owed -- use it for collecting payment.
  operational_total_amount?: number;
  operational_balance_due?: number;
  billing_adjustment_total?: number;
  company_billing_deferred?: boolean;
  completed_payments: number;
  transactions: Array<{
    id: number;
    amount: number;
    applied_amount?: number | null;
    applied_currency?: string | null;
    company_night_charge_refundable_allocations?: Array<{
      charge_id: number;
      stay_date: string;
      remaining_amount: number | string;
    }>;
    fx_rate_snapshot?: number | null;
    gross_amount?: number;
    fee_amount?: number;
    currency: string;
    method: string;
    type: string;
    status: string;
    manual_reference?: string | null;
    refund_of_transaction_id?: number | null;
    refund_reason?: string | null;
    collected_before?: boolean;
    collected_on?: string | null;
    prior_receipt_note?: string | null;
    created_at: string;
  }>;
};

export type PaymentReceiptData = {
  id: number;
  reservation_id: number;
  confirmation_code: string;
  hotel_name: string;
  hotel_timezone: string;
  amount: number | string;
  applied_amount?: number | string | null;
  applied_currency?: string | null;
  fx_rate_snapshot?: number | null;
  gross_amount: number | string;
  fee_amount: number | string;
  currency: string;
  method: string;
  type: string;
  status: string;
  manual_reference?: string | null;
  refund_of_transaction_id?: number | null;
  created_at: string;
};

export type PaymentReceiptEmailRequest = {
  recipient_email: string;
};

export type PaymentReceiptEmailResponse = {
  transaction_id: number;
  status: "sent";
  replayed: boolean;
};

export const getPaymentSummary = (reservationId: number, session?: SessionLike) =>
  apiFetch<PaymentSummary>(`/api/payments/summary/${reservationId}`, { session });

export const getPaymentReceiptData = (transactionId: number, session?: SessionLike) =>
  apiFetch<PaymentReceiptData>(`/api/payments/transactions/${transactionId}/receipt`, { session });

export const newPaymentReceiptEmailIdempotencyKey = (transactionId: number) => {
  const requestId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `ui-payment-receipt-email-${transactionId}-${requestId}`;
};

export const emailPaymentReceipt = (
  transactionId: number,
  payload: PaymentReceiptEmailRequest,
  session?: SessionLike,
  idempotencyKey: string = newPaymentReceiptEmailIdempotencyKey(transactionId)
) =>
  apiFetch<PaymentReceiptEmailResponse>(`/api/payments/transactions/${transactionId}/receipt/email`, {
    method: "POST",
    data: payload,
    session,
    headers: { "Idempotency-Key": idempotencyKey }
  });

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

import { apiFetch, buildAuthHeaders, buildUrl, type SessionLike } from "./client";

export type PaymentMethod = "cash" | "mercado_pago" | "paypal" | "credit_card" | "debit_card" | "bank_transfer";

export type TransactionType = "deposit" | "full_payment" | "partial_payment" | "balance_payment" | "refund";

export type PaymentRequest = {
  reservation_id: number;
  amount: number;
  payment_method: PaymentMethod;
  /** Total cash physically handed over, including any configured surcharge. */
  cash_received_amount?: number;
  /** Voluntary amount retained as a tip, separate from the payment amount. */
  cash_tip_amount?: number;
  transaction_type: TransactionType;
  currency?: string;
  description?: string;
  manual_reference?: string;
  refund_of_transaction_id?: number;
  refund_component?: "payment" | "rounding_credit";
  refund_reason?: string;
  /** Signed backend FX/surcharge snapshot for this exact individual payment. */
  payment_quote_token?: string;
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
  rounding_credit_by_currency?: Array<{
    currency_code: string;
    issued_amount: number;
    refunded_amount: number;
    open_amount: number;
  }>;
  rounding_credit_sources?: Array<{
    source_transaction_id: number;
    currency_code: string;
    issued_amount: number;
    refunded_amount: number;
    open_amount: number;
  }>;
  /** Internal corrections visible to authorized payment managers. */
  payment_corrections?: PaymentCorrectionHistory[];
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
    cash_received_amount?: number | null;
    cash_change_amount?: number | null;
    cash_tip_amount?: number | null;
    currency: string;
    method: string;
    type: string;
    status: string;
    group_payment_batch_id?: number | null;
    manual_reference?: string | null;
    refund_of_transaction_id?: number | null;
    rounding_credit_amount?: number | null;
    credit_refund_amount?: number | null;
    refund_component?: "payment" | "rounding_credit" | null;
    refund_reason?: string | null;
    collected_before?: boolean;
    collected_on?: string | null;
    prior_receipt_note?: string | null;
    created_at: string;
  }>;
};

export type PaymentCorrectionType = "reassign" | "duplicate_reversal";

export type PaymentCorrectionRequest =
  | {
      correction_type: "reassign";
      destination_confirmation_code: string;
      reason: string;
    }
  | {
      correction_type: "duplicate_reversal";
      reason: string;
    };

export type PaymentCorrectionResponse = {
  correction_id: number;
  correction_type: PaymentCorrectionType;
  source_transaction_id: number;
  source_reservation_id: number;
  target_reservation_id: number | null;
  replacement_transaction_id: number | null;
  reason: string;
  actor_user_id?: number | null;
  created_at: string;
  replayed: boolean;
};

export type PaymentCorrectionHistory = Omit<PaymentCorrectionResponse, "replayed">;

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
  cash_received_amount?: number | string | null;
  cash_change_amount?: number | string | null;
  cash_tip_amount?: number | string | null;
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
  status: "sent" | "captured";
  delivery_mode: "provider" | "local_simulation";
  replayed: boolean;
};

export type PaymentReceiptPdfDownload = {
  blob: Blob;
  filename: string;
};

export const getPaymentSummary = (reservationId: number, session?: SessionLike) =>
  apiFetch<PaymentSummary>(`/api/payments/summary/${reservationId}`, { session });

export const getPaymentReceiptData = (transactionId: number, session?: SessionLike) =>
  apiFetch<PaymentReceiptData>(`/api/payments/transactions/${transactionId}/receipt`, { session });

export const downloadPaymentReceiptPdf = async (
  transactionId: number,
  session?: SessionLike
): Promise<PaymentReceiptPdfDownload> => {
  const response = await fetch(buildUrl(`/api/payments/transactions/${transactionId}/receipt.pdf`), {
    headers: buildAuthHeaders(session),
    credentials: "include"
  });
  if (!response.ok) throw new Error("No se pudo descargar el comprobante PDF.");

  const contentType = response.headers.get("content-type")?.split(";", 1)[0].trim().toLocaleLowerCase();
  if (contentType !== "application/pdf") {
    throw new Error("El servidor no devolvió un comprobante PDF válido.");
  }

  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const utf8Filename = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plainFilename = contentDisposition.match(/filename="?([^";]+)"?/i)?.[1];
  let filename = `comprobante-pago-${transactionId}.pdf`;
  if (utf8Filename) {
    try {
      filename = decodeURIComponent(utf8Filename);
    } catch {
      filename = `comprobante-pago-${transactionId}.pdf`;
    }
  } else if (plainFilename) {
    filename = plainFilename;
  }
  filename = filename.replace(/[\\/\r\n\0]/g, "_").trim();
  if (!filename || !filename.toLocaleLowerCase().endsWith(".pdf")) {
    filename = `comprobante-pago-${transactionId}.pdf`;
  }

  return { blob: await response.blob(), filename };
};

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

export const newPaymentCorrectionIdempotencyKey = (transactionId: number) => {
  const requestId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `ui-payment-correction-${transactionId}-${requestId}`;
};

export const correctPaymentTransaction = (
  transactionId: number,
  payload: PaymentCorrectionRequest,
  session?: SessionLike,
  idempotencyKey: string = newPaymentCorrectionIdempotencyKey(transactionId)
) =>
  apiFetch<PaymentCorrectionResponse>(`/api/payments/transactions/${transactionId}/correction`, {
    method: "POST",
    data: payload,
    session,
    headers: { "Idempotency-Key": idempotencyKey }
  });

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

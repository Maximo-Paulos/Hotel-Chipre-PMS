import { apiFetch, type SessionLike } from "./client";

export type PaymentLinkTest = {
  id: number;
  provider: string;
  recipient_email: string;
  amount: number;
  currency: string;
  description: string;
  external_reference: string;
  preference_id?: string | null;
  payment_url?: string | null;
  status: string;
  external_status?: string | null;
  external_payment_id?: string | null;
  refunded_amount?: number | null;
  email_sent_at?: string | null;
  sender_channel?: string | null;
  sender_email?: string | null;
  expires_at?: string | null;
  last_checked_at?: string | null;
  last_error?: string | null;
  paid_at?: string | null;
  refunded_at?: string | null;
  cancelled_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PaymentLinkTestCreatePayload = {
  recipient_email: string;
  amount: number;
  currency?: string;
  description: string;
  expires_in_minutes?: number;
};

export const listPaymentLinkTests = (session?: SessionLike) =>
  apiFetch<PaymentLinkTest[]>("/api/payment-link-tests", { session });

export const createMercadoPagoPaymentLinkTest = (payload: PaymentLinkTestCreatePayload, session?: SessionLike) =>
  apiFetch<PaymentLinkTest>("/api/payment-link-tests/mercadopago", {
    method: "POST",
    data: payload,
    session,
  });

export const refreshPaymentLinkTest = (testId: number, session?: SessionLike) =>
  apiFetch<PaymentLinkTest>(`/api/payment-link-tests/${testId}/refresh`, {
    method: "POST",
    session,
  });

export const cancelPaymentLinkTest = (testId: number, session?: SessionLike) =>
  apiFetch<PaymentLinkTest>(`/api/payment-link-tests/${testId}/cancel`, {
    method: "POST",
    session,
  });

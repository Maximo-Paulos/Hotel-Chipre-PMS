import { apiFetch, type SessionLike } from "./client";

export type PaymentLink = {
  id: number;
  reservation_id: number;
  provider: string;
  link_code: string;
  requested_amount: number;
  collected_amount: number;
  currency: string;
  recipient_email: string;
  status: string;
  external_checkout_url?: string | null;
  expires_at?: string | null;
  created_at: string;
};

export type PaymentLinkCreatePayload = {
  reservation_id: number;
  requested_amount: number;
  recipient_email: string;
  recipient_name?: string | null;
  recipient_phone?: string | null;
  currency?: string;
  title?: string;
  description?: string;
};

export const listPaymentLinks = (reservationId: number, session?: SessionLike) =>
  apiFetch<PaymentLink[]>(`/api/payment-links?reservation_id=${reservationId}`, { session });

export const createPaymentLink = (payload: PaymentLinkCreatePayload, session?: SessionLike) =>
  apiFetch<PaymentLink>("/api/payment-links", { method: "POST", data: payload, session });

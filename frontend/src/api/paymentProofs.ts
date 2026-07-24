import { apiFetch, type SessionLike } from "./client";

export type PaymentProofStatus = "pending" | "approved" | "rejected";

export type PaymentProof = {
  id: number;
  reservation_id: number;
  transaction_id?: number | null;
  amount: number | string;
  currency: string;
  payment_method: string;
  status: PaymentProofStatus;
  original_filename?: string | null;
  content_type: string;
  file_size_bytes: number;
  sha256_hex: string;
  rejection_reason?: string | null;
  created_at: string;
  reviewed_at?: string | null;
};

export type PaymentProofCreatePayload = {
  reservation_id: number;
  amount: number;
  image_base64: string;
  original_filename?: string | null;
};

export const listPaymentProofs = (reservationId: number, session?: SessionLike) =>
  apiFetch<PaymentProof[]>(`/api/payment-proofs?reservation_id=${reservationId}`, { session });

export const submitPaymentProof = (payload: PaymentProofCreatePayload, session?: SessionLike) =>
  apiFetch<PaymentProof>("/api/payment-proofs", { method: "POST", data: payload, session });

export const approvePaymentProof = (proofId: number, session?: SessionLike) =>
  apiFetch<PaymentProof>(`/api/payment-proofs/${proofId}/approve`, { method: "POST", session });

export const rejectPaymentProof = (proofId: number, reason: string, session?: SessionLike) =>
  apiFetch<PaymentProof>(`/api/payment-proofs/${proofId}/reject`, {
    method: "POST",
    data: { reason },
    session
  });

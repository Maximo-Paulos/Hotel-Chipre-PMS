import { apiFetch, type SessionLike } from "./client";

export type ReservationEmailKind = "confirmation" | "voucher";
export type ReservationEmailStatus = "pending" | "accepted" | "failed" | "unknown";

export type ReservationEmailDelivery = {
  id: number;
  reservation_id: number;
  kind: ReservationEmailKind;
  status: ReservationEmailStatus;
  recipient_email: string;
  subject: string;
  provider_message_id?: string | null;
  attempt_count: number;
  is_resend: boolean;
  requested_by_user_id?: number | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
  accepted_at?: string | null;
};

export const listReservationCommunications = (reservationId: number, session?: SessionLike) =>
  apiFetch<ReservationEmailDelivery[]>(`/api/reservations/${reservationId}/communications`, { session });

export const sendReservationCommunication = (
  reservationId: number,
  payload: { kind: ReservationEmailKind; recipient_email?: string | null; resend?: boolean },
  session?: SessionLike
) =>
  apiFetch<{ delivery: ReservationEmailDelivery; deduplicated: boolean }>(
    `/api/reservations/${reservationId}/communications`,
    { method: "POST", data: payload, session }
  );

import { apiFetch, type SessionLike } from "./client";
import type { Reservation } from "./reservations";

export type WaitlistStatus = "waiting" | "promoted" | "cancelled" | "expired";

export type WaitlistEntry = {
  id: number;
  hotel_id: number;
  guest_id: number;
  category_id: number;
  promoted_reservation_id?: number | null;
  check_in_date: string;
  check_out_date: string;
  num_adults: number;
  num_children: number;
  status: WaitlistStatus;
  priority: number;
  notes?: string | null;
  contact_phone?: string | null;
  created_at: string;
  promoted_at?: string | null;
  expired_at?: string | null;
};

export type WaitlistEntryCreate = {
  guest_id: number;
  category_id: number;
  check_in_date: string;
  check_out_date: string;
  num_adults?: number;
  num_children?: number;
  priority?: number;
  notes?: string | null;
  contact_phone?: string | null;
};

export type WaitlistPromotePayload = {
  room_id?: number | null;
  notes?: string | null;
};

export type WaitlistPromoteResponse = {
  waitlist_entry: WaitlistEntry;
  reservation: Reservation;
};

export const listWaitlistEntries = (statusFilter = "", session?: SessionLike) => {
  const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  return apiFetch<WaitlistEntry[]>(`/api/waitlist/${query}`, { session });
};

export const createWaitlistEntry = (payload: WaitlistEntryCreate, session?: SessionLike) =>
  apiFetch<WaitlistEntry>("/api/waitlist/", { method: "POST", data: payload, session });

export const promoteWaitlistEntry = (entryId: number, payload: WaitlistPromotePayload, session?: SessionLike) =>
  apiFetch<WaitlistPromoteResponse>(`/api/waitlist/${entryId}/promote`, {
    method: "POST",
    data: payload,
    session
  });

export const cancelWaitlistEntry = (entryId: number, session?: SessionLike) =>
  apiFetch<WaitlistEntry>(`/api/waitlist/${entryId}/cancel`, { method: "POST", session });

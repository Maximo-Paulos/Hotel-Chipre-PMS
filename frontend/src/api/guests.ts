import { apiFetch, type SessionLike } from "./client";

export type Guest = {
  id: number;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone?: string | null;
  document_number?: string | null;
  document_type?: string | null;
  address_line1?: string | null;
  city?: string | null;
  country?: string | null;
};

export type GuestPayload = {
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  terms_accepted?: boolean;
};

export const createGuest = (payload: GuestPayload, session?: SessionLike) =>
  apiFetch<Guest>("/api/guests", { method: "POST", data: payload, session });

export const getGuest = (guestId: number, session?: SessionLike) =>
  apiFetch<Guest>(`/api/guests/${guestId}`, { session });

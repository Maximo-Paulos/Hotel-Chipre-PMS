import { apiFetch, type SessionLike } from "./client";

export type Guest = {
  id: number;
  first_name: string;
  last_name: string;
  nationality?: string | null;
  email?: string | null;
  phone?: string | null;
  document_number?: string | null;
  document_type?: string | null;
  address_line2?: string | null;
  address_line1?: string | null;
  city?: string | null;
  state_province?: string | null;
  postal_code?: string | null;
  country?: string | null;
  special_requests?: string | null;
  observations?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type GuestPayload = {
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  terms_accepted?: boolean;
};

export type GuestUpdatePayload = Partial<GuestPayload> & {
  document_type?: string | null;
  document_number?: string | null;
  nationality?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state_province?: string | null;
  postal_code?: string | null;
  country?: string | null;
  special_requests?: string | null;
  observations?: string | null;
};

export const createGuest = (payload: GuestPayload, session?: SessionLike) =>
  apiFetch<Guest>("/api/guests/", { method: "POST", data: payload, session });

export const listGuests = (search = "", session?: SessionLike) =>
  apiFetch<Guest[]>(`/api/guests/${search ? `?search=${encodeURIComponent(search)}` : ""}`, { session });

export const getGuest = (guestId: number, session?: SessionLike) =>
  apiFetch<Guest>(`/api/guests/${guestId}`, { session });

export const updateGuest = (guestId: number, payload: GuestUpdatePayload, session?: SessionLike) =>
  apiFetch<Guest>(`/api/guests/${guestId}`, { method: "PATCH", data: payload, session });

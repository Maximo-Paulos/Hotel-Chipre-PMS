import { apiFetch, buildAuthHeaders, buildUrl, type SessionLike } from "./client";

export type Guest = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  nationality?: string | null;
  email?: string | null;
  phone?: string | null;
  document_number?: string | null;
  document_type?: "DNI" | "PASSPORT" | "CEDULA" | null;
  address_line2?: string | null;
  address_line1?: string | null;
  city?: string | null;
  state_province?: string | null;
  postal_code?: string | null;
  country?: string | null;
  special_requests?: string | null;
  observations?: string | null;
  created_at?: string | null;
  retention_until?: string | null;
  updated_at?: string | null;
  companions?: GuestCompanion[] | null;
};

export type GuestCompanion = {
  id?: number;
  guest_id?: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  document_type?: "DNI" | "PASSPORT" | "CEDULA" | null;
  document_number?: string | null;
  nationality?: string | null;
  relationship_to_guest?: string | null;
};

export type GuestPayload = {
  first_name: string;
  last_name: string;
  date_of_birth?: string;
  document_type?: "DNI" | "PASSPORT" | "CEDULA";
  document_number?: string;
  nationality?: string;
  email?: string;
  phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state_province?: string;
  postal_code?: string;
  country?: string;
  terms_accepted?: boolean;
  special_requests?: string;
  observations?: string;
  companions?: GuestCompanion[];
};

export type GuestUpdatePayload = Partial<GuestPayload> & {
  date_of_birth?: string | null;
  document_type?: "DNI" | "PASSPORT" | "CEDULA" | null;
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

export type GuestCompanionPayload = GuestCompanion;

export const createGuest = (payload: GuestPayload, session?: SessionLike) =>
  apiFetch<Guest>("/api/guests/", { method: "POST", data: payload, session });

export const listGuests = (search = "", session?: SessionLike) =>
  apiFetch<Guest[]>(`/api/guests/${search ? `?search=${encodeURIComponent(search)}` : ""}`, { session });

export const getGuest = (guestId: number, session?: SessionLike) =>
  apiFetch<Guest>(`/api/guests/${guestId}`, { session });

export const updateGuest = (guestId: number, payload: GuestUpdatePayload, session?: SessionLike) =>
  apiFetch<Guest>(`/api/guests/${guestId}`, { method: "PATCH", data: payload, session });

export const addGuestCompanions = (guestId: number, companions: GuestCompanionPayload[], session?: SessionLike) =>
  apiFetch<GuestCompanion[]>(`/api/guests/${guestId}/companions`, {
    method: "POST",
    data: companions,
    session
  });

export const exportGuestLedger = (fromDate: string, toDate: string, session?: SessionLike) =>
  fetch(buildUrl(`/api/guests/ledger/export?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`), {
    headers: buildAuthHeaders(session)
  });

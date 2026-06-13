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

export type GuestTagType =
  | "no_pago"
  | "robo"
  | "conflictivo"
  | "robo_cosas"
  | "prohibido_alojar"
  | "requiere_deposito"
  | "vip"
  | "alergias"
  | "otro";

export type GuestTag = {
  id: number;
  hotel_id: number;
  guest_id: number;
  tag_type: GuestTagType;
  note?: string | null;
  expires_at?: string | null;
  created_at: string;
  created_by_user_id?: number | null;
};

export type GuestTagPayload = {
  tag_type: GuestTagType;
  note?: string | null;
  expires_at?: string | null;
};

export type GuestStaySummary = {
  reservation_id: number;
  confirmation_code: string;
  status: string;
  check_in_date: string;
  check_out_date: string;
  room_id?: number | null;
  room_number?: string | null;
  notes?: string | null;
};

export type GuestQuickProfile = {
  guest: Guest;
  active_tags: GuestTag[];
  last_stays: GuestStaySummary[];
};

export type GuestCheckInReservation = {
  id: number;
  confirmation_code: string;
  guest_id: number;
  room_id?: number | null;
  check_in_date: string;
  check_out_date: string;
  status: string;
  balance_due?: number;
  nights?: number;
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

export const searchGuests = (q: string, limit = 20, session?: SessionLike) =>
  apiFetch<Guest[]>(`/api/guests/search?q=${encodeURIComponent(q)}&limit=${limit}`, { session });

export const getGuest = (guestId: number, session?: SessionLike) =>
  apiFetch<Guest>(`/api/guests/${guestId}`, { session });

export const getGuestQuickProfile = (guestId: number, session?: SessionLike) =>
  apiFetch<GuestQuickProfile>(`/api/guests/${guestId}/quick-profile`, { session });

export const listGuestTags = (guestId: number, session?: SessionLike) =>
  apiFetch<GuestTag[]>(`/api/guests/${guestId}/tags`, { session });

export const addGuestTag = (guestId: number, payload: GuestTagPayload, session?: SessionLike) =>
  apiFetch<GuestTag>(`/api/guests/${guestId}/tags`, { method: "POST", data: payload, session });

export const resolveGuestTag = (guestId: number, tagId: number, session?: SessionLike) =>
  apiFetch<GuestTag>(`/api/guests/${guestId}/tags/${tagId}/resolve`, { method: "POST", session });

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

export const checkInGuestReservation = (
  reservationId: number,
  payload: { override_prohibido?: boolean } = {},
  session?: SessionLike
) =>
  apiFetch<GuestCheckInReservation>(`/api/checkin/${reservationId}`, {
    method: "POST",
    data: payload,
    session
  });

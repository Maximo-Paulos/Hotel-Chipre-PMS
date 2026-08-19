import { apiFetch, buildAuthHeaders, buildUrl, type SessionLike } from "./client";
import type { RestrictionOverride } from "./guestRestrictions";

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
  terms_accepted?: boolean;
  // v72 §7.2 (B3.2/B3.3) -- always required to complete check-in.
  birth_place?: string | null;
  birth_country?: string | null;
  marital_status?: string | null;
  occupation?: string | null;
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
  birth_place?: string;
  birth_country?: string;
  marital_status?: string;
  occupation?: string;
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
  birth_place?: string | null;
  birth_country?: string | null;
  marital_status?: string | null;
  occupation?: string | null;
  special_requests?: string | null;
  observations?: string | null;
};

export type GuestCompanionPayload = GuestCompanion;

export const createGuest = (payload: GuestPayload, session?: SessionLike) =>
  apiFetch<Guest>("/api/guests/", { method: "POST", data: payload, session });

// A5: the backend has paginated this endpoint since app/api/guests.py:114-130
// (skip/limit/search), but nothing here sent skip/limit -- every hotel with
// more than 50 guests silently only ever saw the first page. No `total`
// count field: matches the A2 precedent for /api/reservations (same
// skip/limit/order shape, no COUNT(*) in the response) -- the UI treats a
// full page (length === limit) as "there may be more" instead of paying for
// an exact count.
export type GuestFilters = {
  search?: string;
  skip?: number;
  limit?: number;
};

const buildGuestQueryString = (filters: GuestFilters = {}) => {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (typeof filters.skip === "number") params.set("skip", String(filters.skip));
  if (typeof filters.limit === "number") params.set("limit", String(filters.limit));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
};

export const listGuests = (filters: GuestFilters = {}, session?: SessionLike) =>
  apiFetch<Guest[]>(`/api/guests/${buildGuestQueryString(filters)}`, { session });

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

export type GuestCheckinValidation = {
  guest_id: number;
  valid: boolean;
  errors: string[];
};

// B3.3/B3.4: lets the check-in UI know *before* attempting the check-in
// whether the guest is missing required data, so it can show the capture
// form up front instead of surfacing a raw 400 after the fact.
export const validateGuestForCheckin = (guestId: number, session?: SessionLike) =>
  apiFetch<GuestCheckinValidation>(`/api/checkin/validate/${guestId}`, { session });

export const checkInGuestReservation = (
  reservationId: number,
  payload: { override_prohibido?: boolean; restriction_override?: RestrictionOverride | null } = {},
  session?: SessionLike
) =>
  apiFetch<GuestCheckInReservation>(`/api/checkin/${reservationId}`, {
    method: "POST",
    data: payload,
    session
  });

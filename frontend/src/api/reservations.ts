import { apiFetch, type SessionLike } from "./client";

export type ReservationStatus =
  | "pending"
  | "deposit_paid"
  | "fully_paid"
  | "checked_in"
  | "checked_out"
  | "cancelled";

export type ReservationSource = "direct" | "booking" | "expedia" | "other_ota";

export type Reservation = {
  id: number;
  confirmation_code: string;
  guest_id: number;
  room_id: number | null;
  category_id: number;
  check_in_date: string;
  check_out_date: string;
  actual_check_in?: string | null;
  actual_check_out?: string | null;
  total_amount: number;
  amount_paid: number;
  deposit_amount: number;
  status: ReservationStatus;
  source: ReservationSource;
  external_id?: string | null;
  num_adults: number;
  num_children: number;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  balance_due?: number;
  nights?: number;
  additional_guests?: Array<{
    id: number;
    first_name: string;
    last_name: string;
    document_type?: string | null;
    document_number?: string | null;
  }>;
};

export type ReservationFilters = {
  status?: ReservationStatus | "all" | "";
  fromDate?: string;
  toDate?: string;
};

export type ReservationPayload = {
  guest_id: number;
  category_id: number;
  room_id?: number | null;
  check_in_date: string;
  check_out_date: string;
  num_adults?: number;
  num_children?: number;
  notes?: string | null;
  source?: ReservationSource;
  external_id?: string | null;
};

export type ReservationUpdatePayload = Partial<ReservationPayload> & {
  status?: ReservationStatus;
};

const buildQueryString = (filters: ReservationFilters = {}) => {
  const params = new URLSearchParams();
  if (filters.status && filters.status !== "all" && filters.status !== "") {
    params.set("status_filter", filters.status);
  }
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
};

export const listReservations = (filters: ReservationFilters = {}, session?: SessionLike) =>
  apiFetch<Reservation[]>(`/api/reservations${buildQueryString(filters)}`, { session });

export const getReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}`, { session });

export const createReservation = (payload: ReservationPayload, session?: SessionLike) =>
  apiFetch<Reservation>("/api/bookings", { method: "POST", data: payload, session });

export const updateReservation = (id: number, payload: ReservationUpdatePayload, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/bookings/${id}`, { method: "PATCH", data: payload, session });

export const cancelReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}/cancel`, { method: "POST", session });

export const checkInReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/checkin/${id}`, { method: "POST", session });

export const checkOutReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/checkin/checkout/${id}`, { method: "POST", session });

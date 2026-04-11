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
  source_provider_code?: string | null;
  num_adults: number;
  num_children: number;
  subtotal_amount?: number;
  tax_amount?: number;
  fee_amount?: number;
  commission_amount?: number;
  net_amount?: number;
  currency_code?: string;
  fx_rate_snapshot?: number | null;
  allocation_status?: string;
  allocation_locked?: boolean;
  requires_manual_review?: boolean;
  payment_collection_model?: string;
  settlement_status?: string;
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

export type ReservationPendingAction = {
  action_key: string;
  code: string;
  priority: "critical" | "high" | "medium" | "low";
  title: string;
  detail: string;
  reservation_id: number;
  confirmation_code: string;
  reservation_status: string;
  source: string;
  source_provider_code?: string | null;
  payment_collection_model?: string | null;
  settlement_status?: string | null;
  check_in_date: string;
  check_out_date: string;
  reference_type?: string | null;
  reference_id?: number | null;
};

export type ReservationBillingAdjustmentSummary = {
  id: number;
  type: string;
  amount: number;
  tax_amount?: number | null;
  total_amount: number;
  currency_code: string;
  notes?: string | null;
};

export type ReservationTransactionSummary = {
  id: number;
  amount: number;
  currency: string;
  method: string;
  type: string;
  status: string;
  created_at: string;
};

export type ReservationFinancialSummary = {
  reservation_id: number;
  confirmation_code: string;
  status: string;
  currency_code: string;
  total_amount: number;
  deposit_required: number;
  amount_paid: number;
  balance_due: number;
  operational_total_amount: number;
  operational_balance_due: number;
  billing_adjustment_total: number;
  payment_collection_model: string;
  settlement_status: string;
  has_financial_reconciliation_gap: boolean;
  financial_reconciliation_gap: number;
  recommended_next_action?: string | null;
  transactions: ReservationTransactionSummary[];
  billing_adjustments: ReservationBillingAdjustmentSummary[];
  completed_payments: number;
};

export type ReservationOTALinkSummary = {
  id: number;
  provider_id: number;
  external_reservation_id: string;
  external_confirmation_code?: string | null;
  provider_state: string;
  sync_status?: string | null;
  error_message?: string | null;
};

export type ReservationAdjustmentSummary = {
  id: number;
  kind: string;
  status: string;
  reason_code?: string | null;
  request_source?: string | null;
  amount_delta?: number | null;
  currency_code?: string | null;
  external_resolution_status?: string | null;
  resulting_reservation_id?: number | null;
  ota_reservation_link_id?: number | null;
  notes?: string | null;
};

export type ReservationRoomMoveSummary = {
  id: number;
  move_type: string;
  reason_code?: string | null;
  from_room_id?: number | null;
  to_room_id?: number | null;
  notes?: string | null;
  occurred_at?: string | null;
};

export type ReservationOperationsSummary = {
  reservation_id: number;
  confirmation_code: string;
  status: string;
  source: string;
  source_provider_code?: string | null;
  allocation_status: string;
  requires_manual_review: boolean;
  payment_collection_model: string;
  settlement_status: string;
  pending_action_count: number;
  pending_actions: ReservationPendingAction[];
  financial_summary: ReservationFinancialSummary;
  ota_link?: ReservationOTALinkSummary | null;
  open_adjustments: ReservationAdjustmentSummary[];
  latest_room_move?: ReservationRoomMoveSummary | null;
};

export type ReservationActionResolvePayload = {
  notes?: string | null;
};

export type ReservationExternalResolutionResponse = {
  reservation_id: number;
  changed_adjustments: number;
  ota_link_resolved: boolean;
  settlement_status: string;
  resolved_by_user_id?: number | null;
};

export type ReservationManualReviewResponse = {
  reservation_id: number;
  requires_manual_review: boolean;
  allocation_status: string;
  reviewed_by_user_id?: number | null;
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
  apiFetch<Reservation[]>(`/api/reservations/${buildQueryString(filters)}`, { session });

export const getReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}`, { session });

export const getReservationOperationsSummary = (id: number, session?: SessionLike) =>
  apiFetch<ReservationOperationsSummary>(`/api/reservations/${id}/operations-summary`, { session });

export const listPendingReservationActions = (limit = 100, session?: SessionLike) =>
  apiFetch<ReservationPendingAction[]>(`/api/reservations/actions/pending?limit=${limit}`, { session });

export const createReservation = (payload: ReservationPayload, session?: SessionLike) =>
  apiFetch<Reservation>("/api/reservations/", { method: "POST", data: payload, session });

export const updateReservation = (id: number, payload: ReservationUpdatePayload, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}`, { method: "PATCH", data: payload, session });

export const cancelReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}/cancel`, { method: "POST", session });

export const checkInReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/checkin/${id}`, { method: "POST", session });

export const checkOutReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/checkin/checkout/${id}`, { method: "POST", session });

export const resolveReservationExternal = (
  id: number,
  payload: ReservationActionResolvePayload,
  session?: SessionLike
) =>
  apiFetch<ReservationExternalResolutionResponse>(`/api/reservations/${id}/operations/resolve-external`, {
    method: "POST",
    data: payload,
    session
  });

export const clearReservationManualReview = (
  id: number,
  payload: ReservationActionResolvePayload,
  session?: SessionLike
) =>
  apiFetch<ReservationManualReviewResponse>(`/api/reservations/${id}/operations/clear-manual-review`, {
    method: "POST",
    data: payload,
    session
  });

import { apiFetch, type SessionLike } from "./client";
import type { GuestUpdatePayload } from "./guests";
import type { RestrictionOverride } from "./guestRestrictions";
import type { PaymentMethod, PaymentRequest } from "./payments";
import type { PaymentLink, PaymentLinkCreatePayload } from "./paymentLinks";

export type ReservationStatus =
  | "pending"
  | "deposit_paid"
  | "fully_paid"
  | "pre_check_in"
  | "checked_in"
  | "checked_out"
  | "cancelled"
  | "no_show";

export type ReservationSource = "direct" | "booking" | "expedia" | "other_ota";

export type Reservation = {
  id: number;
  confirmation_code: string;
  guest_id: number;
  guest?: {
    id: number;
    first_name: string;
    last_name: string;
    document_type?: string | null;
    document_number?: string | null;
  } | null;
  room_id: number | null;
  room_number?: string | null;
  category_id: number;
  category_name?: string | null;
  company_id?: number | null;
  group_id?: number | null;
  check_in_date: string;
  check_out_date: string;
  actual_check_in?: string | null;
  actual_check_out?: string | null;
  total_amount: number | null;
  amount_paid: number | null;
  deposit_amount: number | null;
  status: ReservationStatus;
  source: ReservationSource;
  external_id?: string | null;
  source_provider_code?: string | null;
  num_adults: number;
  num_children: number;
  subtotal_amount?: number | null;
  tax_amount?: number | null;
  fee_amount?: number | null;
  commission_amount?: number | null;
  net_amount?: number | null;
  currency_code?: string;
  fx_rate_snapshot?: number | null;
  // Two independently-typed prices for manual OTA loads (NOT a conversion
  // of one into the other) so the receptionist can quote either currency
  // to the guest. Separate from total_amount/currency_code, which remain
  // the canonical billing amount.
  quoted_amount_ars?: number | null;
  quoted_amount_usd?: number | null;
  external_paid_amount?: number | null;
  external_paid_currency?: string | null;
  external_paid_balance_credit_applied?: boolean;
  external_paid_reference?: string | null;
  external_paid_confirmed?: boolean;
  allocation_status?: string;
  allocation_locked?: boolean;
  requires_manual_review?: boolean;
  payment_collection_model?: string;
  settlement_status?: string;
  company_billing_deferred?: boolean;
  manual_rate_reason?: string | null;
  notes?: string | null;
  arrival_time_hint?: string | null;
  reservation_comment?: string | null;
  company_extension_request_pending?: boolean;
  company_extension_request_note?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  version?: number;
  balance_due?: number | null;
  nights?: number;
  additional_guests?: Array<{
    id: number;
    first_name: string;
    last_name: string;
    document_type?: string | null;
    document_number?: string | null;
  }>;
};

/** Company accommodation billed outside the PMS; only explicit nightly extras are payable here. */
export const isDeferredCompanyReservation = (
  reservation: Pick<Reservation, "company_id" | "settlement_status" | "company_billing_deferred"> | null | undefined
): boolean => Boolean(
  reservation?.company_id &&
  (reservation.company_billing_deferred === true || ["deferred", "settled"].includes(reservation.settlement_status ?? ""))
);

export type ReservationPendingAction = {
  action_key: string;
  code: string;
  priority: "critical" | "high" | "medium" | "low";
  title: string;
  detail: string;
  reservation_id: number;
  confirmation_code: string;
  guest_name?: string | null;
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
  manual_reference?: string | null;
  refund_of_transaction_id?: number | null;
  refund_reason?: string | null;
  created_at: string;
};

export type ReservationFinancialSummary = {
  reservation_id: number;
  confirmation_code: string;
  status: string;
  currency_code: string;
  total_amount: number | null;
  deposit_required: number | null;
  amount_paid: number | null;
  hotel_received_amount?: number | null;
  ota_prepaid_amount?: number | null;
  balance_due: number | null;
  operational_total_amount: number;
  operational_balance_due: number;
  billing_adjustment_total: number;
  payment_collection_model: string;
  settlement_status: string;
  has_financial_reconciliation_gap: boolean;
  financial_reconciliation_gap: number | null;
  company_billing_deferred?: boolean;
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

export type ReservationOrder = "recent" | "check_in";

export type ReservationFilters = {
  status?: ReservationStatus | "all" | "";
  fromDate?: string;
  toDate?: string;
  search?: string;
  skip?: number;
  limit?: number;
  companyId?: number;
  /**
   * "recent" (created_at DESC, newest first) is the backend default -- used
   * for dashboards / "recent activity" views. "check_in" preserves the
   * pre-A2 ordering (check_in_date ASC) for operational views that already
   * assume arrivals are sorted by stay date.
   */
  order?: ReservationOrder;
  /** Server-side operational filter for arrivals that have not entered yet. */
  upcomingOnly?: boolean;
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
  arrival_time_hint?: string | null;
  reservation_comment?: string | null;
  source?: ReservationSource;
  company_id?: number | null;
  external_id?: string | null;
  pricing_payment_method?: string | null;
  deposit_amount?: number | null;
  quote_token?: string | null;
  // B4: manual tarifa override -- when set, the backend skips the
  // auto-computed daily-rate/rate-plan total for this reservation and uses
  // this amount instead (see app/services/reservation_service.py
  // _apply_manual_total_override). target_currency only relabels
  // currency_code; it does not run a live FX conversion unless the category
  // also has a rate_plan + OTACurrencyRate configured (fx_rate_snapshot
  // stays null otherwise -- show it only when present).
  total_amount?: number | null;
  confirm_large_total_adjustment?: boolean;
  target_currency?: string | null;
  manual_rate_reason?: string | null;
  paid_total_change_reason?: string | null;
  // Authorizes bypassing an active guest restriction after the operator
  // confirms an override reason -- see RestrictionOverrideModal. Only
  // actors with reservation:prohibition_override can use it; others get a
  // 403 (see app/api/reservations.py).
  restriction_override?: RestrictionOverride | null;
};

// Aggregated or per-night promotion application -- see
// app.services.promotion_service.apply_promotions_to_night.
export type ReservationQuotePromotionApplied = {
  promotion_id: number;
  code: string;
  version: number;
  benefit_type: "fixed" | "percentage";
  benefit_value: string;
  amount_deducted: string;
};

export type ReservationQuote = {
  status: "ok";
  company_billing_deferred?: boolean;
  billing_mode?: string;
  amounts_disclosed?: boolean;
  category_id: number;
  check_in_date: string;
  check_out_date: string;
  nights: number;
  nightly_rate: number | null;
  subtotal_amount: number | null;
  tax_amount: number | null;
  fee_amount: number | null;
  commission_amount: number | null;
  net_amount: number | null;
  total_amount: number | null;
  deposit_amount: number | null;
  currency_code: string;
  manual_rate_min_adjustment_pct?: string | number | null;
  manual_rate_max_adjustment_pct?: string | number | null;
  pricing_payment_method?: string | null;
  pricing_revision: string;
  breakdown: Array<{
    date: string;
    price: number;
    base_price?: number;
    source?: string;
    promotions_applied?: ReservationQuotePromotionApplied[];
  }>;
  // Aggregated across every night in the stay (same entries also appear
  // per-night inside `breakdown[].promotions_applied`).
  promotions_applied?: ReservationQuotePromotionApplied[];
  quote_token: string;
  expires_at: string;
};

export type ReservationQuoteParams = {
  category_id: number;
  check_in_date: string;
  check_out_date: string;
  pricing_payment_method?: string | null;
  occupancy?: number;
  // When set, the backend 409s with GUEST_PROHIBITED if the guest has an
  // active restriction (see app/api/bookings.py price_quote) -- the quote
  // endpoint never accepts an override, this is a preview-time warning only.
  guest_id?: number | null;
  company_id?: number | null;
};

export type ReservationGroupSummary = {
  id: number;
  hotel_id: number;
  guest_id: number;
  guest_name: string;
  company_id?: number | null;
  company_name?: string | null;
  check_in_date: string;
  check_out_date: string;
  notes?: string | null;
  reservation_count: number;
  room_count: number;
  reservation_ids: number[];
  reservation_codes: string[];
  reservations: Array<{
    id: number;
    confirmation_code: string;
    total_amount: number | null;
    amount_paid: number | null;
    balance_due: number | null;
    currency_code: string;
    status: ReservationStatus;
    company_billing_deferred: boolean;
  }>;
  total_amount: number | null;
  amount_paid: number | null;
  balance_due: number | null;
  company_billing_deferred?: boolean;
  currency_code: string;
  created_at: string;
};

export type ReservationGroupPaymentPayload = {
  received_amount: number;
  currency?: string;
  payment_method: Exclude<PaymentMethod, "mercado_pago" | "paypal">;
  manual_reference?: string;
  description?: string;
  allocations: Array<{
    reservation_id: number;
    received_amount: number;
    company_night_charge_ids?: number[];
  }>;
};

export type ReservationGroupPaymentResult = {
  id: number;
  group_id: number;
  received_amount: number;
  currency: string;
  payment_method: string;
  manual_reference?: string | null;
  description?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  allocations: Array<{
    reservation_id: number;
    transaction_id: number;
    received_amount: number;
  }>;
};

export const newReservationGroupPaymentIdempotencyKey = () => {
  const requestId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `ui-group-payment-${requestId}`;
};

export const createReservationGroupPayment = (
  groupId: number,
  payload: ReservationGroupPaymentPayload,
  session?: SessionLike,
  idempotencyKey: string = newReservationGroupPaymentIdempotencyKey()
) => apiFetch<ReservationGroupPaymentResult>(`/api/reservation-groups/${groupId}/payments`, {
  method: "POST",
  data: payload,
  session,
  headers: { "Idempotency-Key": idempotencyKey }
});

export const RESERVATION_GROUP_SUMMARY_LIMIT = 6;

export const listReservationGroups = (session?: SessionLike) =>
  apiFetch<ReservationGroupSummary[]>(
    `/api/reservation-groups?limit=${RESERVATION_GROUP_SUMMARY_LIMIT}`,
    { session }
  );

export const createReservationGroup = (reservations: ReservationPayload[], session?: SessionLike) =>
  apiFetch<ReservationGroupSummary>("/api/reservation-groups", {
    method: "POST",
    data: { reservations },
    session
  });

export type ReservationUpdatePayload = Partial<ReservationPayload> & {
  status?: ReservationStatus;
  client_version?: number;
};

export type ReservationNoShowPayload = {
  client_version: number;
  notes?: string | null;
};

export type ReservationRoomMovePayload = {
  client_version: number;
  to_room_id: number;
  reason_code: string;
  notes?: string | null;
  price_action?: "keep" | "reprice";
  origin_room_disposition?: "cleaning" | "available" | "maintenance" | null;
  origin_room_disposition_note?: string | null;
};

export type ReservationRoomMoveResponse = {
  reservation: Reservation;
  category_changed: boolean;
  price_action: "keep" | "reprice";
  previous_total_amount: number;
  quoted_total_amount: number;
  amount_delta: number;
  currency_code: string;
  origin_room_disposition?: "cleaning" | "available" | "maintenance" | null;
  origin_room_disposition_note?: string | null;
  origin_room_status_before?: string | null;
  origin_room_status_after?: string | null;
};

export type ReservationChargePayload = {
  amount: number;
  currency_code?: string;
  description: string;
};

const buildQueryString = (filters: ReservationFilters = {}) => {
  const params = new URLSearchParams();
  if (filters.status && filters.status !== "all") {
    params.set("status_filter", filters.status);
  }
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  if (filters.search) params.set("search", filters.search);
  if (typeof filters.skip === "number") params.set("skip", String(filters.skip));
  if (typeof filters.limit === "number") params.set("limit", String(filters.limit));
  if (filters.order) params.set("order", filters.order);
  if (filters.upcomingOnly) params.set("upcoming_only", "true");
  if (typeof filters.companyId === "number") params.set("company_id", String(filters.companyId));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
};

export const listReservations = (filters: ReservationFilters = {}, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<Reservation[]>(`/api/reservations/${buildQueryString(filters)}`, { session, signal });

export const getReservation = (id: number, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<Reservation>(`/api/reservations/${id}`, { session, signal });

export const getReservationOperationsSummary = (id: number, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<ReservationOperationsSummary>(`/api/reservations/${id}/operations-summary`, { session, signal });

export const listPendingReservationActions = (limit = 100, session?: SessionLike, signal?: AbortSignal) =>
  apiFetch<ReservationPendingAction[]>(`/api/reservations/actions/pending?limit=${limit}`, { session, signal });

export const createReservation = (payload: ReservationPayload, session?: SessionLike) =>
  apiFetch<Reservation>("/api/reservations/", { method: "POST", data: payload, session });

// B4: "Cargar reserva de OTA" -- backend is an upsert keyed by (channel,
// external_id), NOT a create-or-reject: submitting the same pair again
// updates the existing reservation instead of erroring (see
// app/services/ota_manual_service.py create_or_update_manual_ota_reservation).
// There is no separate "duplicate" error to catch here.
export type ManualOtaChannel = "booking" | "expedia" | "despegar" | "other_ota";

export type ManualOtaReservationPayload = {
  guest_id: number;
  category_id: number;
  room_id?: number | null;
  check_in_date: string;
  check_out_date: string;
  num_adults?: number;
  num_children?: number;
  notes?: string | null;
  arrival_time_hint?: string | null;
  reservation_comment?: string | null;
  channel: ManualOtaChannel;
  external_id: string;
  external_confirmation_code?: string | null;
  target_currency?: string | null;
  total_amount?: number | null;
  // Two independent prices the operator types by hand (ARS and USD), not a
  // conversion of one into the other -- see Reservation.quoted_amount_ars/usd.
  quoted_amount_ars?: number | null;
  quoted_amount_usd?: number | null;
  amount_paid?: number | null;
  external_paid_currency?: string | null;
  external_paid_reference?: string | null;
};

export const createManualOtaReservation = (payload: ManualOtaReservationPayload, session?: SessionLike) =>
  apiFetch<Reservation>("/api/reservations/manual-ota", { method: "POST", data: payload, session });

export const getReservationQuote = (params: ReservationQuoteParams, session?: SessionLike, signal?: AbortSignal) => {
  const query = new URLSearchParams({
    category_id: String(params.category_id),
    check_in_date: params.check_in_date,
    check_out_date: params.check_out_date
  });
  if (params.pricing_payment_method) query.set("pricing_payment_method", params.pricing_payment_method);
  if (params.occupancy && params.occupancy > 0) query.set("occupancy", String(params.occupancy));
  if (params.guest_id) query.set("guest_id", String(params.guest_id));
  if (params.company_id) query.set("company_id", String(params.company_id));
  return apiFetch<ReservationQuote>(`/api/bookings/price-quote?${query.toString()}`, { session, signal });
};

export const updateReservation = (id: number, payload: ReservationUpdatePayload, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}`, { method: "PATCH", data: payload, session });

export const cancelReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}/cancel`, { method: "POST", session });

export const markReservationNoShow = (id: number, payload: ReservationNoShowPayload, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}/noshow`, { method: "POST", data: payload, session });

export const moveReservationRoom = (id: number, payload: ReservationRoomMovePayload, session?: SessionLike) =>
  apiFetch<ReservationRoomMoveResponse>(`/api/reservations/${id}/room-move`, { method: "POST", data: payload, session });

export const addReservationCharge = (id: number, payload: ReservationChargePayload, session?: SessionLike) =>
  apiFetch<ReservationBillingAdjustmentSummary>(`/api/reservations/${id}/charges`, {
    method: "POST",
    data: payload,
    session
  });

// B3.4: `guest` carries whatever check-in fields the receptionist just
// completed (birth place/country, marital status, occupation, etc.) so the
// backend applies them and validates in the same request/transaction.
export type CheckInPayload = {
  override_prohibido?: boolean;
  guest?: GuestUpdatePayload;
  // Only honored by the final check-in endpoint below, not partial
  // check-in -- see app/api/checkin.py (checkin_partial never catches
  // GuestProhibitedError).
  restriction_override?: RestrictionOverride | null;
};

export const checkInReservation = (id: number, payload: CheckInPayload = {}, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/checkin/${id}`, { method: "POST", data: payload, session });

// B3.1: writes PRE_CHECK_IN ("huésped ingresó al cuarto, falta confirmar").
export const partialCheckInReservation = (id: number, payload: CheckInPayload = {}, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/checkin/${id}/partial`, { method: "POST", data: payload, session });

export const checkOutReservation = (id: number, session?: SessionLike) =>
  apiFetch<Reservation>(`/api/checkin/checkout/${id}`, { method: "POST", session });

// B3.5: acompañantes -- the endpoint already dedups by document_number and
// validates capacity against max_occupancy, so a quick-add with just a name
// (+ optional document) is enough; no separate search step needed.
export type ReservationGuestCreatePayload = {
  first_name: string;
  last_name: string;
  document_type?: "DNI" | "PASSPORT" | "CEDULA";
  document_number?: string;
  nationality?: string;
  date_of_birth?: string;
};

export const addReservationGuests = (id: number, guests: ReservationGuestCreatePayload[], session?: SessionLike) =>
  apiFetch<Reservation>(`/api/reservations/${id}/guests`, { method: "POST", data: guests, session });

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

export type CompanyExtensionRequestPayload = {
  pending: boolean;
  note?: string | null;
  client_version: number;
};

export type ReservationExtensionPayload = {
  new_checkout_date: string;
  client_version: number;
  pricing_mode: "current_rate";
  payment_action: "immediate_payment" | "payment_link" | "company_account";
  immediate_payment?: PaymentRequest;
  payment_link?: PaymentLinkCreatePayload;
  notes?: string;
};

export type ReservationExtensionPreview = {
  reservation_id: number;
  current_checkout_date: string;
  new_checkout_date: string;
  client_version: number;
  extension_amount: number | string;
  currency_code: string;
};

export type ReservationExtensionResponse = {
  reservation: Reservation;
  extension_amount: number | string;
  transaction: ReservationTransactionSummary | null;
  payment_link: PaymentLink | null;
};

export const updateCompanyExtensionRequest = (
  id: number,
  payload: CompanyExtensionRequestPayload,
  session?: SessionLike
) => apiFetch<Reservation>(`/api/reservations/${id}/extension-request`, {
  method: "PUT",
  data: payload,
  session
});

export const extendReservationStay = (
  id: number,
  payload: ReservationExtensionPayload,
  session?: SessionLike
) => apiFetch<ReservationExtensionResponse>(`/api/reservations/${id}/extend`, {
  method: "POST",
  data: payload,
  session
});

export const previewReservationStayExtension = (
  id: number,
  newCheckoutDate: string,
  session?: SessionLike,
  signal?: AbortSignal
) => apiFetch<ReservationExtensionPreview>(
  `/api/reservations/${id}/extend-preview?new_checkout_date=${encodeURIComponent(newCheckoutDate)}`,
  { session, signal }
);

// ── B2: occupancy grid (planilla de ocupación) ──────────────────────────────

export type OccupancyGridRoom = {
  id: number;
  room_number: string;
  floor: number;
  category_id: number;
  category_name: string;
  status: string;
};

export type OccupancyGridReservation = {
  id: number;
  version: number;
  room_id: number | null;
  confirmation_code: string;
  check_in_date: string;
  check_out_date: string;
  status: ReservationStatus;
  guest_name: string;
  num_adults: number;
  num_children: number;
  operational_balance_due: number;
};

export type OccupancyGridBlock = {
  room_id: number;
  starts_at: string;
  ends_at: string | null;
  reason_code: string;
};

export type OccupancyGridResponse = {
  rooms: OccupancyGridRoom[];
  reservations: OccupancyGridReservation[];
  unassigned: OccupancyGridReservation[];
  blocks: OccupancyGridBlock[];
};

export const getOccupancyGrid = (
  params: { dateFrom: string; dateTo: string },
  session?: SessionLike,
  signal?: AbortSignal
) => {
  const query = new URLSearchParams({ date_from: params.dateFrom, date_to: params.dateTo });
  return apiFetch<OccupancyGridResponse>(`/api/reservations/occupancy-grid?${query.toString()}`, { session, signal });
};

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addReservationGuests,
  clearReservationManualReview,
  cancelReservation,
  checkInReservation,
  checkOutReservation,
  createManualOtaReservation,
  createReservation,
  extendReservationStay,
  getOccupancyGrid,
  getReservation,
  getReservationQuote,
  getReservationOperationsSummary,
  listReservations,
  listPendingReservationActions,
  partialCheckInReservation,
  resolveReservationExternal,
  updateReservation,
  updateCompanyExtensionRequest,
  type CheckInPayload,
  type ManualOtaReservationPayload,
  type OccupancyGridResponse,
  type ReservationActionResolvePayload,
  type ReservationExternalResolutionResponse,
  type ReservationGuestCreatePayload,
  type Reservation,
  type ReservationQuote,
  type ReservationQuoteParams,
  type ReservationFilters,
  type ReservationManualReviewResponse,
  type ReservationOperationsSummary,
  type ReservationPayload,
  type ReservationPendingAction,
  type ReservationStatus,
  type ReservationUpdatePayload,
  type CompanyExtensionRequestPayload,
  type ReservationExtensionPayload
} from "../api/reservations";
import { validateGuestForCheckin, type GuestCheckinValidation } from "../api/guests";
import type { SessionState } from "../state/session";
import { ApiError, hasValidSession } from "../api/client";
import { refreshReservationCreatedState, refreshReservationGuestState, refreshReservationRecordState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const reservationsKey = (hotelId: number | null, filters: ReservationFilters) => ["reservations", hotelId, filters];
const reservationKey = (hotelId: number | null, reservationId: number) => ["reservation", hotelId, reservationId];
const reservationOperationsKey = (hotelId: number | null, reservationId: number) => [
  "reservation-operations",
  hotelId,
  reservationId
];
const pendingReservationActionsKey = (hotelId: number | null, limit: number) => [
  "reservation-pending-actions",
  hotelId,
  limit
];
const occupancyGridKey = (hotelId: number | null, dateFrom: string, dateTo: string) => [
  "occupancy-grid",
  hotelId,
  dateFrom,
  dateTo
];

export function useReservations(filters: ReservationFilters) {
  const { session } = useSession();
  const searchFilterReady = filters.search === undefined || filters.search.trim().length >= 2;

  return useQuery<Reservation[]>({
    queryKey: reservationsKey(session.hotelId, filters),
    queryFn: ({ signal }) => listReservations(filters, session, signal),
    // A caller-provided search term shorter than 2 chars is not useful (and
    // noisy against the DB), so hold off until there's enough to match on.
    // Filters without a search term behave exactly as before.
    enabled: hasValidSession(session) && searchFilterReady,
    placeholderData: keepPreviousData,
    staleTime: 1000 * 15,
    retry: false
  });
}

export function useReservation(reservationId?: number) {
  const { session } = useSession();
  const queryKey = reservationId ? reservationKey(session.hotelId, reservationId) : ["reservation", "none"];

  return useQuery<Reservation>({
    queryKey,
    queryFn: ({ signal }) => getReservation(reservationId!, session, signal),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 1000 * 15,
    retry: false
  });
}

// B3.3/B3.4: drives whether the check-in UI shows the "complete missing
// data" form before the receptionist even attempts the check-in.
export function useValidateGuestCheckin(guestId?: number) {
  const { session } = useSession();
  return useQuery<GuestCheckinValidation>({
    queryKey: guestId ? ["guest-checkin-validation", session.hotelId, guestId] : ["guest-checkin-validation", "none"],
    queryFn: ({ signal }) => validateGuestForCheckin(guestId!, session, signal),
    enabled: Boolean(guestId) && hasValidSession(session),
    staleTime: 0,
    // Do not silently retry a prerequisite that gates check-in. Show the
    // error and let the operator retry explicitly.
    retry: false
  });
}

export function useReservationQuote(params: ReservationQuoteParams | null) {
  const { session } = useSession();
  return useQuery<ReservationQuote>({
    queryKey: [
      "reservation-quote",
      session.hotelId ?? null,
      params?.category_id ?? null,
      params?.check_in_date ?? null,
      params?.check_out_date ?? null,
      params?.pricing_payment_method ?? null,
      params?.occupancy ?? null,
      params?.guest_id ?? null,
      params?.company_id ?? null
    ],
    queryFn: ({ signal }) => getReservationQuote(params!, session, signal),
    enabled: Boolean(params) && hasValidSession(session),
    staleTime: 30 * 1000,
    gcTime: 1000 * 60 * 10,
    // price-quote 4xx (no active rate plan, invalid date range, etc.) is a
    // deterministic business rejection -- retrying the identical request
    // just delays the actionable error behind an extra round trip.
    retry: (failureCount, error) => (error instanceof ApiError && error.status < 500 ? false : failureCount < 1)
  });
}

export function useReservationOperationsSummary(reservationId?: number) {
  const { session } = useSession();
  const queryKey = reservationId
    ? reservationOperationsKey(session.hotelId, reservationId)
    : ["reservation-operations", "none"];

  return useQuery<ReservationOperationsSummary>({
    queryKey,
    queryFn: ({ signal }) => getReservationOperationsSummary(reservationId!, session, signal),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 1000 * 15,
    retry: false
  });
}

export function usePendingReservationActions(limit = 100) {
  const { session } = useSession();

  return useQuery<ReservationPendingAction[]>({
    queryKey: pendingReservationActionsKey(session.hotelId, limit),
    queryFn: ({ signal }) => listPendingReservationActions(limit, session, signal),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15,
    retry: false
  });
}

export function useReservationMutations(filters?: ReservationFilters) {
  void filters;
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidateReservationRecord = (
    reservationId: number,
    options: { includePaymentSummary?: boolean; includePaymentLinks?: boolean } = {}
  ) => refreshReservationRecordState(queryClient, session.hotelId, reservationId, options);
  // Creating a reservation changes reservation-facing views, but recording a
  // required deposit amount does not create a cash movement. Keep active cash
  // sessions and room-movement groups fresh through their own mutations
  // instead of refetching them for each new booking.
  const invalidateCreatedReservation = () =>
    refreshReservationCreatedState(queryClient, session.hotelId);

  // Check-in/check-out/companion changes are read by the drawer's own
  // single-reservation query, not just the list, and they write guest data
  // too -- refresh both domains so the status/guest data the receptionist
  // just saved shows up immediately.
  const invalidateReservationDetail = (reservationId: number) => {
    return refreshReservationGuestState(queryClient, session.hotelId, reservationId);
  };

  // Double-click / double-tap on "confirm" fires two submits in the same JS
  // turn, before React re-renders the button as disabled. Without a real
  // server-side idempotency key on reservation creation, that used to be able
  // to book two separate rooms for the same guest/dates from one click.
  // useGuardedMutation closes the client-side race the same way it already
  // does for payments; check-in/check-out get the same guard since firing
  // them twice would double-apply their side effects.
  const createMutation = useGuardedMutation({
    mutationFn: (payload: ReservationPayload) => createReservation(payload, session),
    onSuccess: async () => invalidateCreatedReservation()
  });

  // B4: "Cargar reserva de OTA" -- upsert by (channel, external_id), see
  // createManualOtaReservation.
  const createManualOtaMutation = useGuardedMutation({
    mutationFn: (payload: ManualOtaReservationPayload) => createManualOtaReservation(payload, session),
    onSuccess: async () => invalidateCreatedReservation()
  });

  const updateMutation = useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReservationUpdatePayload }) =>
      updateReservation(id, payload, session),
    onSuccess: async (_, variables) => invalidateReservationRecord(variables.id, { includePaymentSummary: true })
  });

  const companyExtensionRequestMutation = useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CompanyExtensionRequestPayload }) =>
      updateCompanyExtensionRequest(id, payload, session),
    onSuccess: async (_, variables) => invalidateReservationDetail(variables.id)
  });

  const companyAccountExtensionMutation = useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReservationExtensionPayload }) =>
      extendReservationStay(id, payload, session),
    // Extending a deferred company stay updates its dates and reservation
    // total only. It does not create a payment or cash movement.
    onSuccess: async (_, variables) => refreshReservationRecordState(queryClient, session.hotelId, variables.id)
  });

  const cancelMutation = useGuardedMutation({
    mutationFn: (id: number) => cancelReservation(id, session),
    // Cancellation changes the reservation projection and cancels its pending
    // payment links, but it does not create a cash movement.
    onSuccess: async (_, reservationId) => invalidateReservationRecord(reservationId, {
      includePaymentSummary: true,
      includePaymentLinks: true
    })
  });

  type CheckInParams = number | ({ id: number } & CheckInPayload);
  const normalizeCheckInParams = (params: CheckInParams) =>
    typeof params === "number"
      ? { id: params, guest: undefined, override_prohibido: undefined, restriction_override: undefined }
      : params;

  const checkInMutation = useGuardedMutation({
    mutationFn: (params: CheckInParams) => {
      const { id, guest, override_prohibido, restriction_override } = normalizeCheckInParams(params);
      return checkInReservation(id, { guest, override_prohibido, restriction_override }, session);
    },
    onSuccess: async (_, params) => invalidateReservationDetail(normalizeCheckInParams(params).id)
  });

  // B3.1: partial check-in (PRE_CHECK_IN) -- same guest-capture payload shape
  // as the final check-in, different target status. restriction_override is
  // accepted by the shared CheckInRequest schema but never acted on here --
  // see app/api/checkin.py (checkin_partial never catches GuestProhibitedError).
  const partialCheckInMutation = useGuardedMutation({
    mutationFn: (params: CheckInParams) => {
      const { id, guest, override_prohibido } = normalizeCheckInParams(params);
      return partialCheckInReservation(id, { guest, override_prohibido }, session);
    },
    onSuccess: async (_, params) => invalidateReservationDetail(normalizeCheckInParams(params).id)
  });

  const checkOutMutation = useGuardedMutation({
    mutationFn: (id: number) => checkOutReservation(id, session),
    onSuccess: async (_, id) => invalidateReservationDetail(id)
  });

  // B3.5: acompañantes -- zero new backend, the endpoint already dedups by
  // document and validates capacity.
  const addGuestsMutation = useGuardedMutation({
    mutationFn: ({ id, guests }: { id: number; guests: ReservationGuestCreatePayload[] }) =>
      addReservationGuests(id, guests, session),
    onSuccess: async (_, { id }) => invalidateReservationDetail(id)
  });

  return {
    createMutation,
    createManualOtaMutation,
    updateMutation,
    companyExtensionRequestMutation,
    companyAccountExtensionMutation,
    cancelMutation,
    checkInMutation,
    partialCheckInMutation,
    checkOutMutation,
    addGuestsMutation
  };
}

export function useReservationActionMutations(filters?: ReservationFilters) {
  void filters;
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidateReservationRecord = (
    reservationId: number,
    options: { includePaymentSummary?: boolean; includePaymentLinks?: boolean } = {}
  ) => refreshReservationRecordState(queryClient, session.hotelId, reservationId, options);

  const resolveExternalMutation = useGuardedMutation<
    ReservationExternalResolutionResponse,
    unknown,
    { reservationId: number; payload: ReservationActionResolvePayload }
  >({
    mutationFn: ({ reservationId, payload }) => resolveReservationExternal(reservationId, payload, session),
    onSuccess: async (_, variables) => invalidateReservationRecord(variables.reservationId, {
      includePaymentSummary: true
    })
  });

  const clearManualReviewMutation = useGuardedMutation<
    ReservationManualReviewResponse,
    unknown,
    { reservationId: number; payload: ReservationActionResolvePayload }
  >({
    mutationFn: ({ reservationId, payload }) => clearReservationManualReview(reservationId, payload, session),
    onSuccess: async (_, variables) => invalidateReservationRecord(variables.reservationId)
  });

  return {
    resolveExternalMutation,
    clearManualReviewMutation
  };
}

// B2: occupancy grid (planilla). A shared query-options builder so the page
// can both `useQuery` the current window and `prefetchQuery` the adjacent
// ones with the exact same key/fn -- no separate prefetch plumbing needed.
function occupancyGridQueryOptions(session: SessionState, dateFrom: string, dateTo: string) {
  return {
    queryKey: occupancyGridKey(session.hotelId, dateFrom, dateTo),
    queryFn: ({ signal }: { signal: AbortSignal }) => getOccupancyGrid({ dateFrom, dateTo }, session, signal),
    enabled: hasValidSession(session),
    staleTime: 30_000,
    retry: false
  };
}

export function useOccupancyGrid(dateFrom: string, dateTo: string, enabled = true) {
  const { session } = useSession();
  return useQuery<OccupancyGridResponse>({
    ...occupancyGridQueryOptions(session, dateFrom, dateTo),
    enabled: enabled && hasValidSession(session)
  });
}

export function usePrefetchOccupancyGrid() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  return (dateFrom: string, dateTo: string) => {
    if (!hasValidSession(session)) return;
    queryClient.prefetchQuery(occupancyGridQueryOptions(session, dateFrom, dateTo));
  };
}

export const reservationStatusLabel = (status: ReservationStatus): string => {
  switch (status) {
    case "pending":
      return "Pendiente";
    case "deposit_paid":
      return "Seña";
    case "fully_paid":
      return "Pago completo";
    case "pre_check_in":
      return "Pre check-in";
    case "checked_in":
      return "Check-in";
    case "checked_out":
      return "Check-out";
    case "cancelled":
      return "Cancelada";
    default:
      return status;
  }
};

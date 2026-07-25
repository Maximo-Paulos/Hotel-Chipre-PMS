import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  clearReservationManualReview,
  cancelReservation,
  checkInReservation,
  checkOutReservation,
  createReservation,
  getOccupancyGrid,
  getReservation,
  getReservationQuote,
  getReservationOperationsSummary,
  listReservations,
  listPendingReservationActions,
  resolveReservationExternal,
  updateReservation,
  type OccupancyGridResponse,
  type ReservationActionResolvePayload,
  type ReservationExternalResolutionResponse,
  type Reservation,
  type ReservationQuote,
  type ReservationQuoteParams,
  type ReservationFilters,
  type ReservationManualReviewResponse,
  type ReservationOperationsSummary,
  type ReservationPayload,
  type ReservationPendingAction,
  type ReservationStatus,
  type ReservationUpdatePayload
} from "../api/reservations";
import type { SessionState } from "../state/session";
import { hasValidSession } from "../api/client";
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

  return useQuery<Reservation[]>({
    queryKey: reservationsKey(session.hotelId, filters),
    queryFn: () => listReservations(filters, session),
    // A caller-provided search term shorter than 2 chars is not useful (and
    // noisy against the DB), so hold off until there's enough to match on.
    // Filters without a search term behave exactly as before.
    enabled: hasValidSession(session) && (!filters.search || filters.search.trim().length >= 2),
    placeholderData: keepPreviousData,
    staleTime: 1000 * 15
  });
}

export function useReservation(reservationId?: number) {
  const { session } = useSession();
  const queryKey = reservationId ? reservationKey(session.hotelId, reservationId) : ["reservation", "none"];

  return useQuery<Reservation>({
    queryKey,
    queryFn: () => getReservation(reservationId!, session),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 1000 * 15
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
      params?.occupancy ?? null
    ],
    queryFn: () => getReservationQuote(params!, session),
    enabled: Boolean(params) && hasValidSession(session),
    staleTime: 0,
    gcTime: 1000 * 60 * 10,
    retry: 1
  });
}

export function useReservationOperationsSummary(reservationId?: number) {
  const { session } = useSession();
  const queryKey = reservationId
    ? reservationOperationsKey(session.hotelId, reservationId)
    : ["reservation-operations", "none"];

  return useQuery<ReservationOperationsSummary>({
    queryKey,
    queryFn: () => getReservationOperationsSummary(reservationId!, session),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 1000 * 15
  });
}

export function usePendingReservationActions(limit = 100) {
  const { session } = useSession();

  return useQuery<ReservationPendingAction[]>({
    queryKey: pendingReservationActionsKey(session.hotelId, limit),
    queryFn: () => listPendingReservationActions(limit, session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15
  });
}

export function useReservationMutations(filters?: ReservationFilters) {
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: filters ? reservationsKey(session.hotelId, filters) : ["reservations", session.hotelId]
    });

  // Double-click / double-tap on "confirm" fires two submits in the same JS
  // turn, before React re-renders the button as disabled. Without a real
  // server-side idempotency key on reservation creation, that used to be able
  // to book two separate rooms for the same guest/dates from one click.
  // useGuardedMutation closes the client-side race the same way it already
  // does for payments; check-in/check-out get the same guard since firing
  // them twice would double-apply their side effects.
  const createMutation = useGuardedMutation({
    mutationFn: (payload: ReservationPayload) => createReservation(payload, session),
    onSuccess: invalidate
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReservationUpdatePayload }) =>
      updateReservation(id, payload, session),
    onSuccess: invalidate
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) => cancelReservation(id, session),
    onSuccess: invalidate
  });

  const checkInMutation = useGuardedMutation({
    mutationFn: (id: number) => checkInReservation(id, session),
    onSuccess: invalidate
  });

  const checkOutMutation = useGuardedMutation({
    mutationFn: (id: number) => checkOutReservation(id, session),
    onSuccess: invalidate
  });

  return {
    createMutation,
    updateMutation,
    cancelMutation,
    checkInMutation,
    checkOutMutation
  };
}

export function useReservationActionMutations(filters?: ReservationFilters) {
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidateAll = (reservationId?: number) => {
    queryClient.invalidateQueries({
      queryKey: filters ? reservationsKey(session.hotelId, filters) : ["reservations", session.hotelId]
    });
    queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["payment-summary", session.hotelId] });
    queryClient.invalidateQueries({ queryKey: ["reservation-pending-actions", session.hotelId] });
    if (reservationId) {
      queryClient.invalidateQueries({ queryKey: reservationOperationsKey(session.hotelId, reservationId) });
      queryClient.invalidateQueries({ queryKey: reservationKey(session.hotelId, reservationId) });
      queryClient.invalidateQueries({ queryKey: ["payment-summary", session.hotelId, reservationId] });
    }
  };

  const resolveExternalMutation = useMutation<
    ReservationExternalResolutionResponse,
    unknown,
    { reservationId: number; payload: ReservationActionResolvePayload }
  >({
    mutationFn: ({ reservationId, payload }) => resolveReservationExternal(reservationId, payload, session),
    onSuccess: (_, variables) => invalidateAll(variables.reservationId)
  });

  const clearManualReviewMutation = useMutation<
    ReservationManualReviewResponse,
    unknown,
    { reservationId: number; payload: ReservationActionResolvePayload }
  >({
    mutationFn: ({ reservationId, payload }) => clearReservationManualReview(reservationId, payload, session),
    onSuccess: (_, variables) => invalidateAll(variables.reservationId)
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
    queryFn: () => getOccupancyGrid({ dateFrom, dateTo }, session),
    enabled: hasValidSession(session),
    staleTime: 30_000
  };
}

export function useOccupancyGrid(dateFrom: string, dateTo: string) {
  const { session } = useSession();
  return useQuery<OccupancyGridResponse>(occupancyGridQueryOptions(session, dateFrom, dateTo));
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

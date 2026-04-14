import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  clearReservationManualReview,
  cancelReservation,
  checkInReservation,
  checkOutReservation,
  createReservation,
  getReservation,
  getReservationOperationsSummary,
  listReservations,
  listPendingReservationActions,
  resolveReservationExternal,
  updateReservation,
  type ReservationActionResolvePayload,
  type ReservationExternalResolutionResponse,
  type Reservation,
  type ReservationFilters,
  type ReservationManualReviewResponse,
  type ReservationOperationsSummary,
  type ReservationPayload,
  type ReservationPendingAction,
  type ReservationStatus,
  type ReservationUpdatePayload
} from "../api/reservations";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

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

export function useReservations(filters: ReservationFilters) {
  const { session } = useSession();

  return useQuery<Reservation[]>({
    queryKey: reservationsKey(session.hotelId, filters),
    queryFn: () => listReservations(filters, session),
    enabled: hasValidSession(session),
    keepPreviousData: true,
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

  const createMutation = useMutation({
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

  const checkInMutation = useMutation({
    mutationFn: (id: number) => checkInReservation(id, session),
    onSuccess: invalidate
  });

  const checkOutMutation = useMutation({
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

export const reservationStatusLabel = (status: ReservationStatus): string => {
  switch (status) {
    case "pending":
      return "Pendiente";
    case "deposit_paid":
      return "Seña";
    case "fully_paid":
      return "Pago completo";
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

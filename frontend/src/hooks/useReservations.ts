import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelReservation,
  checkInReservation,
  checkOutReservation,
  createReservation,
  listReservations,
  updateReservation,
  type Reservation,
  type ReservationFilters,
  type ReservationPayload,
  type ReservationStatus,
  type ReservationUpdatePayload
} from "../api/reservations";
import { useSession } from "../state/session";

const reservationsKey = (hotelId: number, filters: ReservationFilters) => ["reservations", hotelId, filters];

export function useReservations(filters: ReservationFilters) {
  const { session } = useSession();

  return useQuery<Reservation[]>({
    queryKey: reservationsKey(session.hotelId, filters),
    queryFn: () => listReservations(filters, session),
    keepPreviousData: true,
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

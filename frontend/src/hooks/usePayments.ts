import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getPaymentSummary, makePayment, type PaymentRequest, type PaymentSummary } from "../api/payments";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const summaryKey = (hotelId: number | null, reservationId: number) => ["payment-summary", hotelId, reservationId];

export function usePaymentSummary(reservationId?: number) {
  const { session } = useSession();
  const queryKey = reservationId ? summaryKey(session.hotelId, reservationId) : ["payment-summary", "none"];

  return useQuery<PaymentSummary>({
    queryKey,
    queryFn: () => getPaymentSummary(reservationId!, session),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 1000 * 30
  });
}

export function usePaymentMutation(reservationId?: number) {
  const { session } = useSession();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: PaymentRequest) => makePayment(payload, session),
    onSuccess: () => {
      if (reservationId) {
        queryClient.invalidateQueries({ queryKey: summaryKey(session.hotelId, reservationId) });
      }
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
    }
  });
}

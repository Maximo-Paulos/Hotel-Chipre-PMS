import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { getPaymentSummary, makePayment, type PaymentRequest, type PaymentSummary } from "../api/payments";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

import { invalidateCashRegisterQueries } from "./useCashRegister";

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
  // A rapid double-click fires two native click handlers in the same JS turn,
  // before React re-renders the button as disabled -- mutation.isPending only
  // flips on the next render, too late to stop the second call. makePayment()
  // also mints a brand-new Idempotency-Key on every invocation (api/payments.ts),
  // so the backend's own idempotency dedup cannot catch two distinct clicks
  // either. This ref is set/read synchronously, so it closes the race for
  // every caller (deposit, partial, full, refund) that shares this hook.
  const submittingRef = useRef(false);

  const mutation = useMutation({
    mutationFn: (payload: PaymentRequest) => makePayment(payload, session),
    onSuccess: () => {
      if (reservationId) {
        queryClient.invalidateQueries({ queryKey: summaryKey(session.hotelId, reservationId) });
      }
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
      invalidateCashRegisterQueries(queryClient, session.hotelId);
    },
    onSettled: () => {
      submittingRef.current = false;
    }
  });

  const guardedMutate: typeof mutation.mutate = (variables, options) => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    mutation.mutate(variables, options);
  };

  return { ...mutation, mutate: guardedMutate };
}

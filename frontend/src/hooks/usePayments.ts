import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import {
  getPaymentSummary,
  makePayment,
  newPaymentIdempotencyKey,
  type PaymentRequest,
  type PaymentSummary
} from "../api/payments";
import { hasValidSession } from "../api/client";
import { invalidateQueriesInBackground, refreshPaymentState } from "../api/queryInvalidation";
import { queryKeys } from "../api/queryKeys";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const summaryKey = (hotelId: number | null, reservationId: number) => queryKeys.paymentSummary(hotelId, reservationId);

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
  const intentKeysRef = useRef(new Map<string, string>());

  return useGuardedMutation({
    mutationFn: (payload: PaymentRequest) => {
      const fingerprint = JSON.stringify(payload);
      let idempotencyKey = intentKeysRef.current.get(fingerprint);
      if (!idempotencyKey) {
        idempotencyKey = newPaymentIdempotencyKey(payload.reservation_id);
        // Bound this in-memory retry cache. Successful intents are removed in
        // onSuccess; failed network attempts remain replayable until evicted.
        if (intentKeysRef.current.size >= 20) {
          const oldest = intentKeysRef.current.keys().next().value;
          if (oldest) intentKeysRef.current.delete(oldest);
        }
        intentKeysRef.current.set(fingerprint, idempotencyKey);
      }
      return makePayment(payload, session, idempotencyKey);
    },
    // The payment endpoint has committed before returning. Keep the saved
    // payment visible and reconcile affected views in the background.
    onSuccess: (_data, payload) => {
      void refreshPaymentState(queryClient, session.hotelId, reservationId).catch(() => undefined);
      if (reservationId) {
        invalidateQueriesInBackground(queryClient, {
          queryKey: ["company-night-charges", session.hotelId, reservationId]
        });
      }
      intentKeysRef.current.delete(JSON.stringify(payload));
    }
  });
}

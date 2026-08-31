import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createPaymentSurcharge,
  deactivatePaymentSurcharge,
  listPaymentSurcharges,
  type PaymentSurcharge,
  type PaymentSurchargeCreatePayload
} from "../api/paymentSurcharges";
import { hasValidSession } from "../api/client";
import { refreshAfterMutation } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const surchargesKey = (hotelId: number | null) => ["payment-surcharges", hotelId];

export function usePaymentSurcharges() {
  const { session } = useSession();
  return useQuery<PaymentSurcharge[]>({
    queryKey: surchargesKey(session.hotelId),
    queryFn: () => listPaymentSurcharges(session),
    enabled: hasValidSession(session),
    staleTime: 60 * 1000
  });
}

export function usePaymentSurchargeMutations() {
  const qc = useQueryClient();
  const { session } = useSession();
  const invalidate = () => refreshAfterMutation(qc, session.hotelId, ["settings", "payments"]);

  const createMutation = useGuardedMutation({
    mutationFn: (payload: PaymentSurchargeCreatePayload) => createPaymentSurcharge(payload, session),
    onSuccess: async () => invalidate()
  });
  const deactivateMutation = useGuardedMutation({
    mutationFn: (id: number) => deactivatePaymentSurcharge(id, session),
    onSuccess: async () => invalidate()
  });

  return { createMutation, deactivateMutation };
}

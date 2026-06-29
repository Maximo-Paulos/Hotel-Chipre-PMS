import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createPaymentSurcharge,
  deactivatePaymentSurcharge,
  listPaymentSurcharges,
  type PaymentSurcharge,
  type PaymentSurchargeCreatePayload
} from "../api/paymentSurcharges";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

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
  const invalidate = () => qc.invalidateQueries({ queryKey: surchargesKey(session.hotelId) });

  const createMutation = useMutation({
    mutationFn: (payload: PaymentSurchargeCreatePayload) => createPaymentSurcharge(payload, session),
    onSuccess: invalidate
  });
  const deactivateMutation = useMutation({
    mutationFn: (id: number) => deactivatePaymentSurcharge(id, session),
    onSuccess: invalidate
  });

  return { createMutation, deactivateMutation };
}

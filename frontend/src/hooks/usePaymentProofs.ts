import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  approvePaymentProof,
  listPaymentProofs,
  rejectPaymentProof,
  submitPaymentProof,
  type PaymentProof,
  type PaymentProofCreatePayload
} from "../api/paymentProofs";
import { hasValidSession } from "../api/client";
import { refreshPaymentState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const proofsKey = (hotelId: number | null, reservationId?: number) => ["payment-proofs", hotelId, reservationId];

export function usePaymentProofs(reservationId?: number) {
  const { session } = useSession();
  return useQuery<PaymentProof[]>({
    queryKey: proofsKey(session.hotelId, reservationId),
    queryFn: () => listPaymentProofs(reservationId!, session),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 10 * 1000
  });
}

export function usePaymentProofMutations(reservationId?: number) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const invalidate = () => refreshPaymentState(queryClient, session.hotelId, reservationId);

  const submitMutation = useGuardedMutation({
    mutationFn: (payload: PaymentProofCreatePayload) => submitPaymentProof(payload, session),
    onSuccess: async () => invalidate()
  });
  const approveMutation = useGuardedMutation({
    mutationFn: (proofId: number) => approvePaymentProof(proofId, session),
    onSuccess: async () => invalidate()
  });
  const rejectMutation = useGuardedMutation({
    mutationFn: ({ proofId, reason }: { proofId: number; reason: string }) => rejectPaymentProof(proofId, reason, session),
    onSuccess: async () => invalidate()
  });

  return { submitMutation, approveMutation, rejectMutation };
}

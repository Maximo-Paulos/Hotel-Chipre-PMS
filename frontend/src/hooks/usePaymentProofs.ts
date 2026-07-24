import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  approvePaymentProof,
  listPaymentProofs,
  rejectPaymentProof,
  submitPaymentProof,
  type PaymentProof,
  type PaymentProofCreatePayload
} from "../api/paymentProofs";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

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
  const invalidate = () => {
    if (reservationId) queryClient.invalidateQueries({ queryKey: proofsKey(session.hotelId, reservationId) });
    queryClient.invalidateQueries({ queryKey: ["payment-summary", session.hotelId, reservationId] });
    queryClient.invalidateQueries({ queryKey: ["reservations", session.hotelId] });
  };

  const submitMutation = useMutation({
    mutationFn: (payload: PaymentProofCreatePayload) => submitPaymentProof(payload, session),
    onSuccess: invalidate
  });
  const approveMutation = useMutation({
    mutationFn: (proofId: number) => approvePaymentProof(proofId, session),
    onSuccess: invalidate
  });
  const rejectMutation = useMutation({
    mutationFn: ({ proofId, reason }: { proofId: number; reason: string }) => rejectPaymentProof(proofId, reason, session),
    onSuccess: invalidate
  });

  return { submitMutation, approveMutation, rejectMutation };
}

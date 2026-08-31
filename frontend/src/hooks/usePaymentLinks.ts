import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createPaymentLink,
  cancelPaymentLink,
  listPaymentLinks,
  type PaymentLink,
  type PaymentLinkCreatePayload
} from "../api/paymentLinks";
import { hasValidSession } from "../api/client";
import { refreshPaymentState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const linksKey = (hotelId: number | null, reservationId?: number) => ["payment-links", hotelId, reservationId];

export function usePaymentLinks(reservationId?: number) {
  const { session } = useSession();
  return useQuery<PaymentLink[]>({
    queryKey: linksKey(session.hotelId, reservationId),
    queryFn: () => listPaymentLinks(reservationId!, session),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 15 * 1000
  });
}

export function usePaymentLinkCreate(reservationId?: number) {
  const qc = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (payload: PaymentLinkCreatePayload) => createPaymentLink(payload, session),
    onSuccess: async (created: PaymentLink) => {
      const key = linksKey(session.hotelId, reservationId);
      // The POST response is already the persisted source of truth. Publish it
      // immediately so a successful local-only request is visible even when
      // the edit form's initial list request is still in flight; the refetch
      // below reconciles the cache with the canonical server ordering.
      qc.setQueryData<PaymentLink[]>(key, (current) => [
        created,
        ...(current ?? []).filter((link) => link.id !== created.id)
      ]);
      await refreshPaymentState(qc, session.hotelId, reservationId);
    }
  });
}

export function usePaymentLinkCancel(reservationId?: number) {
  const qc = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (linkId: number) => cancelPaymentLink(linkId, "operator_request", session),
    onSuccess: async () => refreshPaymentState(qc, session.hotelId, reservationId)
  });
}

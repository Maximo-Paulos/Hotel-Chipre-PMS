import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createPaymentLink,
  listPaymentLinks,
  type PaymentLink,
  type PaymentLinkCreatePayload
} from "../api/paymentLinks";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

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
  return useMutation({
    mutationFn: (payload: PaymentLinkCreatePayload) => createPaymentLink(payload, session),
    onSuccess: () => qc.invalidateQueries({ queryKey: linksKey(session.hotelId, reservationId) })
  });
}

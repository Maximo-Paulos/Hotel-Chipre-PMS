import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createMercadoPagoPaymentLinkTest,
  listPaymentLinkTests,
  refreshPaymentLinkTest,
  type PaymentLinkTestCreatePayload,
} from "../api/paymentLinkTests";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const paymentLinkTestsKey = (hotelId: number | null) => ["payment-link-tests", hotelId, "mercadopago"];

export function useMercadoPagoTests() {
  const { session } = useSession();
  return useQuery({
    queryKey: paymentLinkTestsKey(session.hotelId),
    queryFn: () => listPaymentLinkTests(session),
    enabled: hasValidSession(session),
    refetchInterval: 30_000,
  });
}

export function useMercadoPagoTestMutations() {
  const { session } = useSession();
  const queryClient = useQueryClient();

  const invalidate = () => queryClient.invalidateQueries({ queryKey: paymentLinkTestsKey(session.hotelId) });

  const createMutation = useMutation({
    mutationFn: (payload: PaymentLinkTestCreatePayload) => createMercadoPagoPaymentLinkTest(payload, session),
    onSuccess: invalidate,
  });

  const refreshMutation = useMutation({
    mutationFn: (testId: number) => refreshPaymentLinkTest(testId, session),
    onSuccess: invalidate,
  });

  return { createMutation, refreshMutation };
}

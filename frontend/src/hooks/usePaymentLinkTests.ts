import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createMercadoPagoPaymentLinkTest,
  listPaymentLinkTests,
  refreshPaymentLinkTest,
  type PaymentLinkTestCreatePayload,
} from "../api/paymentLinkTests";
import { hasValidSession } from "../api/client";
import { refreshAfterMutation } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

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

  const invalidate = () => refreshAfterMutation(queryClient, session.hotelId, ["payments", "settings"]);

  const createMutation = useGuardedMutation({
    mutationFn: (payload: PaymentLinkTestCreatePayload) => createMercadoPagoPaymentLinkTest(payload, session),
    onSuccess: async () => invalidate(),
  });

  const refreshMutation = useGuardedMutation({
    mutationFn: (testId: number) => refreshPaymentLinkTest(testId, session),
    onSuccess: async () => invalidate(),
  });

  return { createMutation, refreshMutation };
}

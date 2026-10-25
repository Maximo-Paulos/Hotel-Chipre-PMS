import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createPaymentSurcharge,
  deactivatePaymentSurcharge,
  listPaymentSurcharges,
  quotePaymentSurcharge,
  type PaymentSurcharge,
  type PaymentSurchargeCreatePayload,
  type PaymentSurchargeQuote,
  type PaymentSurchargeQuoteRequest
} from "../api/paymentSurcharges";
import { hasValidSession } from "../api/client";
import { refreshAfterMutation } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const surchargesKey = (hotelId: number | null) => ["payment-surcharges", hotelId];

export function usePaymentSurcharges(options?: { enabled?: boolean }) {
  const { session } = useSession();
  return useQuery<PaymentSurcharge[]>({
    queryKey: surchargesKey(session.hotelId),
    queryFn: () => listPaymentSurcharges(session),
    enabled: hasValidSession(session) && (options?.enabled ?? true),
    staleTime: 60 * 1000
  });
}

export function usePaymentSurchargeQuote(
  input: PaymentSurchargeQuoteRequest | null,
  options?: { enabled?: boolean }
) {
  const { session } = useSession();
  const normalizedInput = input
    ? { ...input, currency_code: input.currency_code.trim().toUpperCase() }
    : null;
  const baseAmountKey = normalizedInput?.base_amount ?? "balance";
  return useQuery<PaymentSurchargeQuote>({
    queryKey: [
      "payment-surcharge-quote",
      session.hotelId,
      normalizedInput?.reservation_id ?? null,
      normalizedInput?.payment_method ?? null,
      normalizedInput?.currency_code ?? null,
      baseAmountKey
    ],
    queryFn: () => {
      if (!normalizedInput) throw new Error("Falta la reserva para cotizar el cobro.");
      return quotePaymentSurcharge(normalizedInput, session);
    },
    enabled: hasValidSession(session) && Boolean(normalizedInput) && (options?.enabled ?? true),
    staleTime: 15_000,
    retry: false
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

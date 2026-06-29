import { useQuery } from "@tanstack/react-query";

import { listPaymentSurcharges, type PaymentSurcharge } from "../api/paymentSurcharges";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

export function usePaymentSurcharges() {
  const { session } = useSession();
  return useQuery<PaymentSurcharge[]>({
    queryKey: ["payment-surcharges", session.hotelId],
    queryFn: () => listPaymentSurcharges(session),
    enabled: hasValidSession(session),
    staleTime: 60 * 1000
  });
}

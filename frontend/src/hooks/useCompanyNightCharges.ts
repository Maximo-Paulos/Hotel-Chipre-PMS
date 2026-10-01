import { useQuery, useQueryClient } from "@tanstack/react-query";

import { createCompanyNightCharges, getCompanyNightCharges } from "../api/companyNightCharges";
import { hasValidSession } from "../api/client";
import { refreshPaymentState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const chargesKey = (hotelId: number | null, reservationId: number) => [
  "company-night-charges",
  hotelId,
  reservationId
] as const;

export function useCompanyNightCharges(reservationId?: number, isCompanyReservation = false) {
  const { session } = useSession();
  return useQuery({
    queryKey: reservationId ? chargesKey(session.hotelId, reservationId) : ["company-night-charges", "none"],
    queryFn: () => getCompanyNightCharges(reservationId!, session),
    enabled: Boolean(reservationId && isCompanyReservation) && hasValidSession(session),
    staleTime: 15 * 1000
  });
}

export function useCreateCompanyNightCharges(reservationId?: number) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  return useGuardedMutation({
    mutationFn: (stayDates: string[]) => createCompanyNightCharges(reservationId!, stayDates, session),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: chargesKey(session.hotelId, reservationId!) }),
        refreshPaymentState(queryClient, session.hotelId, reservationId)
      ]);
    }
  });
}

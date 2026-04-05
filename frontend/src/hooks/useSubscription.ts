import { useQuery } from "@tanstack/react-query";
import { getSubscriptionStatus, listSubscriptionPlans } from "../api/subscription";
import { useSession } from "../state/session";

export function useSubscriptionStatus() {
  const { session } = useSession();
  return useQuery({ queryKey: ["subscription", session.hotelId], queryFn: () => getSubscriptionStatus(session) });
}

export function useSubscriptionPlans() {
  const { session } = useSession();
  return useQuery({ queryKey: ["subscription-plans"], queryFn: () => listSubscriptionPlans(session) });
}

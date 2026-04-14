import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import { getOnboardingStatus, type OnboardingStatus } from "../api/onboarding";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

export const onboardingStatusKey = (hotelId: number | null, userId: string | null) => [
  "onboarding-status",
  hotelId,
  userId
];

export function useOnboardingStatus(
  options?: Omit<UseQueryOptions<OnboardingStatus>, "queryKey" | "queryFn">
) {
  const { session } = useSession();

  return useQuery<OnboardingStatus>({
    queryKey: onboardingStatusKey(session.hotelId, session.userId),
    queryFn: () => getOnboardingStatus(session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 30,
    ...options
  });
}

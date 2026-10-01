import { useQuery } from "@tanstack/react-query";

import { getAuthProviders } from "../api/auth";

export const authProvidersQueryKey = ["auth-providers"] as const;

export function useAuthProviders() {
  return useQuery({
    queryKey: authProvidersQueryKey,
    queryFn: getAuthProviders,
    staleTime: 30_000,
    retry: false
  });
}

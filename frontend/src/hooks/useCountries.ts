import { useQuery } from "@tanstack/react-query";

import { listCountries } from "../api/timezones";

export function useCountries() {
  return useQuery({
    queryKey: ["countries"],
    queryFn: listCountries,
    staleTime: Infinity,
    gcTime: Infinity,
    placeholderData: () => []
  });
}

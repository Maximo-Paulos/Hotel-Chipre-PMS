import { useQuery } from "@tanstack/react-query";

import { listTimezones } from "../api/timezones";

export function useTimezones() {
  return useQuery({
    queryKey: ["timezones"],
    queryFn: listTimezones,
    staleTime: Infinity,
    gcTime: Infinity,
    placeholderData: () => []
  });
}

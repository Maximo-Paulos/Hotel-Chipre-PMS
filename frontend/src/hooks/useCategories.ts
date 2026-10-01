import { useQuery } from "@tanstack/react-query";

import { listCategories } from "../api/categories";
import { hasValidSession } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useSession } from "../state/session";

export function useCategories() {
  const { session } = useSession();
  return useQuery({
    queryKey: queryKeys.roomCategories(session.hotelId),
    queryFn: () => listCategories(session),
    enabled: hasValidSession(session),
    staleTime: 5 * 60 * 1000
  });
}

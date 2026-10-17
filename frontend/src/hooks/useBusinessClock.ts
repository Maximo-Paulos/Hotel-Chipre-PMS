import { useQuery } from "@tanstack/react-query";

import { getBusinessClock, type BusinessClock } from "../api/config";
import { hasValidSession } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { EVENT_REFRESHED_QUERY_STALE_TIME_MS } from "../api/queryPolicy";
import { todayIso } from "../utils/date";
import { useSession } from "../state/session";

export function useBusinessClock(options?: { enabled?: boolean }) {
  const { session } = useSession();
  return useQuery<BusinessClock>({
    queryKey: queryKeys.businessClock(session.hotelId),
    queryFn: () => getBusinessClock(session),
    enabled: hasValidSession(session) && (options?.enabled ?? true),
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS
  });
}

export function useBusinessDate(fallbackDate?: string | null) {
  const clockQuery = useBusinessClock({ enabled: import.meta.env.DEV });
  const validFallback = fallbackDate && /^\d{4}-\d{2}-\d{2}$/.test(fallbackDate)
    ? fallbackDate
    : null;
  return clockQuery.data?.business_date ?? validFallback ?? todayIso();
}

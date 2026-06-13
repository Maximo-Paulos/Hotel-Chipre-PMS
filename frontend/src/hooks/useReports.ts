import { useQuery } from "@tanstack/react-query";

import {
  getDailyOperationalReport,
  getOperationalAlerts,
  type DailyOperationalReport,
  type NightlyOperationalSummary
} from "../api/reports";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const dailyReportKey = (hotelId: number | null, reportDate: string) => ["reports", "operational-daily", hotelId, reportDate];
const alertsKey = (hotelId: number | null, reportDate: string) => ["reports", "operational-alerts", hotelId, reportDate];

export function useDailyOperationalReport(reportDate: string) {
  const { session } = useSession();
  return useQuery<DailyOperationalReport>({
    queryKey: dailyReportKey(session.hotelId, reportDate),
    queryFn: () => getDailyOperationalReport(reportDate, session),
    enabled: Boolean(reportDate) && hasValidSession(session),
    staleTime: 30 * 1000
  });
}

export function useOperationalAlerts(reportDate: string) {
  const { session } = useSession();
  return useQuery<NightlyOperationalSummary>({
    queryKey: alertsKey(session.hotelId, reportDate),
    queryFn: () => getOperationalAlerts(reportDate, session),
    enabled: Boolean(reportDate) && hasValidSession(session),
    staleTime: 30 * 1000
  });
}

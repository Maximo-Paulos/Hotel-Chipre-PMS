import { useQuery } from "@tanstack/react-query";

import {
  getDailyOperationalReport,
  getOccupancyReport,
  getOperationalAlerts,
  getRevenueReport,
  type DailyOperationalReport,
  type NightlyOperationalSummary,
  type OccupancyReport,
  type RevenueReport
} from "../api/reports";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const dailyReportKey = (hotelId: number | null, reportDate: string) => ["reports", "operational-daily", hotelId, reportDate];
const alertsKey = (hotelId: number | null, reportDate: string) => ["reports", "operational-alerts", hotelId, reportDate];
const occupancyKey = (hotelId: number | null, startDate: string, endDate: string) => ["reports", "occupancy", hotelId, startDate, endDate];
const revenueKey = (hotelId: number | null, startDate: string, endDate: string) => ["reports", "revenue", hotelId, startDate, endDate];

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

export function useOccupancyReport(startDate: string, endDate: string) {
  const { session } = useSession();
  return useQuery<OccupancyReport>({
    queryKey: occupancyKey(session.hotelId, startDate, endDate),
    queryFn: () => getOccupancyReport(startDate, endDate, session),
    enabled: Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: 30 * 1000
  });
}

export function useRevenueReport(startDate: string, endDate: string, enabled = true) {
  const { session } = useSession();
  return useQuery<RevenueReport>({
    queryKey: revenueKey(session.hotelId, startDate, endDate),
    queryFn: () => getRevenueReport(startDate, endDate, session),
    enabled: enabled && Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: 30 * 1000
  });
}

import { useQuery } from "@tanstack/react-query";

import {
  getDailyOperationalReport,
  getBookedValueReport,
  getTodayArrivalCount,
  getOccupancyReport,
  getOperationalAlerts,
  getRevenueReport,
  type DailyOperationalReport,
  type ArrivalCount,
  type BookedValueReport,
  type NightlyOperationalSummary,
  type OccupancyReport,
  type RevenueReport
} from "../api/reports";
import { hasValidSession } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useSession } from "../state/session";

const dailyReportKey = (hotelId: number | null, reportDate: string) => [
  ...queryKeys.reports(hotelId, "operational-daily"),
  reportDate
];
const alertsKey = (hotelId: number | null, reportDate: string) => [
  ...queryKeys.reports(hotelId, "operational-alerts"),
  reportDate
];
const occupancyKey = (hotelId: number | null, startDate: string, endDate: string) => [
  ...queryKeys.reports(hotelId, "occupancy"),
  startDate,
  endDate
];
const revenueKey = (hotelId: number | null, startDate: string, endDate: string) => [
  ...queryKeys.reports(hotelId, "revenue"),
  startDate,
  endDate
];
const bookedValueKey = (hotelId: number | null, startDate: string, endDate: string) => [
  ...queryKeys.reports(hotelId, "booked-value"),
  startDate,
  endDate
];

export function useDailyOperationalReport(reportDate: string) {
  const { session } = useSession();
  return useQuery<DailyOperationalReport>({
    queryKey: dailyReportKey(session.hotelId, reportDate),
    queryFn: ({ signal }) => getDailyOperationalReport(reportDate, session, signal),
    enabled: Boolean(reportDate) && hasValidSession(session),
    staleTime: 30 * 1000,
    retry: false
  });
}

export function useTodayArrivalCount() {
  const { session } = useSession();
  return useQuery<ArrivalCount>({
    queryKey: [...queryKeys.reports(session.hotelId, "today-arrival-count")],
    queryFn: ({ signal }) => getTodayArrivalCount(session, signal),
    enabled: hasValidSession(session),
    staleTime: 30 * 1000,
    retry: false
  });
}

export function useOperationalAlerts(reportDate: string) {
  const { session } = useSession();
  return useQuery<NightlyOperationalSummary>({
    queryKey: alertsKey(session.hotelId, reportDate),
    queryFn: ({ signal }) => getOperationalAlerts(reportDate, session, signal),
    enabled: Boolean(reportDate) && hasValidSession(session),
    staleTime: 30 * 1000,
    retry: false
  });
}

export function useOccupancyReport(startDate: string, endDate: string, enabled = true) {
  const { session } = useSession();
  return useQuery<OccupancyReport>({
    queryKey: occupancyKey(session.hotelId, startDate, endDate),
    queryFn: ({ signal }) => getOccupancyReport(startDate, endDate, session, signal),
    enabled: enabled && Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: 30 * 1000,
    retry: false
  });
}

export function useRevenueReport(startDate: string, endDate: string, enabled = true) {
  const { session } = useSession();
  return useQuery<RevenueReport>({
    queryKey: revenueKey(session.hotelId, startDate, endDate),
    queryFn: ({ signal }) => getRevenueReport(startDate, endDate, session, signal),
    enabled: enabled && Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: 30 * 1000,
    retry: false
  });
}

export function useBookedValueReport(startDate: string, endDate: string, enabled = true) {
  const { session } = useSession();
  return useQuery<BookedValueReport>({
    queryKey: bookedValueKey(session.hotelId, startDate, endDate),
    queryFn: ({ signal }) => getBookedValueReport(startDate, endDate, session, signal),
    enabled: enabled && Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: 30 * 1000,
    retry: false
  });
}

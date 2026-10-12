import { useQuery } from "@tanstack/react-query";

import {
  getDailyOperationalReport,
  getBookedValueReport,
  getTodayArrivalCount,
  getOccupancyReport,
  getRevenueReport,
  type DailyOperationalReport,
  type ArrivalCount,
  type BookedValueReport,
  type OccupancyReport,
  type RevenueReport
} from "../api/reports";
import { hasValidSession } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { EVENT_REFRESHED_QUERY_STALE_TIME_MS } from "../api/queryPolicy";
import { useSession } from "../state/session";

const dailyReportKey = (hotelId: number | null, reportDate: string, pendingPage: number, pendingPageSize: number) => [
  ...queryKeys.reports(hotelId, "operational-daily"),
  reportDate,
  pendingPage,
  pendingPageSize
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

export function useDailyOperationalReport(reportDate: string, pendingPage = 1, pendingPageSize = 50) {
  const { session } = useSession();
  return useQuery<DailyOperationalReport>({
    queryKey: dailyReportKey(session.hotelId, reportDate, pendingPage, pendingPageSize),
    queryFn: ({ signal }) => getDailyOperationalReport(reportDate, pendingPage, session, signal, pendingPageSize),
    enabled: Boolean(reportDate) && hasValidSession(session),
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS,
    retry: false,
    placeholderData: (previousData) => previousData
  });
}

export function useTodayArrivalCount() {
  const { session } = useSession();
  return useQuery<ArrivalCount>({
    queryKey: [...queryKeys.reports(session.hotelId, "today-arrival-count")],
    queryFn: ({ signal }) => getTodayArrivalCount(session, signal),
    enabled: hasValidSession(session),
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS,
    retry: false
  });
}

export function useOccupancyReport(startDate: string, endDate: string, enabled = true) {
  const { session } = useSession();
  return useQuery<OccupancyReport>({
    queryKey: occupancyKey(session.hotelId, startDate, endDate),
    queryFn: ({ signal }) => getOccupancyReport(startDate, endDate, session, signal),
    enabled: enabled && Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS,
    retry: false
  });
}

export function useRevenueReport(startDate: string, endDate: string, enabled = true) {
  const { session } = useSession();
  return useQuery<RevenueReport>({
    queryKey: revenueKey(session.hotelId, startDate, endDate),
    queryFn: ({ signal }) => getRevenueReport(startDate, endDate, session, signal),
    enabled: enabled && Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS,
    retry: false
  });
}

export function useBookedValueReport(startDate: string, endDate: string, enabled = true) {
  const { session } = useSession();
  return useQuery<BookedValueReport>({
    queryKey: bookedValueKey(session.hotelId, startDate, endDate),
    queryFn: ({ signal }) => getBookedValueReport(startDate, endDate, session, signal),
    enabled: enabled && Boolean(startDate && endDate) && hasValidSession(session),
    staleTime: EVENT_REFRESHED_QUERY_STALE_TIME_MS,
    retry: false
  });
}

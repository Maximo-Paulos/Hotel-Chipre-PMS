import { useQuery } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import {
  getCategoryDailyRates,
  getRateCalendarDaily,
  listPricePeriods,
  getRatePaymentMethodOptions,
  type DailyRateRangeRow,
  type RateCalendarResponse,
  type PricePeriod,
  type RatePaymentMethodOptions
} from "../api/rate-calendar";
import { useSession } from "../state/session";

export type { PricePeriodInput } from "../api/rate-calendar";

export { formatLocalIsoDate, todayIso, addDaysIso } from "../utils/date";

export function useRateCalendar(categoryId: number | null, dateFrom: string, dateTo: string) {
  const { session } = useSession();

  return useQuery<RateCalendarResponse>({
    queryKey: ["rate-calendar", session.hotelId ?? null, categoryId, dateFrom, dateTo],
    queryFn: () => getRateCalendarDaily({ categoryId: categoryId as number, dateFrom, dateTo }, session),
    enabled: hasValidSession(session) && typeof categoryId === "number" && categoryId > 0,
    staleTime: 60_000
  });
}

export function useRatePaymentMethodOptions() {
  const { session } = useSession();
  return useQuery<RatePaymentMethodOptions>({
    queryKey: ["rate-payment-method-options", session.hotelId ?? null],
    queryFn: () => getRatePaymentMethodOptions(session),
    enabled: hasValidSession(session),
    staleTime: 60_000
  });
}

export function useCategoryDailyRates(categoryId: number | null, dateFrom: string, dateTo: string) {
  const { session } = useSession();

  return useQuery<DailyRateRangeRow[]>({
    queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId, dateFrom, dateTo],
    queryFn: () => getCategoryDailyRates(categoryId as number, dateFrom, dateTo, session),
    enabled: hasValidSession(session) && typeof categoryId === "number" && categoryId > 0,
    staleTime: 60_000
  });
}

export function usePricePeriods(categoryId: number | null) {
  const { session } = useSession();
  return useQuery<PricePeriod[]>({
    queryKey: ["price-periods", session.hotelId ?? null, categoryId],
    queryFn: () => listPricePeriods(categoryId as number, session),
    enabled: hasValidSession(session) && typeof categoryId === "number" && categoryId > 0,
    staleTime: 60_000
  });
}

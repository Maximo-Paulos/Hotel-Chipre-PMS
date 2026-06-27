import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import {
  bulkUpsertDailyRates,
  getCategoryDailyRates,
  getRateCalendarDaily,
  upsertDailyRate,
  type BulkRateResult,
  type DailyRateOut,
  type DailyRatePrices,
  type DailyRateRangeRow,
  type RateCalendarResponse
} from "../api/rate-calendar";
import { useSession } from "../state/session";

const pad = (value: number) => String(value).padStart(2, "0");

const formatLocalIsoDate = (value: Date) =>
  `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;

export const resolveRateCalendarRange = (year: number, today = new Date()) => {
  const currentYear = today.getFullYear();
  if (year === currentYear) {
    return {
      dateFrom: formatLocalIsoDate(today),
      dateTo: `${year}-12-31`
    };
  }

  return {
    dateFrom: `${year}-01-01`,
    dateTo: `${year}-12-31`
  };
};

export function useRateCalendar(categoryId: number | null, year: number) {
  const { session } = useSession();
  const { dateFrom, dateTo } = resolveRateCalendarRange(year);

  return useQuery<RateCalendarResponse>({
    queryKey: ["rate-calendar", session.hotelId ?? null, categoryId, year],
    queryFn: () =>
      getRateCalendarDaily(
        {
          categoryId: categoryId as number,
          dateFrom,
          dateTo
        },
        session
      ),
    enabled: hasValidSession(session) && typeof categoryId === "number" && categoryId > 0,
    staleTime: 60_000
  });
}

export function useCategoryDailyRates(categoryId: number | null, year: number) {
  const { session } = useSession();
  const { dateFrom, dateTo } = resolveRateCalendarRange(year);

  return useQuery<DailyRateRangeRow[]>({
    queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId, year],
    queryFn: () => getCategoryDailyRates(categoryId as number, dateFrom, dateTo, session),
    enabled: hasValidSession(session) && typeof categoryId === "number" && categoryId > 0,
    staleTime: 60_000
  });
}

export type SingleRateInput = DailyRatePrices & { date: string };

export function useUpsertDailyRate(categoryId: number | null, year: number) {
  const { session } = useSession();
  const queryClient = useQueryClient();

  return useMutation<DailyRateOut, Error, SingleRateInput>({
    mutationFn: (payload) => {
      if (typeof categoryId !== "number" || categoryId <= 0) {
        throw new Error("Seleccioná una categoría válida antes de guardar tarifas.");
      }
      return upsertDailyRate(categoryId, payload, session);
    },
    onSuccess: () => {
      // Refresh both the editable grid and the availability/channel view.
      queryClient.invalidateQueries({
        queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId, year]
      });
      queryClient.invalidateQueries({ queryKey: ["rate-calendar", session.hotelId ?? null, categoryId] });
    }
  });
}

export type BulkRateInput = DailyRatePrices & {
  from_date: string;
  to_date: string;
  exclude_dates?: string[];
};

export function useBulkUpsertRates(categoryId: number | null) {
  const { session } = useSession();
  const queryClient = useQueryClient();

  return useMutation<BulkRateResult, Error, BulkRateInput>({
    mutationFn: (payload) => {
      if (typeof categoryId !== "number" || categoryId <= 0) {
        throw new Error("Seleccioná una categoría válida antes de guardar tarifas.");
      }
      return bulkUpsertDailyRates(categoryId, payload, session);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rate-calendar", session.hotelId ?? null, categoryId] });
      queryClient.invalidateQueries({ queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId] });
    }
  });
}

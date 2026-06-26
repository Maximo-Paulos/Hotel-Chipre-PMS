import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import {
  bulkUpsertDailyRates,
  getRateCalendarDaily,
  type BulkRateResult,
  type DailyRatePrices,
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
    }
  });
}

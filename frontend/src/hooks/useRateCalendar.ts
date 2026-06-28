import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import {
  bulkUpsertDailyRates,
  bulkUpdateDailyRateField,
  getCategoryDailyRates,
  getRateCalendarDaily,
  upsertDailyRate,
  type BulkRateResult,
  type BulkRateField,
  type BulkRateFieldMode,
  type DailyRateOut,
  type DailyRatePrices,
  type DailyRateRangeRow,
  type RateCalendarResponse
} from "../api/rate-calendar";
import { useSession } from "../state/session";

const pad = (value: number) => String(value).padStart(2, "0");

export const formatLocalIsoDate = (value: Date) =>
  `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;

export const todayIso = () => formatLocalIsoDate(new Date());

/** Shift an ISO date (YYYY-MM-DD) by a number of days, returning ISO. */
export const addDaysIso = (iso: string, days: number) => {
  const base = new Date(`${iso}T00:00:00`);
  base.setDate(base.getDate() + days);
  return formatLocalIsoDate(base);
};

export function useRateCalendar(categoryId: number | null, dateFrom: string, dateTo: string) {
  const { session } = useSession();

  return useQuery<RateCalendarResponse>({
    queryKey: ["rate-calendar", session.hotelId ?? null, categoryId, dateFrom, dateTo],
    queryFn: () => getRateCalendarDaily({ categoryId: categoryId as number, dateFrom, dateTo }, session),
    enabled: hasValidSession(session) && typeof categoryId === "number" && categoryId > 0,
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

export type SingleRateInput = DailyRatePrices & { date: string };

export function useUpsertDailyRate(categoryId: number | null) {
  const { session } = useSession();
  const queryClient = useQueryClient();

  return useMutation<DailyRateOut, Error, SingleRateInput>({
    mutationFn: (payload) => {
      if (typeof categoryId !== "number" || categoryId <= 0) {
        throw new Error("Seleccioná una categoría válida antes de guardar tarifas.");
      }
      return upsertDailyRate(categoryId, payload, session);
    },
    // Prefix-match invalidation so every loaded date window refetches.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId] });
      queryClient.invalidateQueries({ queryKey: ["rate-calendar", session.hotelId ?? null, categoryId] });
    }
  });
}

export type BulkRateInput = DailyRatePrices & {
  from_date: string;
  to_date: string;
  exclude_dates?: string[];
};

export type BulkRateFieldInput = {
  from_date: string;
  to_date: string;
  field: BulkRateField;
  mode: BulkRateFieldMode;
  value: number;
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

export function useBulkUpdateRateField(categoryId: number | null) {
  const { session } = useSession();
  const queryClient = useQueryClient();

  return useMutation<BulkRateResult, Error, BulkRateFieldInput>({
    mutationFn: (payload) => {
      if (typeof categoryId !== "number" || categoryId <= 0) {
        throw new Error("Seleccioná una categoría válida antes de guardar tarifas.");
      }
      return bulkUpdateDailyRateField(categoryId, payload, session);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rate-calendar", session.hotelId ?? null, categoryId] });
      queryClient.invalidateQueries({ queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId] });
    }
  });
}

import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import {
  bulkUpsertDailyRates,
  bulkUpdateDailyRateField,
  getCategoryDailyRates,
  getRateCalendarDaily,
  upsertDailyRate,
  listPricePeriods,
  createPricePeriod,
  updatePricePeriod,
  deletePricePeriod,
  type BulkRateResult,
  type BulkRateField,
  type BulkRateFieldMode,
  type DailyRateOut,
  type DailyRatePrices,
  type DailyRateRangeRow,
  type RateCalendarResponse,
  type PricePeriod,
  type PricePeriodInput
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

export function usePricePeriods(categoryId: number | null) {
  const { session } = useSession();
  return useQuery<PricePeriod[]>({
    queryKey: ["price-periods", session.hotelId ?? null, categoryId],
    queryFn: () => listPricePeriods(categoryId as number, session),
    enabled: hasValidSession(session) && typeof categoryId === "number" && categoryId > 0,
    staleTime: 60_000
  });
}

export function usePricePeriodMutations(categoryId: number | null) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["price-periods", session.hotelId ?? null, categoryId] });
    queryClient.invalidateQueries({ queryKey: ["rate-calendar", session.hotelId ?? null, categoryId] });
    queryClient.invalidateQueries({ queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId] });
  };
  const create = useMutation({ mutationFn: (payload: PricePeriodInput) => createPricePeriod(payload, session), onSuccess: invalidate });
  const update = useMutation({ mutationFn: ({ id, payload }: { id: number; payload: Partial<PricePeriodInput> }) => updatePricePeriod(id, payload, session), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => deletePricePeriod(id, session), onSuccess: invalidate });
  return { create, update, remove };
}

import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelRateChangeDraft,
  confirmRateChangeDraft,
  createRateChangeDraft,
  editRateRecommendationDraft,
  listRateChangeDrafts,
  type RateChangeDraftInput
} from "../api/rateChangeDrafts";
import { hasValidSession } from "../api/client";
import { invalidateQueriesInBackground } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

export function useRateChangeDrafts(categoryId: number | null) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const enabled = hasValidSession(session) && typeof categoryId === "number" && categoryId > 0;
  const draftsQuery = useQuery({
    queryKey: ["rate-change-drafts", session.hotelId ?? null, categoryId],
    queryFn: () => listRateChangeDrafts(categoryId as number, session),
    enabled,
    staleTime: 10_000
  });

  const invalidateDrafts = () => {
    invalidateQueriesInBackground(queryClient, { queryKey: ["rate-change-drafts", session.hotelId ?? null, categoryId] });
  };

  const invalidateConfirmedRates = () => {
    invalidateDrafts();
    invalidateQueriesInBackground(queryClient, { queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId] });
    invalidateQueriesInBackground(queryClient, { queryKey: ["rate-calendar", session.hotelId ?? null, categoryId] });
    invalidateQueriesInBackground(queryClient, { queryKey: ["price-periods", session.hotelId ?? null, categoryId] });
    invalidateQueriesInBackground(queryClient, { queryKey: ["reservation-quote", session.hotelId ?? null, categoryId] });
  };

  const create = useGuardedMutation({
    mutationFn: (payload: RateChangeDraftInput) => createRateChangeDraft(payload, session),
    onSuccess: invalidateDrafts
  });
  const confirm = useGuardedMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => confirmRateChangeDraft(id, version, session),
    onSuccess: invalidateConfirmedRates
  });
  const cancel = useGuardedMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => cancelRateChangeDraft(id, version, session),
    onSuccess: invalidateDrafts
  });
  const editRecommendation = useGuardedMutation({
    mutationFn: ({
      id,
      version,
      changes
    }: {
      id: number;
      version: number;
      changes: Array<{ date: string; values: { price: number } }>;
    }) => editRateRecommendationDraft(id, version, changes, session),
    onSuccess: invalidateDrafts
  });

  return { draftsQuery, create, editRecommendation, confirm, cancel };
}

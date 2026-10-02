import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelRateChangeDraft,
  confirmRateChangeDraft,
  createRateChangeDraft,
  listRateChangeDrafts,
  type RateChangeDraftInput
} from "../api/rateChangeDrafts";
import { hasValidSession } from "../api/client";
import { refreshAfterMutation } from "../api/queryInvalidation";
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

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["rate-change-drafts", session.hotelId ?? null, categoryId] }),
      queryClient.invalidateQueries({ queryKey: ["category-daily-rates", session.hotelId ?? null, categoryId] }),
      queryClient.invalidateQueries({ queryKey: ["rate-calendar", session.hotelId ?? null, categoryId] }),
      refreshAfterMutation(queryClient, session.hotelId, ["rooms", "settings", "reservations", "analytics"])
    ]);
  };

  const create = useGuardedMutation({
    mutationFn: (payload: RateChangeDraftInput) => createRateChangeDraft(payload, session),
    onSuccess: invalidate
  });
  const confirm = useGuardedMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => confirmRateChangeDraft(id, version, session),
    onSuccess: invalidate
  });
  const cancel = useGuardedMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => cancelRateChangeDraft(id, version, session),
    onSuccess: invalidate
  });

  return { draftsQuery, create, confirm, cancel };
}

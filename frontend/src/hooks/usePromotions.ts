import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import {
  createPromotion,
  deactivatePromotion,
  listPromotions,
  reactivatePromotion,
  simulatePromotionPricing,
  updatePromotion,
  type Promotion,
  type PromotionCreatePayload,
  type PromotionSimulateParams,
  type PromotionSimulateResult,
  type PromotionUpdatePayload
} from "../api/promotions";
import { useSession } from "../state/session";
import { refreshSettingsState } from "../api/queryInvalidation";

import { useGuardedMutation } from "./useGuardedMutation";

const promotionsKey = (hotelId: number | null, includeInactive: boolean) => ["promotions", hotelId, includeInactive];

export function usePromotions(includeInactive = false) {
  const { session } = useSession();
  return useQuery<Promotion[]>({
    queryKey: promotionsKey(session.hotelId, includeInactive),
    queryFn: () => listPromotions(includeInactive, session),
    enabled: hasValidSession(session),
    staleTime: 30 * 1000
  });
}

export function usePromotionMutations() {
  const qc = useQueryClient();
  const { session } = useSession();
  // Both include_inactive=true/false query variants are cached separately;
  // invalidate the whole "promotions" family so neither goes stale.
  const invalidate = () => refreshSettingsState(qc, session.hotelId);

  const createMutation = useGuardedMutation({
    mutationFn: (payload: PromotionCreatePayload) => createPromotion(payload, session),
    onSuccess: async () => invalidate()
  });

  const updateMutation = useGuardedMutation({
    mutationFn: ({ id, payload }: { id: number; payload: PromotionUpdatePayload }) =>
      updatePromotion(id, payload, session),
    onSuccess: async () => invalidate()
  });

  const deactivateMutation = useGuardedMutation({
    mutationFn: (id: number) => deactivatePromotion(id, session),
    onSuccess: async () => invalidate()
  });

  const reactivateMutation = useGuardedMutation({
    mutationFn: (id: number) => reactivatePromotion(id, session),
    onSuccess: async () => invalidate()
  });

  return { createMutation, updateMutation, deactivateMutation, reactivateMutation };
}

export function useSimulatePromotion() {
  const { session } = useSession();
  return useMutation<PromotionSimulateResult, Error, PromotionSimulateParams>({
    mutationFn: (payload) => simulatePromotionPricing(payload, session)
  });
}

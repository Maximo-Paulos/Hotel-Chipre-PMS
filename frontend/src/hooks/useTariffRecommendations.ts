import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getTariffRecommendationSettings,
  runTariffRecommendation,
  updateTariffRecommendationSettings,
  type TariffRecommendationSettingsInput
} from "../api/tariff-recommendations";
import { hasValidSession } from "../api/client";
import { invalidateQueriesInBackground } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

export function useTariffRecommendations(categoryId: number | null) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["tariff-recommendation-settings", session.hotelId ?? null],
    queryFn: () => getTariffRecommendationSettings(session),
    enabled: hasValidSession(session),
    staleTime: 60_000
  });
  const saveSettings = useGuardedMutation({
    mutationFn: (payload: TariffRecommendationSettingsInput) => updateTariffRecommendationSettings(payload, session),
    onSuccess: (data) => {
      queryClient.setQueryData(["tariff-recommendation-settings", session.hotelId ?? null], data);
    }
  });
  const generate = useGuardedMutation({
    mutationFn: ({ dateFrom, dateTo }: { dateFrom: string; dateTo: string }) => {
      if (!categoryId) throw new Error("Seleccioná una categoría para generar recomendaciones.");
      return runTariffRecommendation({ category_id: categoryId, date_from: dateFrom, date_to: dateTo }, session);
    },
    onSuccess: () => {
      invalidateQueriesInBackground(queryClient, {
        queryKey: ["rate-change-drafts", session.hotelId ?? null, categoryId]
      });
    }
  });

  return { settingsQuery, saveSettings, generate };
}

import { apiFetch, type SessionLike } from "./client";

export type TariffRecommendationSettings = {
  hotel_id: number;
  enabled: boolean;
  high_occupancy_pct: number;
  low_occupancy_pct: number;
  pickup_change_pct: number;
  max_step_pct: number;
};

export type TariffRecommendationSettingsInput = Omit<TariffRecommendationSettings, "hotel_id">;

export type TariffRecommendationRunResult = {
  created: boolean;
  reason: string | null;
  draft_id: number | null;
  suggestions: Array<{
    date: string;
    direction: "up" | "down";
    signal: string;
    season_key: string;
    event_name: string | null;
    currency_code: string;
    current_amount: number;
    suggested_amount: number;
    current_usd: number;
    suggested_usd: number;
    comparable_average_usd: number;
    current_vs_comparable_pct: number;
    occupancy_pct: number;
    pickup_change_pct: number | null;
    adjustment_pct: number;
    max_step_pct: number;
  }>;
  skipped: Record<string, number>;
  draft: unknown;
};

export const getTariffRecommendationSettings = (session?: SessionLike) =>
  apiFetch<TariffRecommendationSettings>("/api/tariff-recommendations/settings", { session });

export const updateTariffRecommendationSettings = (
  payload: TariffRecommendationSettingsInput,
  session?: SessionLike
) => apiFetch<TariffRecommendationSettings>("/api/tariff-recommendations/settings", {
  method: "PUT",
  data: payload,
  session
});

export const runTariffRecommendation = (
  payload: { category_id: number; date_from: string; date_to: string },
  session?: SessionLike
) => apiFetch<TariffRecommendationRunResult>("/api/tariff-recommendations/generate", {
  method: "POST",
  data: payload,
  session
});

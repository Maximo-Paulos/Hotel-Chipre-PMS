import { apiFetch, type SessionLike } from "./client";

export type RateChangeField =
  | "price"
  | "price_cash"
  | "price_transfer"
  | "price_mercadopago"
  | "price_paypal"
  | "price_credit_card";

export type RateChangeValues = Partial<Record<RateChangeField, number | null>>;

export type RateChangeDraftInput = {
  category_id: number;
  changes: Array<{ date: string; values: RateChangeValues }>;
  draft_type?: "daily_rates";
} | {
  category_id: number;
  draft_type: "price_period";
  period_operation: {
    action: "create" | "update" | "delete";
    period_id?: number;
    values?: {
      name: string;
      start_date: string;
      end_date: string;
      price_per_night: number;
      price_cash?: number | null;
      price_transfer?: number | null;
      price_mercadopago?: number | null;
      price_paypal?: number | null;
      price_credit_card?: number | null;
      price_debit_card?: number | null;
      price_booking?: number | null;
      price_expedia?: number | null;
      priority: number;
      is_active: boolean;
      comparable_season_key?: string | null;
      is_high_demand_event: boolean;
    };
  };
};

export type RateChangeImpact = {
  reservations_impacted: number;
  reservation_nights: number;
  dates_with_reservations: string[];
  recommendation?: {
    engine?: string;
    trigger?: string;
    currency_code?: string;
    fx_market?: string | null;
    fx_side?: string | null;
    fx_ars_per_usd?: number | null;
    fx_quote_as_of?: string | null;
    method?: string;
    suggestions?: Array<{
      date: string;
      direction: "up" | "down";
      signal: string;
      event_name?: string | null;
      current_amount: number;
      suggested_amount: number;
      current_usd: number;
      suggested_usd: number;
      comparable_average_usd: number;
      current_vs_comparable_pct?: number;
      occupancy_pct: number;
      pickup_change_pct: number | null;
      adjustment_pct?: number;
      max_step_pct: number;
    }>;
  };
};

export type RateChangeDraft = {
  id: number;
  hotel_id: number;
  category_id: number;
  draft_type: "daily_rates" | "price_period";
  status: "draft" | "confirmed" | "cancelled";
  version: number;
  changes: Array<{
    date: string;
    source_before?: string | null;
    before: RateChangeValues;
    after: RateChangeValues;
    values: RateChangeValues;
  }>;
  period_operation?: {
    action: "create" | "update" | "delete";
    period_id?: number | null;
    before?: Record<string, unknown> | null;
    after?: Record<string, unknown> | null;
    effective_changes: Array<{
      date: string;
      before: Record<string, number>;
      after: Record<string, number>;
      source_before: string;
      source_after: string;
    }>;
  } | null;
  impact: RateChangeImpact;
  impact_at_creation: RateChangeImpact;
  created_by_user_id?: number | null;
  created_at: string;
  updated_at: string;
  confirmed_at?: string | null;
  confirmed_by_user_id?: number | null;
  cancelled_at?: string | null;
  cancelled_by_user_id?: number | null;
};

export const listRateChangeDrafts = (categoryId: number, session?: SessionLike) => {
  const search = new URLSearchParams({ category_id: String(categoryId), limit: "50" });
  return apiFetch<RateChangeDraft[]>(`/api/rate-change-drafts?${search.toString()}`, { session });
};

export const createRateChangeDraft = (payload: RateChangeDraftInput, session?: SessionLike) =>
  apiFetch<RateChangeDraft>("/api/rate-change-drafts", { method: "POST", data: payload, session });

export const getRateChangeDraft = (draftId: number, session?: SessionLike) =>
  apiFetch<RateChangeDraft>(`/api/rate-change-drafts/${draftId}`, { session });

export const editRateRecommendationDraft = (
  draftId: number,
  expectedVersion: number,
  changes: Array<{ date: string; values: { price: number } }>,
  session?: SessionLike
) => apiFetch<RateChangeDraft>(`/api/rate-change-drafts/${draftId}`, {
  method: "PATCH",
  data: { expected_version: expectedVersion, changes },
  session
});

export const confirmRateChangeDraft = (draftId: number, expectedVersion: number, session?: SessionLike) =>
  apiFetch<RateChangeDraft>(`/api/rate-change-drafts/${draftId}/confirm`, {
    method: "POST",
    data: { expected_version: expectedVersion },
    session
  });

export const cancelRateChangeDraft = (draftId: number, expectedVersion: number, session?: SessionLike) =>
  apiFetch<RateChangeDraft>(`/api/rate-change-drafts/${draftId}/cancel`, {
    method: "POST",
    data: { expected_version: expectedVersion },
    session
  });

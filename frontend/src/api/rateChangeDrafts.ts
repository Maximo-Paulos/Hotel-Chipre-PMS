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
    };
  };
};

export type RateChangeImpact = {
  reservations_impacted: number;
  reservation_nights: number;
  dates_with_reservations: string[];
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

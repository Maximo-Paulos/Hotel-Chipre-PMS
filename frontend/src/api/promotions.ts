import { apiFetch, type SessionLike } from "./client";

export type PromotionBenefitType = "fixed" | "percentage";
export type PromotionScope = "full_stay" | "from_night_n";

// Every field is a wildcard ("no restriction on this dimension") when null/omitted.
// Mirrors app/schemas/promotion.py PromotionConditions -- keep field-for-field in sync.
export type PromotionConditions = {
  booking_from?: string | null;
  booking_to?: string | null;
  stay_from?: string | null;
  stay_to?: string | null;
  min_nights?: number | null;
  max_nights?: number | null;
  weekdays?: string[] | null; // subset of mon..sun
  category_id?: number | null;
  room_id?: number | null;
  sales_channel_code?: string | null;
  guest_id?: number | null;
  company_id?: number | null;
  guest_tag_type?: string | null;
  payment_currency?: string | null;
  payment_method?: string | null;
};

export type Promotion = {
  id: number;
  hotel_id: number;
  code: string;
  name: string;
  description?: string | null;
  benefit_type: PromotionBenefitType;
  benefit_value: number;
  scope: PromotionScope;
  from_night_number?: number | null;
  priority: number;
  stackable: boolean;
  is_active: boolean;
  version: number;
  previous_version_id?: number | null;
  conditions: PromotionConditions;
  created_at: string;
  updated_at: string;
  deactivated_at?: string | null;
};

export type PromotionCreatePayload = {
  code: string;
  name: string;
  description?: string | null;
  benefit_type: PromotionBenefitType;
  benefit_value: number;
  scope: PromotionScope;
  from_night_number?: number | null;
  priority?: number;
  stackable?: boolean;
  conditions?: PromotionConditions;
};

// Editing a promotion creates a new immutable version server-side; the code
// itself can never change (see app/schemas/promotion.py PromotionUpdate).
export type PromotionUpdatePayload = {
  name?: string;
  description?: string | null;
  benefit_type?: PromotionBenefitType;
  benefit_value?: number;
  scope?: PromotionScope;
  from_night_number?: number | null;
  priority?: number;
  stackable?: boolean;
  conditions?: PromotionConditions;
};

export type PromotionSimulateParams = {
  category_id: number;
  check_in_date: string;
  check_out_date: string;
  payment_method?: string | null;
  target_currency?: string | null;
  sales_channel_code?: string | null;
  guest_id?: number | null;
  company_id?: number | null;
  booking_date?: string | null;
};

export type PromotionAppliedEntry = {
  promotion_id: number;
  code: string;
  version: number;
  benefit_type: PromotionBenefitType;
  benefit_value: string;
  amount_deducted: string;
};

export type PromotionSimulateNight = {
  date: string;
  base_amount: string;
  promotions_applied: PromotionAppliedEntry[];
  post_promotion_amount: string;
};

export type PromotionSimulateResult = {
  pricing_source: string;
  hotel_id: number;
  category_id: number;
  check_in: string;
  check_out: string;
  nights: number;
  base_currency: string;
  output_currency: string;
  per_night: PromotionSimulateNight[];
  promotions_applied: PromotionAppliedEntry[];
  subtotal_amount: string;
  tax_amount: string;
  fee_amount: string;
  fx_rate_snapshot: string | null;
  booking_total: string;
  payment_adjustment: {
    payment_method: string;
    surcharge_type: string;
    surcharge_value: string | null;
    surcharge_amount: string;
  } | null;
  final_total_with_payment_adjustment: string;
};

export const listPromotions = (includeInactive = false, session?: SessionLike) =>
  apiFetch<Promotion[]>(`/api/promotions?include_inactive=${includeInactive}`, { session });

export const createPromotion = (payload: PromotionCreatePayload, session?: SessionLike) =>
  apiFetch<Promotion>("/api/promotions", { method: "POST", data: payload, session });

export const updatePromotion = (id: number, payload: PromotionUpdatePayload, session?: SessionLike) =>
  apiFetch<Promotion>(`/api/promotions/${id}`, { method: "PATCH", data: payload, session });

export const deactivatePromotion = (id: number, session?: SessionLike) =>
  apiFetch<Promotion>(`/api/promotions/${id}`, { method: "DELETE", session });

export const reactivatePromotion = (id: number, session?: SessionLike) =>
  apiFetch<Promotion>(`/api/promotions/${id}/reactivate`, { method: "POST", session });

export const simulatePromotionPricing = (payload: PromotionSimulateParams, session?: SessionLike) =>
  apiFetch<PromotionSimulateResult>("/api/promotions/simulate", { method: "POST", data: payload, session });

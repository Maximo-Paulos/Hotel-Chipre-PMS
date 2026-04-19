import { apiFetch, type SessionLike } from "./client";

export type SubscriptionPlan = {
  code: string;
  name: string;
  room_limit: number;
  price_month?: number | null;
  price_year?: number | null;
  description?: string;
  features?: string[];
  badge?: string;
  highlight?: boolean;
  mock?: boolean;
};

export type SubscriptionLimit = {
  code?: string;
  label?: string;
  limit?: number | null;
  used?: number | null;
};

export type SubscriptionStatus = {
  hotel_id: number | null;
  status: string;
  plan: string | null;
  room_limit: number;
  staff_limit?: number | null;
  rooms_in_use: number;
  can_write?: boolean;
  limits?: Array<SubscriptionLimit> | Record<string, SubscriptionLimit>;
  trial_started_at?: string | null;
  trial_end_at?: string | null;
  trial_remaining_days?: number | null;
  source?: "api" | "mock";
  available_plans?: Array<SubscriptionPlan>;
};

export const getSubscriptionStatus = (session?: SessionLike) =>
  apiFetch<SubscriptionStatus>("/api/subscription/status", { session });

export const listSubscriptionPlans = (session?: SessionLike) =>
  apiFetch<Array<SubscriptionPlan>>("/api/subscription/plans", { session });

export const changeSubscriptionPlan = (plan_code: string, session?: SessionLike) =>
  apiFetch<SubscriptionStatus>("/api/subscription/plan", { method: "POST", data: { plan_code }, session });

export const startTrial = (plan_code: string, session?: SessionLike) =>
  apiFetch<SubscriptionStatus>("/api/subscription/trial", { method: "POST", data: { plan_code }, session });

export const adminCompedOverride = (
  hotel_id: number,
  plan_code: string,
  reason?: string,
  session?: SessionLike
) =>
  apiFetch<SubscriptionStatus>("/api/admin/subscription/comped-override", {
    method: "POST",
    data: { hotel_id, plan_code, reason },
    session
  });

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
  hotel_id: number;
  status: string;
  plan: string | null;
  room_limit: number;
  rooms_in_use: number;
  can_write?: boolean;
  limits?: Array<SubscriptionLimit> | Record<string, SubscriptionLimit>;
  source?: "api" | "mock";
  available_plans?: Array<SubscriptionPlan>;
};

export const getSubscriptionStatus = (session?: SessionLike) =>
  apiFetch<SubscriptionStatus>("/api/subscription/status", { session });

export const listSubscriptionPlans = (session?: SessionLike) =>
  apiFetch<Array<SubscriptionPlan>>("/api/subscription/plans", { session });

export const changeSubscriptionPlan = (plan_code: string, session?: SessionLike) =>
  apiFetch<SubscriptionStatus>("/api/subscription/plan", { method: "POST", data: { plan_code }, session });

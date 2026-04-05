import { apiFetch, type SessionLike } from "./client";

export type SubscriptionStatus = {
  hotel_id: number;
  status: string;
  plan: string | null;
  room_limit: number;
  rooms_in_use: number;
  available_plans?: Array<{ code: string; name: string; room_limit: number; price_month?: number | null }>;
};

export const getSubscriptionStatus = (session?: SessionLike) =>
  apiFetch<SubscriptionStatus>("/api/subscription/status", { session });

export const listSubscriptionPlans = (session?: SessionLike) =>
  apiFetch<Array<{ code: string; name: string; room_limit: number; price_month?: number | null }>>(
    "/api/subscription/plans",
    { session }
  );

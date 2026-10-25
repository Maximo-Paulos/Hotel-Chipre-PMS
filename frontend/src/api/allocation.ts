import { apiFetch, type SessionLike } from "./client";

export type AllocationObjective = "occupied_nights" | "net_revenue" | "combined";

export type AllocationPolicyVersion = {
  id: number;
  profile_id: number;
  version_number: number;
  source: string;
  constraints: Record<string, unknown>;
  weights: Record<string, number>;
  optimization_objective: AllocationObjective;
  combined_revenue_weight: number | null;
  prompt_summary: string | null;
  is_published: boolean;
  created_by_user_id: number | null;
  created_at: string;
};

export type ActiveAllocationPolicy = {
  profile_id: number;
  profile_code: string;
  profile_name: string;
  version: AllocationPolicyVersion;
};

export type AllocationPolicyVersionCreate = {
  constraints: Record<string, unknown>;
  weights: Record<string, number>;
  optimization_objective: AllocationObjective;
  combined_revenue_weight?: number;
  prompt_summary?: string;
  source: "manual";
  publish: true;
};

export type AllocationExplanation = {
  id: number;
  allocation_run_id: number;
  reservation_id: number;
  explanation_type: string;
  summary: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type AllocationAssignment = {
  id: number;
  reservation_id: number;
  source_room_id: number | null;
  room_id: number | null;
  status: "proposed" | "applied" | "locked" | "rejected" | "manual_review" | string;
  explanation_summary: string | null;
};

export type AllocationRunDetail = {
  run_id: number;
  status: "pending" | "running" | "succeeded" | "failed" | "partial" | string;
  trigger_type: string;
  objective_score: number | null;
  solver_summary: string | null;
  error_message: string | null;
  policy_version_id: number | null;
  horizon_start: string | null;
  horizon_end: string | null;
  created_at: string;
  explanations: AllocationExplanation[];
  metrics: Array<{ metric_key: string; metric_value: number }>;
  assignments: AllocationAssignment[];
};

export type ReservationReassignmentLock = {
  reservation_id: number;
  room_id: number | null;
  allocation_locked: boolean;
};

export const getActiveAllocationPolicy = (session?: SessionLike) =>
  apiFetch<ActiveAllocationPolicy>("/api/allocation/policy", { session });

export const createAndPublishAllocationPolicy = (payload: AllocationPolicyVersionCreate, session?: SessionLike) =>
  apiFetch<AllocationPolicyVersion>("/api/allocation/policy/versions", {
    method: "POST",
    data: payload,
    session
  });

export const getLatestAllocationRun = (session?: SessionLike) =>
  apiFetch<AllocationRunDetail>("/api/allocation/policy/runs/latest", { session });

export const getAllocationRun = (runId: number, session?: SessionLike) =>
  apiFetch<AllocationRunDetail>(`/api/allocation/policy/runs/${runId}`, { session });

export const acceptAllocationRun = (runId: number, session?: SessionLike) =>
  apiFetch<AllocationRunDetail>(`/api/allocation/policy/runs/${runId}/accept`, { method: "POST", session });

export const rejectAllocationRun = (runId: number, session?: SessionLike) =>
  apiFetch<AllocationRunDetail>(`/api/allocation/policy/runs/${runId}/reject`, { method: "POST", session });

export const setReservationReassignmentLock = (
  reservationId: number,
  locked: boolean,
  session?: SessionLike
) => apiFetch<ReservationReassignmentLock>(`/api/allocation/policy/reservations/${reservationId}/reassignment-lock`, {
  method: "PATCH",
  data: { locked, reason: null },
  session
});

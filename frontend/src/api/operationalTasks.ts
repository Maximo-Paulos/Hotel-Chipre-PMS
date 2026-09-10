import { apiFetch, type SessionLike } from "./client";

export type OperationalTaskType = "general" | "reception" | "housekeeping" | "maintenance";
export type OperationalTaskStatus = "pending" | "in_progress" | "pending_review" | "resolved";
export type OperationalTaskPriority = "low" | "medium" | "high" | "critical";

export type OperationalTask = {
  id: number;
  hotel_id: number;
  task_type: OperationalTaskType;
  status: OperationalTaskStatus;
  priority: OperationalTaskPriority;
  title: string;
  description?: string | null;
  room_id?: number | null;
  room_number?: string | null;
  reservation_id?: number | null;
  confirmation_code?: string | null;
  room_block_id?: number | null;
  assigned_to_user_id?: number | null;
  due_at?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export type OperationalTaskEvent = {
  id: number;
  from_status?: string | null;
  to_status: string;
  actor_user_id?: number | null;
  comment?: string | null;
  created_at: string;
};

export type ShiftHandoff = {
  id: number;
  hotel_id: number;
  delivered_by_user_id?: number | null;
  received_by_user_id?: number | null;
  cash_close_report_id?: number | null;
  status: "pending_acknowledgement" | "acknowledged";
  notes?: string | null;
  delivered_at: string;
  acknowledged_at?: string | null;
  version: number;
  task_ids: number[];
};

export type OperationalTaskCreate = {
  task_type: OperationalTaskType;
  priority: OperationalTaskPriority;
  title: string;
  description?: string | null;
  room_id?: number | null;
  reservation_id?: number | null;
  room_block_id?: number | null;
  assigned_to_user_id?: number | null;
  due_at?: string | null;
};

export const listOperationalTasks = (session?: SessionLike) =>
  apiFetch<OperationalTask[]>("/api/operational-tasks?limit=200", { session });

export const createOperationalTask = (payload: OperationalTaskCreate, session?: SessionLike) =>
  apiFetch<OperationalTask>("/api/operational-tasks", { method: "POST", data: payload, session });

export const updateOperationalTask = (
  taskId: number,
  payload: { client_version: number; status?: OperationalTaskStatus; comment?: string | null },
  session?: SessionLike
) => apiFetch<OperationalTask>(`/api/operational-tasks/${taskId}`, { method: "PATCH", data: payload, session });

export const listOperationalTaskHistory = (taskId: number, session?: SessionLike) =>
  apiFetch<OperationalTaskEvent[]>(`/api/operational-tasks/${taskId}/history`, { session });

export const resolveOperationalTask = (taskId: number, clientVersion: number, comment?: string, session?: SessionLike) =>
  apiFetch<OperationalTask>(`/api/operational-tasks/${taskId}/resolve`, {
    method: "POST",
    data: { client_version: clientVersion, comment: comment || null },
    session
  });

export const createShiftHandoff = (payload: { task_ids: number[]; notes?: string | null; cash_close_report_id?: number | null }, session?: SessionLike) =>
  apiFetch<ShiftHandoff>("/api/operational-tasks/handoffs", { method: "POST", data: payload, session });

export const listShiftHandoffs = (session?: SessionLike) =>
  apiFetch<ShiftHandoff[]>("/api/operational-tasks/handoffs", { session });

export const acknowledgeShiftHandoff = (handoffId: number, clientVersion: number, session?: SessionLike) =>
  apiFetch<ShiftHandoff>(`/api/operational-tasks/handoffs/${handoffId}/acknowledge`, {
    method: "POST",
    data: { client_version: clientVersion },
    session
  });

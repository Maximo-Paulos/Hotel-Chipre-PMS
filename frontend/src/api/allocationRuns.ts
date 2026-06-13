import { apiFetch, type SessionLike } from "./client";

export type AllocationRunPayload = {
  apply: boolean;
  horizon_start?: string | null;
  horizon_end?: string | null;
};

export type AllocationRunResponse = {
  run_id: number;
  status: string;
  objective_score: number;
  assignments_created: number;
  unassigned_count: number;
  moved_count: number;
};

export type RoomMoveEvent = {
  id: number;
  hotel_id: number;
  reservation_id: number;
  movement_group_id?: number | null;
  from_room_id?: number | null;
  to_room_id?: number | null;
  move_type: string;
  reason_code?: string | null;
  trigger_event?: string | null;
  state_before?: string | null;
  state_after?: string | null;
  occurred_at: string;
  created_by_user_id?: number | null;
};

export type RoomMovementGroup = {
  id: number;
  hotel_id: number;
  trigger_reason: string;
  notes?: string | null;
  is_reverted: boolean;
  reverted_by_user_id?: number | null;
  reverted_at?: string | null;
  created_by_user_id?: number | null;
  created_at: string;
  move_events: RoomMoveEvent[];
};

export const triggerAllocationRecalculation = (payload: AllocationRunPayload, session?: SessionLike) =>
  apiFetch<AllocationRunResponse>("/api/reservations/allocation/recalculate", {
    method: "POST",
    data: payload,
    session
  });

export const listRoomMovementGroups = (limit = 6, session?: SessionLike) =>
  apiFetch<RoomMovementGroup[]>(`/api/room-movement-groups/?limit=${limit}`, { session });

export const revertRoomMovementGroup = (groupId: number, session?: SessionLike) =>
  apiFetch<RoomMovementGroup>(`/api/room-movement-groups/${groupId}/revert`, {
    method: "POST",
    session
  });

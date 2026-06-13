import { apiFetch, type SessionLike } from "./client";

export type RoomBlockReasonCode =
  | "maintenance"
  | "deep_cleaning"
  | "owner_use"
  | "vip_hold"
  | "overbooking_buffer"
  | "other";

export type RoomBlock = {
  id: number;
  hotel_id: number;
  room_id: number;
  reason_code: RoomBlockReasonCode;
  reason_note?: string | null;
  starts_at: string;
  ends_at?: string | null;
  is_indefinite: boolean;
  created_by_user_id?: number | null;
  resolved_by_user_id?: number | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type RoomBlockCreatePayload = {
  room_id: number;
  starts_at: string;
  ends_at?: string | null;
  is_indefinite: boolean;
  reason_code: RoomBlockReasonCode;
  reason_note?: string | null;
};

export const listActiveRoomBlocks = (
  params: { start_date?: string; end_date?: string } = {},
  session?: SessionLike
) => {
  const search = new URLSearchParams();
  if (params.start_date) search.set("start_date", params.start_date);
  if (params.end_date) search.set("end_date", params.end_date);
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  return apiFetch<RoomBlock[]>(`/api/room-blocks/${suffix}`, { session });
};

export const createRoomBlock = (payload: RoomBlockCreatePayload, session?: SessionLike) =>
  apiFetch<RoomBlock>("/api/room-blocks/", { method: "POST", data: payload, session });

export const resolveRoomBlock = (blockId: number, session?: SessionLike) =>
  apiFetch<RoomBlock>(`/api/room-blocks/${blockId}/resolve`, { method: "POST", session });

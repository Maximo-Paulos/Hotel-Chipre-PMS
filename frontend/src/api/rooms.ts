import { apiFetch, type SessionLike } from "./client";

export type RoomStatus = "available" | "occupied" | "maintenance" | "blocked" | "cleaning";
export type HousekeepingStatus = "dirty" | "in_progress" | "clean" | "inspected";
export type RoomBlockReason = "maintenance" | "deep_cleaning" | "owner_use" | "vip_hold" | "overbooking_buffer" | "other";
export type AllocationPriorityChannelGroup = "direct" | "ota" | "company";
export const HOUSEKEEPING_CHECKLIST_ITEM_CODES = [
  "change_sheets",
  "clean_bathroom",
  "replenish_towels",
  "empty_waste",
  "check_amenities"
] as const;
export type HousekeepingChecklistItemCode = (typeof HOUSEKEEPING_CHECKLIST_ITEM_CODES)[number];
export type HousekeepingChecklistItem = {
  code: HousekeepingChecklistItemCode;
  label: string;
  completed: boolean;
  completed_at: string | null;
};
export type HousekeepingChecklist = {
  checklist_id: number;
  room: {
    id: number;
    number: string;
    operational_status: RoomStatus;
    housekeeping_status: HousekeepingStatus;
  };
  status: "open" | "completed";
  version: number;
  created_at: string;
  completed_at: string | null;
  items: HousekeepingChecklistItem[];
};
export type OpenHousekeepingChecklistsResponse = { checklists: HousekeepingChecklist[] };
export type HousekeepingBoardRoom = {
  room_id: number;
  room_number: string;
  floor: number;
  category_name: string;
  operational_status: RoomStatus;
  housekeeping_status: HousekeepingStatus;
  has_arrival_today: boolean;
  has_departure_today: boolean;
  has_stayover_today: boolean;
  maintenance_blocked: boolean;
  active_block_reasons: RoomBlockReason[];
};
export type HousekeepingBoard = { date: string; rooms: HousekeepingBoardRoom[] };

export type RoomCategory = {
  id: number;
  name: string;
  code: string;
  description?: string | null;
  base_price_per_night: number;
  /** Today's effective nightly rate from the single source of truth (Tarifas/daily_rate). */
  current_rate?: number | null;
  current_rate_source?: "daily_rate" | "price_period" | "category_base" | "none" | null;
  max_occupancy: number;
  amenities?: string | null;
};

export type Room = {
  id: number;
  room_number: string;
  floor: number;
  category_id: number;
  status: RoomStatus;
  housekeeping_status: HousekeepingStatus;
  is_active: boolean;
  allocation_priority_channel_groups: AllocationPriorityChannelGroup[];
  allocation_priority_company_ids: number[];
  notes?: string | null;
  category?: RoomCategory | null;
};

export type RoomDeleteBlockingReservation = {
  id: number;
  confirmation_code: string;
  guest_name: string;
  check_in_date: string;
  check_out_date: string;
  status: string;
  /** Source category used by the reservation room-move permission classifier. */
  category_id: number;
  version: number;
};

export type RoomDeleteBlockedDetail = {
  message: string;
  reservations: RoomDeleteBlockingReservation[];
};

export const listRooms = (session?: SessionLike) => apiFetch<Room[]>("/api/rooms/", { session });

export const getHousekeepingBoard = (session?: SessionLike) =>
  apiFetch<HousekeepingBoard>("/api/rooms/housekeeping-board", { session });

export const getOpenHousekeepingChecklists = (session?: SessionLike) =>
  apiFetch<OpenHousekeepingChecklistsResponse>("/api/housekeeping/checklists", { session });

export const completeHousekeepingChecklistItem = (
  checklistId: number,
  itemCode: HousekeepingChecklistItemCode,
  session?: SessionLike
) => apiFetch<HousekeepingChecklist>(
  `/api/housekeeping/checklists/${checklistId}/items/${encodeURIComponent(itemCode)}/complete`,
  { method: "POST", session }
);

export const listRoomCategories = (session?: SessionLike) =>
  apiFetch<RoomCategory[]>("/api/rooms/categories", { session });

export const createRoomCategory = (category: Omit<RoomCategory, "id">, session?: SessionLike) =>
  apiFetch<RoomCategory>("/api/rooms/categories", { method: "POST", data: category, session });

export const updateRoomCategory = (
  categoryId: number,
  category: Partial<Omit<RoomCategory, "id">>,
  session?: SessionLike
) => apiFetch<RoomCategory>(`/api/rooms/categories/${categoryId}`, { method: "PATCH", data: category, session });

export const createRoom = (
  room: {
    room_number: string;
    floor: number;
    category_id: number;
    status?: RoomStatus;
    is_active?: boolean;
    notes?: string;
    allocation_priority_channel_groups?: AllocationPriorityChannelGroup[];
    allocation_priority_company_ids?: number[];
  },
  session?: SessionLike
) => apiFetch<Room>("/api/rooms/", { method: "POST", data: room, session });

export const updateRoom = (
  roomId: number,
  room: Partial<{
    room_number: string;
    floor: number;
    category_id: number;
    status: RoomStatus;
    is_active: boolean;
    notes: string;
    allocation_priority_channel_groups: AllocationPriorityChannelGroup[];
    allocation_priority_company_ids: number[];
  }>,
  session?: SessionLike
) => apiFetch<Room>(`/api/rooms/${roomId}`, { method: "PATCH", data: room, session });

export const deleteRoom = (roomId: number, session?: SessionLike) =>
  apiFetch<void>(`/api/rooms/${roomId}`, { method: "DELETE", session });

export const updateRoomStatus = (roomId: number, status: RoomStatus, notes?: string, session?: SessionLike) =>
  apiFetch(`/api/rooms/${roomId}/status`, {
    method: "PATCH",
    data: { status, notes },
    session
  });

export const updateRoomCleaningStatus = (
  roomId: number,
  status: HousekeepingStatus,
  notes?: string,
  session?: SessionLike
) =>
  apiFetch<{ room: Room; reallocation: null }>(`/api/rooms/${roomId}/cleaning-status`, {
    method: "PATCH",
    data: { status, notes: notes ?? null },
    session
  });

export type RoomAvailabilityResponse =
  | {
      status: "placeholder";
      available_rooms: number[];
      message: string;
    }
  | {
      status: "ok";
      count: number;
      available_rooms: number[];
    };

export const checkRoomAvailability = (
  params: { category_id: number; check_in_date: string; check_out_date: string },
  session?: SessionLike
) => {
  const search = new URLSearchParams({
    category_id: String(params.category_id),
    check_in_date: params.check_in_date,
    check_out_date: params.check_out_date
  });
  return apiFetch<RoomAvailabilityResponse>(`/api/rooms/availability?${search.toString()}`, { session });
};

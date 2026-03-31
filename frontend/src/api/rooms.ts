import { apiFetch, type SessionLike } from "./client";

export type RoomStatus = "available" | "occupied" | "maintenance" | "blocked" | "cleaning";

export type RoomCategory = {
  id: number;
  name: string;
  code: string;
  description?: string | null;
  base_price_per_night: number;
  max_occupancy: number;
  amenities?: string | null;
};

export type Room = {
  id: number;
  room_number: string;
  floor: number;
  category_id: number;
  status: RoomStatus;
  is_active: boolean;
  notes?: string | null;
  category?: RoomCategory | null;
};

export const listRooms = (session?: SessionLike) => apiFetch<Room[]>("/api/rooms", { session });

export const listRoomCategories = (session?: SessionLike) =>
  apiFetch<RoomCategory[]>("/api/rooms/categories", { session });

export const updateRoomStatus = (roomId: number, status: RoomStatus, notes?: string, session?: SessionLike) =>
  apiFetch(`/api/rooms/${roomId}/status`, {
    method: "PATCH",
    data: { status, notes },
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

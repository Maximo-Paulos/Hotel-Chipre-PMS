import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listRoomCategories, listRooms, updateRoomStatus, type Room, type RoomCategory, type RoomStatus } from "../api/rooms";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const roomsKey = (hotelId: number | null) => ["rooms", hotelId];
const categoriesKey = (hotelId: number | null) => ["room-categories", hotelId];

export function useRooms() {
  const { session } = useSession();

  const roomsQuery = useQuery<Room[]>({
    queryKey: roomsKey(session.hotelId),
    queryFn: () => listRooms(session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15
  });

  const categoriesQuery = useQuery<RoomCategory[]>({
    queryKey: categoriesKey(session.hotelId),
    queryFn: () => listRoomCategories(session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 60
  });

  const queryClient = useQueryClient();

  const updateStatusMutation = useMutation({
    mutationFn: ({ roomId, status, notes }: { roomId: number; status: RoomStatus; notes?: string }) =>
      updateRoomStatus(roomId, status, notes, session),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: roomsKey(session.hotelId) });
    }
  });

  return { roomsQuery, categoriesQuery, updateStatusMutation };
}

export const roomStatusLabel: Record<RoomStatus, string> = {
  available: "Libre",
  occupied: "Ocupada",
  cleaning: "Limpieza",
  maintenance: "Mantenimiento",
  blocked: "Bloqueada"
};

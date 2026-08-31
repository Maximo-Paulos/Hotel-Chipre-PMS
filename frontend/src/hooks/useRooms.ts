import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listRoomCategories, listRooms, updateRoomCleaningStatus, updateRoomStatus, type Room, type RoomCategory, type RoomStatus } from "../api/rooms";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";
import { queryKeys } from "../api/queryKeys";
import { refreshRoomState } from "../api/queryInvalidation";

import { useGuardedMutation } from "./useGuardedMutation";

export function useRooms(options?: { includeCategories?: boolean }) {
  const { session } = useSession();

  const roomsQuery = useQuery<Room[]>({
    queryKey: queryKeys.rooms(session.hotelId),
    queryFn: () => listRooms(session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15
  });

  const categoriesQuery = useQuery<RoomCategory[]>({
    queryKey: queryKeys.roomCategories(session.hotelId),
    queryFn: () => listRoomCategories(session),
    enabled: hasValidSession(session) && (options?.includeCategories ?? true),
    staleTime: 1000 * 60
  });

  const queryClient = useQueryClient();

  const updateStatusMutation = useGuardedMutation({
    mutationFn: ({ roomId, status, notes }: { roomId: number; status: RoomStatus; notes?: string }) =>
      updateRoomStatus(roomId, status, notes, session),
    onSuccess: async (_, variables) => refreshRoomState(queryClient, session.hotelId, variables.roomId)
  });

  const updateCleaningStatusMutation = useGuardedMutation({
    mutationFn: ({ roomId, status, notes }: { roomId: number; status: "cleaning" | "available"; notes?: string }) =>
      updateRoomCleaningStatus(roomId, status, notes, session),
    onSuccess: async (_, variables) => refreshRoomState(queryClient, session.hotelId, variables.roomId)
  });

  return { roomsQuery, categoriesQuery, updateStatusMutation, updateCleaningStatusMutation };
}

export const roomStatusLabel: Record<RoomStatus, string> = {
  available: "Libre",
  occupied: "Ocupada",
  cleaning: "Limpieza",
  maintenance: "Mantenimiento",
  blocked: "Bloqueada"
};

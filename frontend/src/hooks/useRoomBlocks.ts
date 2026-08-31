import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createRoomBlock,
  listActiveRoomBlocks,
  resolveRoomBlock,
  type RoomBlock,
  type RoomBlockCreatePayload,
  type RoomBlockReasonCode
} from "../api/roomBlocks";
import { hasValidSession } from "../api/client";
import { refreshRoomState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const roomBlocksKey = (hotelId: number | null) => ["room-blocks", hotelId];

export const roomBlockReasonLabel: Record<RoomBlockReasonCode, string> = {
  maintenance: "Mantenimiento",
  deep_cleaning: "Limpieza profunda",
  owner_use: "Uso del propietario",
  vip_hold: "Reserva VIP",
  overbooking_buffer: "Margen por sobreventa",
  other: "Otro"
};

export const roomBlockReasonOptions = Object.keys(roomBlockReasonLabel) as RoomBlockReasonCode[];

export function useRoomBlocks(options?: { enabled?: boolean }) {
  const { session } = useSession();
  const queryClient = useQueryClient();

  const blocksQuery = useQuery<RoomBlock[]>({
    queryKey: roomBlocksKey(session.hotelId),
    queryFn: () => listActiveRoomBlocks({}, session),
    enabled: hasValidSession(session) && (options?.enabled ?? true),
    staleTime: 1000 * 15
  });

  const invalidate = () => refreshRoomState(queryClient, session.hotelId);

  const createBlockMutation = useGuardedMutation({
    mutationFn: (payload: RoomBlockCreatePayload) => createRoomBlock(payload, session),
    onSuccess: async () => invalidate()
  });

  const resolveBlockMutation = useGuardedMutation({
    mutationFn: (blockId: number) => resolveRoomBlock(blockId, session),
    onSuccess: async () => invalidate()
  });

  return { blocksQuery, createBlockMutation, resolveBlockMutation };
}

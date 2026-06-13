import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createRoomBlock,
  listActiveRoomBlocks,
  resolveRoomBlock,
  type RoomBlock,
  type RoomBlockCreatePayload,
  type RoomBlockReasonCode
} from "../api/roomBlocks";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

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

export function useRoomBlocks() {
  const { session } = useSession();
  const queryClient = useQueryClient();

  const blocksQuery = useQuery<RoomBlock[]>({
    queryKey: roomBlocksKey(session.hotelId),
    queryFn: () => listActiveRoomBlocks({}, session),
    enabled: hasValidSession(session),
    staleTime: 1000 * 15
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: roomBlocksKey(session.hotelId) });
    queryClient.invalidateQueries({ queryKey: ["rooms", session.hotelId] });
  };

  const createBlockMutation = useMutation({
    mutationFn: (payload: RoomBlockCreatePayload) => createRoomBlock(payload, session),
    onSuccess: invalidate
  });

  const resolveBlockMutation = useMutation({
    mutationFn: (blockId: number) => resolveRoomBlock(blockId, session),
    onSuccess: invalidate
  });

  return { blocksQuery, createBlockMutation, resolveBlockMutation };
}

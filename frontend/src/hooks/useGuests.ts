import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createGuest,
  getGuest,
  listGuests,
  updateGuest,
  type Guest,
  type GuestPayload,
  type GuestUpdatePayload
} from "../api/guests";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const guestsKey = (hotelId: number | null, search: string) => ["guests", hotelId, search];

export function useGuestCreate() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  return useMutation({
    mutationFn: (payload: GuestPayload) => createGuest(payload, session),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["guests", session.hotelId] });
    }
  });
}

export function useGuests(search = "") {
  const { session } = useSession();
  return useQuery<Guest[]>({
    queryKey: guestsKey(session.hotelId, search),
    queryFn: () => listGuests(search, session),
    enabled: hasValidSession(session),
    staleTime: 60 * 1000
  });
}

export function useGuest(guestId?: number) {
  const { session } = useSession();
  return useQuery<Guest>({
    queryKey: guestId ? ["guest", session.hotelId, guestId] : ["guest", "none"],
    queryFn: () => getGuest(guestId!, session),
    enabled: Boolean(guestId) && hasValidSession(session),
    staleTime: 5 * 60 * 1000
  });
}

export function useGuestUpdate() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  return useMutation({
    mutationFn: ({ guestId, payload }: { guestId: number; payload: GuestUpdatePayload }) =>
      updateGuest(guestId, payload, session),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["guests", session.hotelId] });
      queryClient.invalidateQueries({ queryKey: ["guest", session.hotelId, variables.guestId] });
    }
  });
}

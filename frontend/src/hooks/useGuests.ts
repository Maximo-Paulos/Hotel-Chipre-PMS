import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addGuestCompanions,
  createGuest,
  getGuest,
  listGuests,
  updateGuest,
  type Guest,
  type GuestCompanionPayload,
  type GuestPayload,
  type GuestUpdatePayload
} from "../api/guests";
import { hasValidSession } from "../api/client";
import { refreshGuestState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

// A5: page size mirrors the backend default (app/api/guests.py:117) so a
// full page reliably means "there may be a next one" for the UI's has-more
// heuristic (see GuestsPage.tsx).
export const GUEST_PAGE_SIZE = 50;

const guestsKey = (hotelId: number | null, search: string, page: number) => ["guests", hotelId, search, page];

export function useGuestCreate() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (payload: GuestPayload) => createGuest(payload, session),
    onSuccess: async () => refreshGuestState(queryClient, session.hotelId)
  });
}

export function useGuests(search = "", page = 0) {
  const { session } = useSession();
  return useQuery<Guest[]>({
    queryKey: guestsKey(session.hotelId, search, page),
    queryFn: () => listGuests({ search, skip: page * GUEST_PAGE_SIZE, limit: GUEST_PAGE_SIZE }, session),
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
  return useGuardedMutation({
    mutationFn: ({ guestId, payload }: { guestId: number; payload: GuestUpdatePayload }) =>
      updateGuest(guestId, payload, session),
    onSuccess: async (_, variables) => {
      // Keep the mutation pending until the refreshed guest data is rendered.
      // GuestsPage resets its form feedback when the selected record changes;
      // awaiting the central domain refresh prevents a success message from
      // being shown while the list/detail still contain the previous guest.
      await refreshGuestState(queryClient, session.hotelId, variables.guestId);
    }
  });
}

export function useGuestCompanionAdd() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: ({ guestId, companions }: { guestId: number; companions: GuestCompanionPayload[] }) =>
      addGuestCompanions(guestId, companions, session),
    onSuccess: async (_, variables) => refreshGuestState(queryClient, session.hotelId, variables.guestId)
  });
}

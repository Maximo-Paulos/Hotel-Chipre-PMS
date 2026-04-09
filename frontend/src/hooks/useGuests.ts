import { useMutation } from "@tanstack/react-query";

import { createGuest, getGuest, type Guest, type GuestPayload } from "../api/guests";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";
import { useQuery } from "@tanstack/react-query";

export function useGuestCreate() {
  const { session } = useSession();
  return useMutation({
    mutationFn: (payload: GuestPayload) => createGuest(payload, session)
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

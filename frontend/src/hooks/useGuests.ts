import { useMutation } from "@tanstack/react-query";

import { createGuest, type GuestPayload } from "../api/guests";
import { useSession } from "../state/session";

export function useGuestCreate() {
  const { session } = useSession();
  return useMutation({
    mutationFn: (payload: GuestPayload) => createGuest(payload, session)
  });
}

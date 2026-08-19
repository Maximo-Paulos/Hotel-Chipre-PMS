import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createGuestRestriction,
  listGuestRestrictions,
  resolveGuestRestriction,
  type GuestRestriction,
  type GuestRestrictionCreatePayload,
  type GuestRestrictionResolvePayload
} from "../api/guestRestrictions";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

import { useEffectivePermissions } from "./usePermissions";

const guestRestrictionsKey = (hotelId: number | null, guestId: number, activeOnly: boolean) => [
  "guest-restrictions",
  hotelId,
  guestId,
  activeOnly
];

// Gated on guest:prohibition_read/manage so the query never fires for an
// actor who lacks permission to see restriction data -- matches
// PermissionGate's contract of no query, no data, no flash for unauthorized
// actors. A 403 from an actor whose permission changed mid-session is
// swallowed (retry: false) so callers can just treat "no data" as "don't
// show the indicator", per the frontend task's instructions.
export function useGuestActiveRestrictions(guestId?: number, activeOnly = true) {
  const { session } = useSession();
  const { hasAnyPermission, permissionsKnown } = useEffectivePermissions();
  const canRead = permissionsKnown && hasAnyPermission(["guest:prohibition_read", "guest:prohibition_manage"]);

  return useQuery<GuestRestriction[]>({
    queryKey: guestId ? guestRestrictionsKey(session.hotelId, guestId, activeOnly) : ["guest-restrictions", "none"],
    queryFn: () => listGuestRestrictions(guestId!, activeOnly, session),
    enabled: Boolean(guestId) && hasValidSession(session) && canRead,
    staleTime: 30 * 1000,
    retry: false
  });
}

export function useGuestRestrictionMutations(guestId?: number) {
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidate = () => {
    if (!guestId) return;
    queryClient.invalidateQueries({ queryKey: ["guest-restrictions", session.hotelId, guestId] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: GuestRestrictionCreatePayload) => createGuestRestriction(guestId!, payload, session),
    onSuccess: invalidate
  });

  const resolveMutation = useMutation({
    mutationFn: ({ restrictionId, payload }: { restrictionId: number; payload: GuestRestrictionResolvePayload }) =>
      resolveGuestRestriction(guestId!, restrictionId, payload, session),
    onSuccess: invalidate
  });

  return { createMutation, resolveMutation };
}

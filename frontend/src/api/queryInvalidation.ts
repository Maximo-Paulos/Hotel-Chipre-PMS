import type { QueryClient } from "@tanstack/react-query";

import {
  HOTEL_ID_INDEX_BY_QUERY_PREFIX,
  QUERY_PREFIXES_BY_DOMAIN,
  hotelIdForQueryKey,
  type QueryDomain
} from "./queryKeys";

/**
 * Invalidate every active query affected by a committed mutation and wait for
 * its refetch. Inactive queries are marked stale and will reconcile when the
 * user opens them. The predicate deliberately requires a known tenant index;
 * an unscoped operational key is never allowed to cross tenant boundaries.
 */
export async function refreshAfterMutation(
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  domains: readonly QueryDomain[]
): Promise<void> {
  if (!hotelId || !Number.isInteger(hotelId) || hotelId <= 0 || domains.length === 0) return;

  const prefixes = new Set(domains.flatMap((domain) => QUERY_PREFIXES_BY_DOMAIN[domain]));
  await queryClient.invalidateQueries({
    predicate: (query) => {
      const prefix = query.queryKey[0];
      if (typeof prefix !== "string" || !prefixes.has(prefix)) return false;
      const hotelIndex = HOTEL_ID_INDEX_BY_QUERY_PREFIX[prefix];
      return hotelIndex !== undefined && query.queryKey[hotelIndex] === hotelId;
    },
    // A mutation is only considered complete by the UI after active views have
    // received the authoritative server representation.
    refetchType: "active"
  });
}

export const refreshReservationState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  reservationId?: number
) => {
  void reservationId;
  return refreshAfterMutation(queryClient, hotelId, ["reservations", "payments", "cash", "analytics", "rooms"]);
};

export const refreshPaymentState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  reservationId?: number
) => refreshReservationState(queryClient, hotelId, reservationId);

export const refreshGuestState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  guestId?: number
) => {
  void guestId;
  return refreshAfterMutation(queryClient, hotelId, ["guests", "reservations", "analytics"]);
};

export const refreshCashState = (queryClient: QueryClient, hotelId: number | null | undefined) =>
  refreshAfterMutation(queryClient, hotelId, ["cash", "payments", "analytics"]);

export const refreshRoomState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  roomId?: number
) => {
  void roomId;
  return refreshAfterMutation(queryClient, hotelId, ["rooms", "reservations", "analytics"]);
};

export const refreshStockState = (queryClient: QueryClient, hotelId: number | null | undefined) =>
  refreshAfterMutation(queryClient, hotelId, ["stock", "analytics"]);

export const refreshSettingsState = (queryClient: QueryClient, hotelId: number | null | undefined) =>
  refreshAfterMutation(queryClient, hotelId, ["settings", "security", "analytics"]);

export const refreshUserState = (queryClient: QueryClient, hotelId: number | null | undefined) =>
  refreshAfterMutation(queryClient, hotelId, ["users", "security", "settings"]);

/** Used by the SSE/BroadcastChannel consumers after a reconnect or event. */
export const refreshDomains = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  domains: readonly QueryDomain[]
) => refreshAfterMutation(queryClient, hotelId, domains);

/** Guard used by tests and future callers when deciding whether a key is safe. */
export const queryBelongsToHotel = (queryKey: readonly unknown[], hotelId: number) =>
  hotelIdForQueryKey(queryKey) === hotelId;

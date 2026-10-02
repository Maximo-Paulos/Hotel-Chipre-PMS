import type { QueryClient } from "@tanstack/react-query";

import {
  HOTEL_ID_INDEX_BY_QUERY_PREFIX,
  QUERY_PREFIXES_BY_DOMAIN,
  hotelIdForQueryKey,
  type QueryDomain
} from "./queryKeys";

const RESERVATION_QUERY_PREFIXES = new Set([
  "reservations",
  "reservation",
  "reservation-operations",
  "reservation-pending-actions",
  "occupancy-grid",
  "waitlist"
]);

const PAYMENT_QUERY_PREFIXES = new Set(["payment-summary", "payment-links", "payment-proofs"]);
const CASH_QUERY_PREFIXES = new Set([
  "cash-sessions",
  "cash-movements",
  "cash-summary",
  "cash-daily-summary",
  "cash-latest-close-report"
]);
const RESERVATION_ENTITY_QUERY_PREFIXES = new Set([
  "reservation",
  "reservation-operations",
  "payment-summary",
  "payment-links",
  "payment-proofs"
]);
const GUEST_QUERY_PREFIXES = new Set([
  "guests",
  "guest",
  "guest-tags",
  "guest-quick-profile",
  "guest-search",
  "guest-restriction-summary",
  "guest-restrictions",
  "guest-checkin-validation"
]);
const ROOM_QUERY_PREFIXES = new Set(["rooms", "housekeeping-board", "room-state-events"]);
type ReservationRecordRefreshOptions = {
  includePaymentSummary?: boolean;
  includePaymentLinks?: boolean;
};

/**
 * Invalidate every active query affected by a committed mutation and wait for
 * its refetch to settle. Inactive queries are marked stale and reconcile when
 * opened. A refetch failure retains the last data but does not roll back the
 * committed mutation. The predicate requires a known tenant index so an
 * unscoped operational key cannot cross tenant boundaries.
 */
export async function refreshAfterMutation(
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  domains: readonly QueryDomain[]
): Promise<void> {
  if (!hotelId || !Number.isInteger(hotelId) || hotelId <= 0 || domains.length === 0) return;

  const prefixes = new Set(domains.flatMap((domain) => QUERY_PREFIXES_BY_DOMAIN[domain]));
  await refreshHotelQueriesByPrefix(queryClient, hotelId, prefixes);
}

const refreshHotelQueriesByPrefix = async (
  queryClient: QueryClient,
  hotelId: number,
  prefixes: ReadonlySet<string>
): Promise<void> => {
  await refreshHotelQueries(queryClient, hotelId, (queryKey) => {
    const prefix = queryKey[0];
    return typeof prefix === "string" && prefixes.has(prefix);
  });
};

const refreshHotelQueries = async (
  queryClient: QueryClient,
  hotelId: number,
  matches: (queryKey: readonly unknown[]) => boolean
): Promise<void> => {
  await queryClient.invalidateQueries({
    predicate: (query) => {
      const prefix = query.queryKey[0];
      if (typeof prefix !== "string" || !matches(query.queryKey)) return false;
      const hotelIndex = HOTEL_ID_INDEX_BY_QUERY_PREFIX[prefix];
      return hotelIndex !== undefined && query.queryKey[hotelIndex] === hotelId;
    },
    // Wait for active views to reconcile after the committed write.
    refetchType: "active"
  }, {
    // A committed mutation stays committed even if one active cache refetch
    // has a transient network error. TanStack keeps the last successful data.
    throwOnError: false
  });
};

const validHotelId = (hotelId: number | null | undefined): hotelId is number =>
  Boolean(hotelId && Number.isInteger(hotelId) && hotelId > 0);

const refreshReservationQueries = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  options: {
    reservationId?: number;
    includePayments?: boolean;
    includeCash?: boolean;
    includeGuests?: boolean;
    includeRooms?: boolean;
    includePaymentSummary?: boolean;
    includePaymentLinks?: boolean;
  } = {}
) => {
  if (!validHotelId(hotelId)) return Promise.resolve();
  if (
    (options.includePaymentSummary || options.includePaymentLinks)
    && (!options.reservationId || !Number.isInteger(options.reservationId) || options.reservationId <= 0)
  ) return Promise.resolve();
  const prefixes = new Set(RESERVATION_QUERY_PREFIXES);
  if (options.includePayments) PAYMENT_QUERY_PREFIXES.forEach((prefix) => prefixes.add(prefix));
  if (options.includeCash) CASH_QUERY_PREFIXES.forEach((prefix) => prefixes.add(prefix));
  if (options.includeGuests) GUEST_QUERY_PREFIXES.forEach((prefix) => prefixes.add(prefix));
  if (options.includeRooms) ROOM_QUERY_PREFIXES.forEach((prefix) => prefixes.add(prefix));
  if (options.includePaymentSummary) prefixes.add("payment-summary");
  if (options.includePaymentLinks) prefixes.add("payment-links");

  return refreshHotelQueries(queryClient, hotelId, (queryKey) => {
    const prefix = queryKey[0];
    if (typeof prefix !== "string" || !prefixes.has(prefix)) return false;
    if (options.reservationId && RESERVATION_ENTITY_QUERY_PREFIXES.has(prefix)) {
      return queryKey[2] === options.reservationId;
    }
    return true;
  });
};

/** Refresh reservation-facing caches without involving payments or cash. */
export const refreshReservationRecordState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  reservationId?: number,
  options: ReservationRecordRefreshOptions = {}
) => refreshReservationQueries(queryClient, hotelId, { reservationId, ...options });

/** A new booking changes reservation lists, pending actions, and occupancy.
 * It does not create a room-movement group, payment, or cash movement. */
export const refreshReservationCreatedState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined
) => {
  if (!hotelId || !Number.isInteger(hotelId) || hotelId <= 0) return Promise.resolve();
  return refreshHotelQueriesByPrefix(
    queryClient,
    hotelId,
    new Set(["reservations", "reservation-pending-actions", "occupancy-grid"])
  );
};

export const refreshReservationState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  reservationId?: number
) => refreshReservationQueries(queryClient, hotelId, { reservationId, includePayments: true, includeCash: true });

/**
 * Check-in (full or partial) also saves the guest data captured in the drawer,
 * and companions are guest records, so the guests domain changes with the
 * stay. Without it the drawer's guest-checkin-validation stays stale and keeps
 * asking for data that was just saved.
 */
export const refreshReservationGuestState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  reservationId?: number
) => refreshReservationQueries(queryClient, hotelId, { reservationId, includeGuests: true, includeRooms: true });

export const refreshPaymentState = (
  queryClient: QueryClient,
  hotelId: number | null | undefined,
  reservationId?: number
) => refreshReservationQueries(queryClient, hotelId, { reservationId, includePayments: true, includeCash: true });

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
) => {
  if (!validHotelId(hotelId) || domains.length === 0) return Promise.resolve();
  const prefixes = new Set(domains.flatMap((domain) => QUERY_PREFIXES_BY_DOMAIN[domain]));
  return refreshHotelQueries(
    queryClient,
    hotelId,
    (queryKey) => {
      const prefix = queryKey[0];
      return typeof prefix === "string" && prefixes.has(prefix);
    }
  );
};

/** Select bootstrap/recovery domains, including bounded fallbacks for gaps. */
export const recoveryDomainsForCursor = (
  currentCursor: number,
  payload: { domains?: readonly string[]; reset_required?: boolean; has_more?: boolean }
): QueryDomain[] => {
  if (!Number.isSafeInteger(currentCursor) || currentCursor < 0) return [];
  const allDomains = Object.keys(QUERY_PREFIXES_BY_DOMAIN) as QueryDomain[];
  const knownDomains = new Set(Object.keys(QUERY_PREFIXES_BY_DOMAIN));
  const changedDomains = (payload.domains ?? []).filter((domain): domain is QueryDomain => knownDomains.has(domain));
  // Cursor 0 is a normal bootstrap, not evidence of a missed historical gap.
  // Reconcile only reported domains unless the bounded sweep was truncated.
  if (currentCursor === 0 && payload.has_more) return allDomains;
  if (currentCursor === 0) return changedDomains;
  if (payload.reset_required) return allDomains;
  return changedDomains;
};

/** Guard used by tests and future callers when deciding whether a key is safe. */
export const queryBelongsToHotel = (queryKey: readonly unknown[], hotelId: number) =>
  hotelIdForQueryKey(queryKey) === hotelId;

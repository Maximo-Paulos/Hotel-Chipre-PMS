import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = async (path) => readFile(new URL(path, import.meta.url), "utf8");

test("room category consumers share one hotel-scoped query key", async () => {
  const [keys, rooms, categories] = await Promise.all([
    source("./src/api/queryKeys.ts"),
    source("./src/hooks/useRooms.ts"),
    source("./src/hooks/useCategories.ts")
  ]);

  assert.match(keys, /const roomCategoriesKey = .*\["room-categories", hotelId\]/);
  assert.match(keys, /categories: roomCategoriesKey/);
  assert.match(rooms, /queryKey: queryKeys\.roomCategories\(session\.hotelId\)/);
  assert.match(categories, /queryKey: queryKeys\.roomCategories\(session\.hotelId\)/);
});

test("reservation mutations avoid refreshing unrelated room and analytics domains", async () => {
  const invalidation = await source("./src/api/queryInvalidation.ts");
  const reservationRefresh = invalidation.match(/export const refreshReservationState = \([\s\S]*?\n\};/)?.[0];

  assert.ok(reservationRefresh, "refreshReservationState must remain defined");
  assert.match(reservationRefresh, /\["reservations", "payments", "cash"\]/);
  assert.doesNotMatch(reservationRefresh, /"rooms"|"analytics"/);
  assert.match(invalidation, /\["reservations", "payments", "cash", "analytics"\]/);
});

test("reservation creation does not refetch cash sessions when no payment was recorded", async () => {
  const invalidation = await source("./src/api/queryInvalidation.ts");
  const reservations = await source("./src/hooks/useReservations.ts");
  const mutations = reservations.match(/export function useReservationMutations[\s\S]*?\n\}/)?.[0];

  assert.ok(mutations, "useReservationMutations must remain defined");
  const creationRefresh = invalidation.match(/export const refreshReservationCreatedState = \([\s\S]*?\n\};/)?.[0];
  assert.ok(creationRefresh, "reservation creation invalidation must remain defined");
  assert.match(creationRefresh, /"reservations", "reservation-pending-actions", "occupancy-grid"/);
  assert.doesNotMatch(creationRefresh, /cash|room-movement-groups/);
  assert.match(mutations, /invalidateCreatedReservation = \(\) =>\s*refreshReservationCreatedState\(queryClient, session\.hotelId\)/);
  const createMutation = mutations.match(/const createMutation = useGuardedMutation\(\{[\s\S]*?\n  \}\);/)?.[0];
  const createOtaMutation = mutations.match(/const createManualOtaMutation = useGuardedMutation\(\{[\s\S]*?\n  \}\);/)?.[0];

  assert.match(createMutation ?? "", /onSuccess: async \(\) => invalidateCreatedReservation\(\)/);
  assert.match(createOtaMutation ?? "", /onSuccess: async \(\) => invalidateCreatedReservation\(\)/);
});

test("slow-changing reference data uses a five-minute cache window", async () => {
  const [rooms, permissions] = await Promise.all([
    source("./src/hooks/useRooms.ts"),
    source("./src/hooks/usePermissions.ts")
  ]);

  assert.match(rooms, /staleTime: 5 \* 60 \* 1000/);
  assert.match(permissions, /staleTime: 5 \* 60 \* 1000/);
});

test("reservation quotes stay fresh for 30 seconds", async () => {
  const reservations = await source("./src/hooks/useReservations.ts");
  const quoteHook = reservations.match(/export function useReservationQuote[\s\S]*?\n\}/)?.[0];

  assert.ok(quoteHook, "useReservationQuote must remain defined");
  assert.match(quoteHook, /staleTime: 30 \* 1000/);
});

test("realtime recovery does not invalidate every domain on a first connection", async () => {
  const sync = await source("./src/sync/crossTabSync.ts");

  assert.match(sync, /payload\.reset_required && currentCursor > 0/);
  assert.match(sync, /\}, 1000\);/);
});

test("subscription and hotel configuration queries require their read permissions", async () => {
  const [subscription, config] = await Promise.all([
    source("./src/hooks/useSubscription.ts"),
    source("./src/hooks/useHotelConfig.ts")
  ]);

  assert.match(subscription, /hasPermission\("settings:subscription:view"\)/);
  assert.match(subscription, /\["subscription", session\.hotelId \?\? "none", session\.userId \?\? "none"\]/);
  assert.match(config, /hasPermission\("hotel_settings:read"\)/);
  assert.match(config, /hotelConfigKey\(session\.hotelId, session\.userId\)/);
});

test("a transient refresh error only clears the session after an explicit 401", async () => {
  const session = await source("./src/state/session.tsx");
  const refreshCatch = session.match(/void refreshSession\(\)[\s\S]*?\.catch\(\(error: unknown\) => \{([\s\S]*?)\n      \}\)/)?.[1];

  assert.ok(refreshCatch, "session restoration must handle refresh failures");
  assert.match(refreshCatch, /error instanceof ApiError && error\.status === 401/);
  assert.equal((refreshCatch.match(/setSession\(EMPTY_SESSION\)/g) ?? []).length, 1);
});

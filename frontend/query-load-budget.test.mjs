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
  assert.doesNotMatch(keys, /categories:\s*roomCategoriesKey/);
  assert.match(rooms, /queryKey: queryKeys\.roomCategories\(session\.hotelId\)/);
  assert.match(categories, /queryKey: queryKeys\.roomCategories\(session\.hotelId\)/);
  assert.match(rooms, /queryFn: \(\) => listCategories\(session\)/);
  assert.match(categories, /queryFn: \(\) => listCategories\(session\)/);
});

test("reservation mutations avoid refreshing unrelated room and analytics domains", async () => {
  const invalidation = await source("./src/api/queryInvalidation.ts");
  const reservationRefreshStart = invalidation.indexOf("export const refreshReservationState = (");
  const reservationRefresh = reservationRefreshStart >= 0
    ? invalidation.slice(reservationRefreshStart, reservationRefreshStart + 260)
    : "";

  assert.ok(reservationRefresh, "refreshReservationState must remain defined");
  assert.match(reservationRefresh, /includePayments: true, includeCash: true/);
  assert.doesNotMatch(reservationRefresh, /analytics|rooms/);
  assert.match(invalidation, /const RESERVATION_QUERY_PREFIXES = new Set/);
  assert.match(invalidation, /const PAYMENT_QUERY_PREFIXES = new Set/);
  assert.match(invalidation, /const CASH_QUERY_PREFIXES = new Set/);
  assert.match(invalidation, /throwOnError: false/);
});

test("analytics events do not refetch settings, room-event, or assistant queries", async () => {
  const keys = await source("./src/api/queryKeys.ts");
  const analyticsPrefixes = keys.match(/analytics:\s*\[([\s\S]*?)\],\s*assistant:/)?.[1] ?? "";
  const assistantPrefixes = keys.match(/assistant:\s*\[([\s\S]*?)\],\s*cash:/)?.[1] ?? "";
  const sync = await source("./src/sync/crossTabSync.ts");

  assert.ok(analyticsPrefixes, "analytics domain must remain defined");
  assert.doesNotMatch(analyticsPrefixes, /companies|room-state-events|gemma/);
  assert.match(assistantPrefixes, /gemma-chat/);
  assert.match(assistantPrefixes, /gemma-insights/);
  assert.match(sync, /normalized\.includes\("gemma"\)\) return \["assistant"\]/);
});

test("reservation group summaries only fetch the six rows rendered on the page", async () => {
  const [api, page] = await Promise.all([
    source("./src/api/reservations.ts"),
    source("./src/views/protected/ReservationsPage.tsx")
  ]);

  assert.match(api, /RESERVATION_GROUP_SUMMARY_LIMIT\s*=\s*6/);
  assert.match(api, /\/api\/reservation-groups\?limit=\$\{RESERVATION_GROUP_SUMMARY_LIMIT\}/);
  assert.match(page, /data\?\.slice\(0, RESERVATION_GROUP_SUMMARY_LIMIT\)/);
});

test("reservation creation refreshes only related views without waiting for the reads", async () => {
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

  assert.match(createMutation ?? "", /onSuccess: \(\) =>\s*\{\s*void invalidateCreatedReservation\(\)\.catch\(\(\) => undefined\);\s*\}/);
  assert.match(createOtaMutation ?? "", /onSuccess: \(\) =>\s*\{\s*void invalidateCreatedReservation\(\)\.catch\(\(\) => undefined\);\s*\}/);
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
  const [sync, invalidation] = await Promise.all([
    source("./src/sync/crossTabSync.ts"),
    source("./src/api/queryInvalidation.ts")
  ]);

  assert.match(sync, /REALTIME_EVENT_DEBOUNCE_MS = 1_000/);
  assert.match(sync, /recoveryDomainsForCursor\(currentCursor, payload\)/);
  assert.match(invalidation, /if \(currentCursor === 0 && payload\.has_more\) return allDomains/);
  assert.match(invalidation, /if \(currentCursor === 0\) return changedDomains/);
  assert.match(invalidation, /if \(payload\.reset_required\) return allDomains/);
  assert.match(sync, /await refreshDomains\(queryClient, hotelId, domains\)/);
  assert.match(invalidation, /refetchType: "active"/);
  assert.doesNotMatch(sync, /activeOnly/);
  assert.doesNotMatch(invalidation, /activeOnly/);
});

test("degraded realtime recovery backs off and cannot reschedule after cleanup", async () => {
  const sync = await source("./src/sync/crossTabSync.ts");
  const recoveryPoll = sync.match(/const REALTIME_RECOVERY_POLL_MS = [\s\S]*?export type RealtimeConnectionStatus/)?.[0] ?? "";
  const recoveryEffect = sync.match(/if \(!hotelId \|\| !session\.accessToken \|\| !session\.userId \|\| realtimeStatus === "connected"[\s\S]*?\}, \[hotelId, queryClient, realtimeStatus, session\.accessToken, session\.userId\]\);/)?.[0] ?? "";

  assert.match(recoveryPoll, /REALTIME_RECOVERY_POLL_MS = 5_000/);
  assert.match(recoveryPoll, /REALTIME_RECOVERY_MAX_POLL_MS = 30_000/);
  assert.match(recoveryPoll, /Math\.min\(REALTIME_RECOVERY_MAX_POLL_MS/);
  assert.match(recoveryEffect, /recoveryFailureState\.current\.count \+= 1/);
  assert.match(recoveryEffect, /if \(stopped\) return;/);
});

test("local reservation mutations refresh their selected entity", async () => {
  const [invalidation, reservations] = await Promise.all([
    source("./src/api/queryInvalidation.ts"),
    source("./src/hooks/useReservations.ts")
  ]);

  assert.match(invalidation, /RESERVATION_ENTITY_QUERY_PREFIXES\.has\(prefix\)[\s\S]*?queryKey\[2\] === options\.reservationId/);
  assert.match(reservations, /onSuccess: async \(_, variables\) => invalidateReservationRecord\(variables\.id, \{ includePaymentSummary: true \}\)/);
  assert.match(reservations, /refreshReservationGuestState\(queryClient, session\.hotelId, reservationId\)/);
});

test("reservation mutation invalidations match their API side effects", async () => {
  const reservations = await source("./src/hooks/useReservations.ts");
  const updateMutation = reservations.match(/const updateMutation = useGuardedMutation\(\{[\s\S]*?\n  \}\);/)?.[0];
  const cancelMutation = reservations.match(/const cancelMutation = useGuardedMutation\(\{[\s\S]*?\n  \}\);/)?.[0];
  const actionMutations = reservations.match(/export function useReservationActionMutations[\s\S]*?\n\}/)?.[0];

  assert.match(updateMutation ?? "", /invalidateReservationRecord\(variables\.id, \{ includePaymentSummary: true \}\)/);
  assert.match(cancelMutation ?? "", /includePaymentSummary: true,[\s\S]*?includePaymentLinks: true/);
  assert.match(reservations, /refreshReservationRecordState\(queryClient, session\.hotelId, reservationId, options\)/);
  assert.match(actionMutations ?? "", /resolveReservationExternal[\s\S]*?includePaymentSummary: true/);
  assert.match(actionMutations ?? "", /clearReservationManualReview[\s\S]*?invalidateReservationRecord\(variables\.reservationId\)/);
  assert.match(reservations, /onSuccess: async \(_, params\) => invalidateReservationDetail\(normalizeCheckInParams\(params\)\.id\)/);
  assert.match(reservations, /onSuccess: async \(_, id\) => invalidateReservationDetail\(id\)/);
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
  const refreshCatch = session.match(/catch \(error: unknown\) \{([\s\S]*?)\n        \}/)?.[1];
  const retryableErrors = session.match(/const isRetryableSessionRestoreError =([\s\S]*?error instanceof ApiError[\s\S]*?);/)?.[1];

  assert.ok(refreshCatch, "session restoration must handle refresh failures");
  assert.match(refreshCatch, /error instanceof ApiError && error\.status === 401/);
  assert.equal((refreshCatch.match(/setSession\(EMPTY_SESSION\)/g) ?? []).length, 1);
  assert.match(refreshCatch, /isRetryableSessionRestoreError/);
  assert.match(retryableErrors ?? "", /error\.name === "AbortError"/);
  assert.match(retryableErrors ?? "", /error\.status === 408/);
});

test("WhatsApp writes refresh only the active hotel's conversations in the background", async () => {
  const crm = await source("./src/hooks/useWhatsappCRM.ts");
  const invalidation = crm.match(/const invalidate = \(\) => invalidateQueriesInBackground\(queryClient, \{[\s\S]*?\}\);/)?.[0];

  assert.ok(invalidation, "WhatsApp mutations must use a non-blocking invalidation");
  assert.match(invalidation, /queryKey: \["whatsapp", "conversations", session\.hotelId\]/);
  assert.doesNotMatch(invalidation, /queryKey: \["whatsapp"\]/);
});

test("approving a Gemma suggestion does not refresh unrelated hotel domains", async () => {
  const gemma = await source("./src/hooks/useGemmaChat.ts");
  const approveMutation = gemma.match(/const approveActionMutation = useGuardedMutation\(\{[\s\S]*?\n  \}\);/)?.[0];

  assert.ok(approveMutation, "Gemma approval mutation must remain defined");
  assert.match(approveMutation, /gemmaChatKey\(session\.hotelId, variables\.payload\.session_id\)/);
  assert.match(approveMutation, /gemmaHistoryKey\(session\.hotelId\)/);
  assert.doesNotMatch(approveMutation, /refreshAfterMutation|reservations|payments|cash|rooms|guests|stock/);
});

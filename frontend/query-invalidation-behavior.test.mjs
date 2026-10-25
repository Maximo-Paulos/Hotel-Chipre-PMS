import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "typescript";
import { QueryClient, QueryObserver } from "@tanstack/react-query";

const compileModule = async (sourceUrl, destination) => {
  const source = await readFile(sourceUrl, "utf8");
  return writeFile(
    destination,
    ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022
      }
    }).outputText
  );
};

const loadQueryModules = async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "hotel-chipre-query-cache-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const keysPath = join(directory, "queryKeys.mjs");
  const invalidationPath = join(directory, "queryInvalidation.mjs");
  await compileModule(new URL("./src/api/queryKeys.ts", import.meta.url), keysPath);
  const invalidationSource = await readFile(new URL("./src/api/queryInvalidation.ts", import.meta.url), "utf8");
  const invalidationModule = ts.transpileModule(invalidationSource, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
  }).outputText.replace('from "./queryKeys"', 'from "./queryKeys.mjs"');
  await writeFile(invalidationPath, invalidationModule);
  const cacheBust = `?test=${Math.random()}`;
  return {
    keys: await import(`${pathToFileURL(keysPath).href}${cacheBust}`),
    invalidation: await import(`${pathToFileURL(invalidationPath).href}${cacheBust}`)
  };
};

test("the room-category key has one hotel-scoped canonical prefix", async (context) => {
  const { keys } = await loadQueryModules(context);
  assert.deepEqual(keys.queryKeys.roomCategories(41), ["room-categories", 41]);
  assert.equal(keys.queryKeys.categories, undefined);
  assert.equal(keys.hotelIdForQueryKey(keys.queryKeys.roomCategories(41)), 41);
});

test("housekeeping checklists are hotel-scoped and refresh with room state", async (context) => {
  const { keys, invalidation } = await loadQueryModules(context);
  const hotelId = 41;
  const client = new QueryClient();
  const entries = [
    [keys.queryKeys.housekeepingBoard(hotelId), true],
    [keys.queryKeys.housekeepingChecklists(hotelId), true],
    [keys.queryKeys.housekeepingChecklists(hotelId + 1), false]
  ];
  entries.forEach(([key]) => client.setQueryData(key, { key }));

  assert.equal(keys.hotelIdForQueryKey(keys.queryKeys.housekeepingChecklists(hotelId)), hotelId);
  await invalidation.refreshAfterMutation(client, hotelId, ["rooms"]);

  for (const [key, shouldInvalidate] of entries) {
    assert.equal(
      client.getQueryState(key)?.isInvalidated ?? false,
      shouldInvalidate,
      `unexpected housekeeping invalidation for ${JSON.stringify(key)}`
    );
  }
  client.clear();
});

test("reservation refresh invalidates only related data and the selected entity", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const hotelId = 41;
  const selectedReservationId = 703;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const entries = [
    [["reservations", hotelId, { status: "confirmed" }], true],
    [["reservation", hotelId, selectedReservationId], true],
    [["reservation", hotelId, 704], false],
    [["reservation-operations", hotelId, selectedReservationId], true],
    [["payment-summary", hotelId, selectedReservationId], true],
    [["payment-summary", hotelId, 704], false],
    [["cash-sessions", hotelId], true],
    [["occupancy-grid", hotelId, "2026-10-01", "2026-10-07"], true],
    [["rooms", hotelId], false],
    [["room-categories", hotelId], false],
    [["reservation-quote", hotelId, 2, "2026-10-02", "2026-10-03"], false],
    [["analytics", hotelId], false],
    [["operational-audit", hotelId, {}], false],
    [["reservations", hotelId + 1, {}], false]
  ];
  entries.forEach(([key]) => client.setQueryData(key, { key }));

  await invalidation.refreshReservationState(client, hotelId, selectedReservationId);

  for (const [key, shouldInvalidate] of entries) {
    assert.equal(
      client.getQueryState(key)?.isInvalidated ?? false,
      shouldInvalidate,
      `unexpected invalidation for ${JSON.stringify(key)}`
    );
  }
  client.clear();
});

test("committed reservation mutations do not wait for active query refetches", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const queryKey = ["reservation", 41, 703];
  client.setQueryData(queryKey, { id: 703, status: "confirmed" });

  let releaseRefetch;
  let markRefetchStarted;
  const refetchStarted = new Promise((resolve) => {
    markRefetchStarted = resolve;
  });
  const observer = new QueryObserver(client, {
    queryKey,
    queryFn: () => new Promise((resolve) => {
      releaseRefetch = resolve;
      markRefetchStarted();
    }),
    staleTime: Infinity,
    retry: false
  });
  const unsubscribe = observer.subscribe(() => undefined);

  const refreshPromise = invalidation.refreshReservationRecordState(client, 41, 703);
  await refetchStarted;
  const returnedBeforeRefetch = await Promise.race([
    refreshPromise.then(() => true),
    new Promise((resolve) => setTimeout(() => resolve(false), 50))
  ]);
  releaseRefetch({ id: 703, status: "checked_in" });
  await refreshPromise;
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(returnedBeforeRefetch, true);
  assert.deepEqual(client.getQueryData(queryKey), { id: 703, status: "checked_in" });
  unsubscribe();
  client.clear();
});

test("creating a guest refreshes guest and analytics views without refetching reservations", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient();
  const entries = [
    [["guests", 41, "", 0], true],
    [["reservations", 41, { limit: 200 }], false],
    [["reservation-pending-actions", 41, 12], false],
    [["analytics", 41], true],
    [["guests", 42, "", 0], false]
  ];
  entries.forEach(([key]) => client.setQueryData(key, { key }));

  await invalidation.refreshGuestCreatedState(client, 41);

  for (const [key, shouldInvalidate] of entries) {
    assert.equal(
      client.getQueryState(key)?.isInvalidated ?? false,
      shouldInvalidate,
      `unexpected guest-create invalidation for ${JSON.stringify(key)}`
    );
  }
  client.clear();
});

test("settings refreshes notification preferences without refetching the inbox", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient();
  const entries = [
    [["notification-inbox", 41, false, 50, 0], false],
    [["notification-preferences", 41], true],
    [["daily-report-schedules", 41], true],
    [["hotel-config", 41], true]
  ];
  entries.forEach(([key]) => client.setQueryData(key, { key }));

  await invalidation.refreshAfterMutation(client, 41, ["settings"]);

  for (const [key, shouldInvalidate] of entries) {
    assert.equal(
      client.getQueryState(key)?.isInvalidated ?? false,
      shouldInvalidate,
      `unexpected settings invalidation for ${JSON.stringify(key)}`
    );
  }
  client.clear();
});

test("reservation record effects invalidate only explicitly selected financial queries", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient();
  const reservationId = 703;
  const entries = [
    [["reservations", 41, { status: "confirmed" }], true],
    [["reservation", 41, reservationId], true],
    [["reservation", 41, 704], false],
    [["reservation-operations", 41, reservationId], true],
    [["occupancy-grid", 41, "2026-10-01", "2026-10-07"], true],
    [["payment-summary", 41, reservationId], true],
    [["payment-summary", 41, 704], false],
    [["payment-links", 41, reservationId], true],
    [["payment-links", 41, 704], false],
    [["payment-proofs", 41, reservationId], false],
    [["cash-sessions", 41], false],
    [["cash-movements", 41], false],
    [["analytics", 41], false]
  ];
  entries.forEach(([key]) => client.setQueryData(key, { key }));

  await invalidation.refreshReservationRecordState(client, 41, reservationId, {
    includePaymentSummary: true,
    includePaymentLinks: true
  });

  for (const [key, shouldInvalidate] of entries) {
    assert.equal(
      client.getQueryState(key)?.isInvalidated ?? false,
      shouldInvalidate,
      `unexpected reservation-record invalidation for ${JSON.stringify(key)}`
    );
  }
  client.clear();
});

test("reservation record changes without financial projection changes skip financial and cash caches", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient();
  const reservationKey = ["reservation", 41, 703];
  const operationsKey = ["reservation-operations", 41, 703];
  const paymentSummaryKey = ["payment-summary", 41, 703];
  const paymentLinksKey = ["payment-links", 41, 703];
  const cashKey = ["cash-sessions", 41];
  [reservationKey, operationsKey, paymentSummaryKey, paymentLinksKey, cashKey].forEach((key) =>
    client.setQueryData(key, { key })
  );

  await invalidation.refreshReservationRecordState(client, 41, 703);

  assert.equal(client.getQueryState(reservationKey)?.isInvalidated, true);
  assert.equal(client.getQueryState(operationsKey)?.isInvalidated, true);
  assert.equal(client.getQueryState(paymentSummaryKey)?.isInvalidated ?? false, false);
  assert.equal(client.getQueryState(paymentLinksKey)?.isInvalidated ?? false, false);
  assert.equal(client.getQueryState(cashKey)?.isInvalidated ?? false, false);
  client.clear();
});

test("committed mutation invalidation returns while active reads reconcile in the background", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const queryKey = ["reservation", 41, 703];
  client.setQueryData(queryKey, { id: 703, total_amount: 900 });
  let releaseFetch;
  let fetchStarted = false;
  const observer = new QueryObserver(client, {
    queryKey,
    queryFn: () => {
      fetchStarted = true;
      return new Promise((resolve) => { releaseFetch = resolve; });
    },
    staleTime: Infinity,
    retry: false
  });
  const unsubscribe = observer.subscribe(() => undefined);

  await invalidation.refreshReservationRecordState(client, 41, 703);

  assert.equal(fetchStarted, true, "the active query should start reconciling immediately");
  assert.equal(client.getQueryState(queryKey)?.fetchStatus, "fetching");
  assert.deepEqual(client.getQueryData(queryKey), { id: 703, total_amount: 900 });

  releaseFetch({ id: 703, total_amount: 1200 });
  await client.getQueryCache().find({ queryKey })?.promise;
  assert.deepEqual(client.getQueryData(queryKey), { id: 703, total_amount: 1200 });

  unsubscribe();
  client.clear();
});

test("direct background invalidation starts an active refetch without returning its network promise", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const queryKey = ["housekeeping-board", 41];
  client.setQueryData(queryKey, { rooms: [{ id: 2, housekeeping_status: "dirty" }] });
  let releaseFetch;
  let fetchStarted = false;
  const observer = new QueryObserver(client, {
    queryKey,
    queryFn: () => {
      fetchStarted = true;
      return new Promise((resolve) => { releaseFetch = resolve; });
    },
    staleTime: Infinity,
    retry: false
  });
  const unsubscribe = observer.subscribe(() => undefined);

  const result = invalidation.invalidateQueriesInBackground(client, { queryKey });

  assert.equal(result, undefined, "mutation success should not inherit the active read promise");
  assert.equal(fetchStarted, true, "the active query should still reconcile immediately");
  assert.equal(client.getQueryState(queryKey)?.fetchStatus, "fetching");
  assert.equal(client.getQueryState(queryKey)?.isInvalidated, true);

  releaseFetch({ rooms: [{ id: 2, housekeeping_status: "clean" }] });
  await client.getQueryCache().find({ queryKey })?.promise;
  assert.equal(client.getQueryData(queryKey)?.rooms[0].housekeeping_status, "clean");

  unsubscribe();
  client.clear();
});

test("a concurrent reservation-domain event still refreshes other clients' active reservation caches", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient();
  const hotelId = 41;
  const entries = [
    [["reservations", hotelId, { status: "confirmed" }], true],
    [["reservation", hotelId, 703], true],
    [["occupancy-grid", hotelId, "2026-10-01", "2026-10-07"], true],
    [["rooms", hotelId], false],
    [["cash-sessions", hotelId], false],
    [["analytics", hotelId], false],
    [["reservations", hotelId + 1, {}], false]
  ];
  entries.forEach(([key]) => client.setQueryData(key, { key }));

  // notifyIfRelevant routes a valid other-tab message here; local senderId
  // messages are filtered before this point in crossTabSync.
  await invalidation.refreshDomains(client, hotelId, ["reservations"]);

  for (const [key, shouldInvalidate] of entries) {
    assert.equal(
      client.getQueryState(key)?.isInvalidated ?? false,
      shouldInvalidate,
      `unexpected remote-domain invalidation for ${JSON.stringify(key)}`
    );
  }
  client.clear();
});

test("security events update the audit view without coupling audit refetches to reservations", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient();
  const auditKey = ["operational-audit", 41, { limit: 20 }];
  const reservationKey = ["reservations", 41, {}];
  client.setQueryData(auditKey, { items: [] });
  client.setQueryData(reservationKey, []);

  await invalidation.refreshDomains(client, 41, ["reservations"]);
  assert.equal(client.getQueryState(auditKey)?.isInvalidated ?? false, false);
  await invalidation.refreshDomains(client, 41, ["security"]);
  assert.equal(client.getQueryState(auditKey)?.isInvalidated ?? false, true);

  client.clear();
});

test("a transient active refetch error keeps cached reservation data and does not reject refresh", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const queryKey = ["reservation", 41, 703];
  const previousReservation = { id: 703, total_amount: 900 };
  client.setQueryData(queryKey, previousReservation);
  const observer = new QueryObserver(client, {
    queryKey,
    queryFn: async () => {
      throw new Error("temporary network failure");
    },
    initialData: previousReservation,
    staleTime: Infinity,
    retry: false
  });
  const unsubscribe = observer.subscribe(() => undefined);

  await assert.doesNotReject(invalidation.refreshReservationRecordState(client, 41, 703));
  assert.deepEqual(client.getQueryData(queryKey), previousReservation);

  unsubscribe();
  client.clear();
});

test("cursor-less recovery uses reported domains; truncation and known cursor gaps reset all domains", async (context) => {
  const { keys, invalidation } = await loadQueryModules(context);
  const allDomains = Object.keys(keys.QUERY_PREFIXES_BY_DOMAIN);
  const firstConnect = invalidation.recoveryDomainsForCursor(0, {
    domains: ["reservations", "rooms", "cash"],
    reset_required: true
  });
  assert.deepEqual(firstConnect, ["reservations", "rooms", "cash"]);

  assert.deepEqual(
    invalidation.recoveryDomainsForCursor(0, {
      domains: ["reservations"],
      reset_required: true,
      has_more: true
    }),
    allDomains
  );

  assert.deepEqual(
    invalidation.recoveryDomainsForCursor(18, { domains: ["reservations", "unknown"] }),
    ["reservations"]
  );
  assert.deepEqual(
    invalidation.recoveryDomainsForCursor(18, { domains: ["reservations"], reset_required: true }),
    allDomains
  );
});

test("initial recovery marks inactive domain caches stale without refetching them until mounted", async (context) => {
  const { invalidation } = await loadQueryModules(context);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const activeKey = ["reservations", 41, { status: "confirmed" }];
  const inactiveKey = ["reservations", 41, { status: "pending" }];
  const unrelatedKey = ["rooms", 41];
  const otherHotelKey = ["reservations", 42, { status: "confirmed" }];
  client.setQueryData(activeKey, []);
  client.setQueryData(inactiveKey, []);
  client.setQueryData(unrelatedKey, []);
  client.setQueryData(otherHotelKey, []);
  let activeFetches = 0;
  let inactiveFetches = 0;
  const observer = new QueryObserver(client, {
    queryKey: activeKey,
    queryFn: async () => {
      activeFetches += 1;
      return [{ id: 703 }];
    },
    staleTime: Infinity,
    retry: false
  });
  const unsubscribe = observer.subscribe(() => undefined);

  const initialDomains = invalidation.recoveryDomainsForCursor(0, { domains: ["reservations"] });
  await invalidation.refreshDomains(client, 41, initialDomains);

  assert.equal(activeFetches, 1);
  assert.deepEqual(client.getQueryData(activeKey), [{ id: 703 }]);
  assert.equal(inactiveFetches, 0, "inactive caches must not refetch during recovery");
  assert.equal(client.getQueryState(inactiveKey)?.isInvalidated ?? false, true);
  assert.deepEqual(client.getQueryData(inactiveKey), [], "the cached value remains until the query is observed");
  assert.equal(client.getQueryState(unrelatedKey)?.isInvalidated ?? false, false);
  assert.equal(client.getQueryState(otherHotelKey)?.isInvalidated ?? false, false);

  const inactiveObserver = new QueryObserver(client, {
    queryKey: inactiveKey,
    queryFn: async () => {
      inactiveFetches += 1;
      return [{ id: 704 }];
    },
    staleTime: Infinity,
    retry: false
  });
  const unsubscribeInactive = inactiveObserver.subscribe(() => undefined);
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(inactiveFetches, 1, "a stale operational cache must refresh when its view opens");
  assert.deepEqual(client.getQueryData(inactiveKey), [{ id: 704 }]);
  unsubscribe();
  unsubscribeInactive();
  client.clear();
});

test("a known cursor reset refetches every active hotel domain and no other tenant", async (context) => {
  const { keys, invalidation } = await loadQueryModules(context);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const activeKeys = [
    ["reservations", 41, { status: "confirmed" }],
    ["cash-sessions", 41],
    ["operational-audit", 41, { limit: 20 }]
  ];
  const inactiveKey = ["rooms", 41];
  const otherHotelKey = ["reservations", 42, { status: "confirmed" }];
  [...activeKeys, inactiveKey, otherHotelKey].forEach((key) => client.setQueryData(key, []));
  const fetchCounts = new Map(activeKeys.map((key) => [JSON.stringify(key), 0]));
  const observers = activeKeys.map((queryKey) => new QueryObserver(client, {
    queryKey,
    queryFn: async () => {
      const id = JSON.stringify(queryKey);
      fetchCounts.set(id, (fetchCounts.get(id) ?? 0) + 1);
      return [{ refreshed: true }];
    },
    staleTime: Infinity,
    retry: false
  }));
  const unsubscribe = observers.map((observer) => observer.subscribe(() => undefined));
  const resetDomains = invalidation.recoveryDomainsForCursor(18, {
    domains: ["reservations"],
    reset_required: true
  });

  await invalidation.refreshDomains(client, 41, resetDomains);

  for (const queryKey of activeKeys) {
    assert.equal(fetchCounts.get(JSON.stringify(queryKey)), 1, `active query was not refreshed: ${queryKey[0]}`);
  }
  assert.deepEqual(client.getQueryData(inactiveKey), []);
  assert.equal(fetchCounts.get(JSON.stringify(otherHotelKey)) ?? 0, 0);
  assert.deepEqual(client.getQueryData(otherHotelKey), []);
  unsubscribe.forEach((stop) => stop());
  client.clear();
});

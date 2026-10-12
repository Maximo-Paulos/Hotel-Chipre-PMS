import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "typescript";

const loadCrossTabSync = async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "hotel-chipre-cross-tab-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const source = await readFile(new URL("./src/sync/crossTabSync.ts", import.meta.url), "utf8");
  const retrySource = await readFile(new URL("./src/sync/retryPolicy.ts", import.meta.url), "utf8");
  const retryPolicyPath = join(directory, "retryPolicy.mjs");
  await writeFile(retryPolicyPath, ts.transpileModule(retrySource, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
  }).outputText);
  let compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
  }).outputText;
  const refreshDescriptor = Object.getOwnPropertyDescriptor(globalThis, "__testRefreshDomains");
  context.after(() => {
    if (refreshDescriptor) Object.defineProperty(globalThis, "__testRefreshDomains", refreshDescriptor);
    else delete globalThis.__testRefreshDomains;
  });
  globalThis.__testRefreshDomains ??= () => {};
  const stubs = [
    ['import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";', "const useEffect = () => {}; const useMemo = () => {}; const useRef = (value) => ({ current: value }); const useSyncExternalStore = () => {};"],
    ['import { useQueryClient } from "@tanstack/react-query";', "const useQueryClient = () => ({});"],
    ['import { buildAuthHeaders, buildUrl } from "../api/client";', "const buildAuthHeaders = () => ({}); const buildUrl = (path) => path;"],
    ['import { recoveryDomainsForCursor, refreshDomains } from "../api/queryInvalidation";', "const recoveryDomainsForCursor = () => []; const refreshDomains = (...args) => { globalThis.__testRefreshDomains(...args); return Promise.resolve(); };"],
    ['import { nextRealtimeRetryPlan } from "./retryPolicy";', "const nextRealtimeRetryPlan = () => ({ failureCount: 1, delayMs: 1_000 });"],
    [
      'import { QUERY_PREFIXES_BY_DOMAIN } from "../api/queryKeys";',
      'const QUERY_PREFIXES_BY_DOMAIN = { analytics: [], assistant: [], cash: [], guests: [], onboarding: [], payments: [], reservations: [], rooms: [], security: [], settings: [], stock: [], users: [] };'
    ],
    ['import { useSession } from "../state/session";', "const useSession = () => ({ session: {} });"]
  ];
  for (const [statement, replacement] of stubs) {
    assert.ok(compiled.includes(statement), `expected compiled import: ${statement}`);
    compiled = compiled.replace(statement, replacement);
  }
  const modulePath = join(directory, "crossTabSync.mjs");
  await writeFile(modulePath, compiled);
  return import(`${pathToFileURL(modulePath).href}?test=${Math.random()}`);
};

test("degraded recovery is slow and backs off after failures", async (context) => {
  const { isTerminalRealtimeAuthorizationError, realtimeRecoveryPollDelay } = await loadCrossTabSync(context);

  assert.deepEqual(
    [0, 1, 2, 3, 20].map(realtimeRecoveryPollDelay),
    [60_000, 120_000, 240_000, 300_000, 300_000]
  );
  assert.equal(realtimeRecoveryPollDelay(-1), 60_000);
  assert.equal(realtimeRecoveryPollDelay(Number.NaN), 60_000);
  assert.equal(isTerminalRealtimeAuthorizationError({ status: 401 }), true);
  assert.equal(isTerminalRealtimeAuthorizationError({ status: 403 }), true);
  assert.equal(isTerminalRealtimeAuthorizationError({ status: 503 }), false);
  assert.equal(isTerminalRealtimeAuthorizationError(new Error("network unavailable")), false);
});

test("realtime reconnect attempts back off to at most once per minute", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "hotel-chipre-realtime-retry-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const source = await readFile(new URL("./src/sync/retryPolicy.ts", import.meta.url), "utf8");
  const modulePath = join(directory, "retryPolicy.mjs");
  await writeFile(modulePath, ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
  }).outputText);
  const { nextRealtimeRetryPlan } = await import(`${pathToFileURL(modulePath).href}?test=${Math.random()}`);

  assert.deepEqual(nextRealtimeRetryPlan(0, null, 0), { failureCount: 1, delayMs: 1_000 });
  assert.deepEqual(nextRealtimeRetryPlan(20, null, 0), { failureCount: 10, delayMs: 60_000 });
  assert.deepEqual(nextRealtimeRetryPlan(20, 60_000, 0), { failureCount: 1, delayMs: 1_000 });
});

test("concurrent recovery callers share one read and never rewind the stored cursor", async (context) => {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const previousFetch = Object.getOwnPropertyDescriptor(globalThis, "fetch");
  const values = new Map();
  globalThis.window = {
    sessionStorage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value)
    }
  };
  let releaseResponse = () => undefined;
  const responseGate = new Promise((resolve) => {
    releaseResponse = resolve;
  });
  let fetchCount = 0;
  globalThis.fetch = async () => {
    fetchCount += 1;
    return responseGate;
  };
  context.after(() => {
    if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow);
    else delete globalThis.window;
    if (previousFetch) Object.defineProperty(globalThis, "fetch", previousFetch);
    else delete globalThis.fetch;
  });

  const { recoverRealtime } = await loadCrossTabSync(context);
  const session = { hotelId: 41, userId: "owner-1", accessToken: "test-token" };
  const queryClient = {};
  const first = recoverRealtime(session, queryClient, 41);
  const duplicate = recoverRealtime(session, queryClient, 41);
  const otherHotel = recoverRealtime(session, queryClient, 42);
  assert.equal(fetchCount, 2, "same user and hotel share a flight, while another hotel stays isolated");

  values.set("hotel-pms:realtime-cursor:41:owner-1", "7");
  releaseResponse({
    ok: true,
    status: 200,
    json: async () => ({ latest_cursor: 6, domains: [] })
  });
  await Promise.all([first, duplicate, otherHotel]);

  assert.equal(values.get("hotel-pms:realtime-cursor:41:owner-1"), "7");
});

const withBrowserGlobals = async (context, { broadcastChannel, localStorage }) => {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const previousBroadcastChannel = Object.getOwnPropertyDescriptor(globalThis, "BroadcastChannel");
  context.after(() => {
    if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow);
    else delete globalThis.window;
    if (previousBroadcastChannel) Object.defineProperty(globalThis, "BroadcastChannel", previousBroadcastChannel);
    else delete globalThis.BroadcastChannel;
  });
  globalThis.window = {
    localStorage,
    setTimeout: globalThis.setTimeout,
    clearTimeout: globalThis.clearTimeout
  };
  if (broadcastChannel === undefined) delete globalThis.BroadcastChannel;
  else globalThis.BroadcastChannel = broadcastChannel;
};

test("domain broadcasts prefer BroadcastChannel and use localStorage only as fallback", async (context) => {
  const storageWrites = [];
  const postedMessages = [];
  class WorkingBroadcastChannel {
    constructor(name) {
      assert.equal(name, "hotel-pms-domain-events");
    }
    postMessage(message) {
      postedMessages.push(message);
    }
  }
  await withBrowserGlobals(context, {
    broadcastChannel: WorkingBroadcastChannel,
    localStorage: { setItem: (...args) => storageWrites.push(args) }
  });
  const { broadcastDomainChange } = await loadCrossTabSync(context);
  const originKey = "123e4567-e89b-42d3-a456-426614174000";

  broadcastDomainChange(41, "/api/reservations", originKey);

  assert.deepEqual(postedMessages.map((message) => message.domain), ["reservations", "rooms", "analytics"]);
  assert.deepEqual(postedMessages.map((message) => message.originKey), [originKey, originKey, originKey]);
  assert.equal(storageWrites.length, 0, "successful BroadcastChannel posts must not be duplicated via storage");
});

test("Gemma writes map to the assistant domain instead of waking analytics queries", async (context) => {
  const { domainsForPath } = await loadCrossTabSync(context);

  assert.deepEqual(domainsForPath("/api/gemma/chat/message"), ["assistant"]);
});

test("matching request origins suppress local SSE and cross-tab duplicates only once", async (context) => {
  const { beginLocalDomainMutation, finishLocalDomainMutation, shouldRefreshForDomainOrigin } =
    await loadCrossTabSync(context);
  const originKey = "123e4567-e89b-42d3-a456-426614174001";

  beginLocalDomainMutation(41, "/api/reservations", originKey);
  assert.equal(
    shouldRefreshForDomainOrigin(41, "reservations", originKey),
    false,
    "the source tab should ignore its own matching SSE event while the write is in flight"
  );
  finishLocalDomainMutation(41, originKey, true);
  assert.equal(
    shouldRefreshForDomainOrigin(41, "reservations", originKey),
    false,
    "a matching event arriving after the successful response should not refetch twice"
  );
  assert.equal(
    shouldRefreshForDomainOrigin(41, "reservations", "123e4567-e89b-42d3-a456-426614174002"),
    true,
    "an unrelated request must still refresh"
  );
});

test("origin deduplication keeps identical keys isolated by hotel", async (context) => {
  const { beginLocalDomainMutation, finishLocalDomainMutation, shouldRefreshForDomainOrigin } =
    await loadCrossTabSync(context);
  const originKey = "123e4567-e89b-42d3-a456-426614174003";

  beginLocalDomainMutation(41, "/api/reservations", originKey);
  beginLocalDomainMutation(42, "/api/reservations", originKey);
  assert.equal(shouldRefreshForDomainOrigin(41, "reservations", originKey), false);
  assert.equal(
    shouldRefreshForDomainOrigin(42, "reservations", originKey),
    false,
    "the same origin can be pending independently for a different hotel"
  );

  finishLocalDomainMutation(41, originKey, true);
  finishLocalDomainMutation(42, originKey, true);
  assert.equal(shouldRefreshForDomainOrigin(41, "reservations", originKey), false);
  assert.equal(shouldRefreshForDomainOrigin(42, "reservations", originKey), false);
  assert.equal(
    shouldRefreshForDomainOrigin(43, "reservations", originKey),
    true,
    "a hotel without this mutation must not inherit another hotel's dedupe state"
  );
});

test("domain broadcasts fall back to localStorage when BroadcastChannel is unavailable or throws", async (context) => {
  for (const mode of ["unavailable", "throws"]) {
    const storageWrites = [];
    const postedMessages = [];
    const broadcastChannel = mode === "unavailable"
      ? undefined
      : class FailingBroadcastChannel {
          constructor() {}
          postMessage(message) {
            postedMessages.push(message);
            throw new Error("channel unavailable");
          }
        };
    await withBrowserGlobals(context, {
      broadcastChannel,
      localStorage: { setItem: (...args) => storageWrites.push(args) }
    });
    const { broadcastDomainChange } = await loadCrossTabSync(context);

    broadcastDomainChange(41, "/api/reservations");

    assert.equal(storageWrites.length, 3, `${mode}: every domain should be written to the fallback`);
    assert.deepEqual(
      storageWrites.map(([, value]) => JSON.parse(value).domain),
      ["reservations", "rooms", "analytics"]
    );
    assert.equal(postedMessages.length, mode === "throws" ? 3 : 0);
  }
});

test("domain refreshes coalesce events and wait until a hidden tab becomes visible", async (context) => {
  const refreshes = [];
  globalThis.__testRefreshDomains = (...args) => refreshes.push(args);
  await withBrowserGlobals(context, {
    broadcastChannel: undefined,
    localStorage: { setItem() {} }
  });
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, "document");
  const listeners = new Set();
  globalThis.document = {
    visibilityState: "hidden",
    addEventListener: (event, listener) => event === "visibilitychange" && listeners.add(listener),
    removeEventListener: (event, listener) => event === "visibilitychange" && listeners.delete(listener)
  };
  context.after(() => {
    if (previousDocument) Object.defineProperty(globalThis, "document", previousDocument);
    else delete globalThis.document;
  });

  const { createDomainRefreshScheduler } = await loadCrossTabSync(context);
  const queryClient = {};
  const scheduler = createDomainRefreshScheduler(queryClient, 41, 5);
  scheduler.schedule("reservations");
  scheduler.schedule("reservations");
  scheduler.schedule("rooms");
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(refreshes.length, 0, "hidden tabs must retain changes without refetching");

  document.visibilityState = "visible";
  listeners.forEach((listener) => listener());
  await new Promise((resolve) => setTimeout(resolve, 10));

  assert.equal(refreshes.length, 1, "domain events from broadcasts and SSE must share one refresh window");
  assert.equal(refreshes[0][0], queryClient);
  assert.equal(refreshes[0][1], 41);
  assert.deepEqual(refreshes[0][2], ["reservations", "rooms"]);
  scheduler.close();
});

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
    ['import { useEffect, useMemo, useSyncExternalStore } from "react";', "const useEffect = () => {}; const useMemo = () => {}; const useSyncExternalStore = () => {};"],
    ['import { useQueryClient } from "@tanstack/react-query";', "const useQueryClient = () => ({});"],
    ['import { buildAuthHeaders, buildUrl } from "../api/client";', "const buildAuthHeaders = () => ({}); const buildUrl = (path) => path;"],
    ['import { recoveryDomainsForCursor, refreshDomains } from "../api/queryInvalidation";', "const recoveryDomainsForCursor = () => []; const refreshDomains = (...args) => { globalThis.__testRefreshDomains(...args); return Promise.resolve(); };"],
    [
      'import { QUERY_PREFIXES_BY_DOMAIN } from "../api/queryKeys";',
      'const QUERY_PREFIXES_BY_DOMAIN = { analytics: [], cash: [], guests: [], onboarding: [], payments: [], reservations: [], rooms: [], security: [], settings: [], stock: [], users: [] };'
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

  broadcastDomainChange(41, "/api/reservations");

  assert.deepEqual(postedMessages.map((message) => message.domain), ["reservations", "rooms", "analytics"]);
  assert.equal(storageWrites.length, 0, "successful BroadcastChannel posts must not be duplicated via storage");
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

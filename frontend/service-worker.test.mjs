import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const buildSha = "a94c1209a8aeb2aee80b348799acef54aef34e14";

function createWorker({ fetchImpl, initialCaches = [] }) {
  const listeners = new Map();
  const cacheData = new Map(initialCaches.map(([name, entries = []]) => [name, new Map(entries)]));
  const deletedCaches = [];
  const messages = [];
  const client = { postMessage: (message) => messages.push(message) };
  const caches = {
    keys: async () => [...cacheData.keys()],
    delete: async (name) => {
      deletedCaches.push(name);
      return cacheData.delete(name);
    },
    open: async (name) => {
      if (!cacheData.has(name)) cacheData.set(name, new Map());
      const entries = cacheData.get(name);
      return { put: async (request, response) => entries.set(request.url, response.clone()) };
    },
    match: async (request) => {
      for (const entries of cacheData.values()) {
        if (entries.has(request.url)) return entries.get(request.url).clone();
      }
      return undefined;
    }
  };
  const self = {
    location: { origin: "https://app.hotels-pms.com" },
    addEventListener: (type, listener) => listeners.set(type, listener),
    skipWaiting: async () => {},
    clients: {
      claim: async () => {},
      matchAll: async () => [client]
    }
  };
  const source = fs
    .readFileSync(path.join(frontendRoot, "public/sw.js"), "utf8")
    .replaceAll("__APP_BUILD_SHA__", buildSha);
  vm.runInNewContext(source, { self, caches, fetch: fetchImpl, URL, Response, Promise, TypeError });
  return { listeners, cacheData, deletedCaches, messages };
}

function scriptRequest(url = "https://app.hotels-pms.com/assets/GuestsPage-old.js") {
  const request = new Request(url);
  Object.defineProperty(request, "destination", { value: "script" });
  return request;
}

function navigationRequest(url = "https://app.hotels-pms.com/huespedes") {
  const request = new Request(url);
  Object.defineProperty(request, "mode", { value: "navigate" });
  return request;
}

async function runFetch(worker, request) {
  let responsePromise;
  worker.listeners.get("fetch")({ request, respondWith: (promise) => (responsePromise = promise) });
  return responsePromise;
}

test("activation rotates the shell cache and notifies existing app tabs", async () => {
  const worker = createWorker({
    fetchImpl: async () => new Response("unused"),
    initialCaches: [["chipre-shell-old", []], ["unrelated-cache", []]]
  });
  let activation;
  worker.listeners.get("activate")({ waitUntil: (promise) => (activation = promise) });
  await activation;

  assert.deepEqual(worker.deletedCaches, ["chipre-shell-old"]);
  assert.equal(JSON.stringify(worker.messages), JSON.stringify([{ type: "HOTEL_CHIPRE_APP_UPDATE", codeSha: buildSha }]));
});

test("an existing tab gets cache-busted recovery when an old chunk returns HTML or 404", async () => {
  for (const response of [
    new Response("<html>SPA fallback</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("missing", { status: 404, headers: { "Content-Type": "text/plain" } })
  ]) {
    const worker = createWorker({ fetchImpl: async () => response.clone() });
    const recovery = await runFetch(worker, scriptRequest());
    assert.equal(recovery.status, 200);
    assert.match(recovery.headers.get("content-type"), /javascript/u);

    const prompts = [];
    const navigations = [];
    const recoveryContext = {
      URL,
      Date,
      navigator: { language: "es-AR" },
      sessionStorage: { getItem: () => null, setItem: () => {} },
      window: {
        confirm: (message) => (prompts.push(message), true),
        location: {
          href: "https://app.hotels-pms.com/huespedes?filter=qa",
          replace: (url) => navigations.push(url)
        }
      }
    };
    const recoverySource = await recovery.text();
    assert.throws(() => vm.runInNewContext(recoverySource, recoveryContext), /Failed to fetch dynamically imported module/u);
    assert.match(prompts[0], /cambios sin guardar/u);
    assert.equal(new URL(navigations[0]).searchParams.get("filter"), "qa");
    assert.ok(new URL(navigations[0]).searchParams.has("__app_reload"));
  }
});

test("asset fetch prefers the network over an old cached chunk", async () => {
  const oldUrl = "https://app.hotels-pms.com/assets/GuestsPage-old.js";
  const cachedOld = new Response("old chunk");
  const worker = createWorker({
    fetchImpl: async () => new Response("new chunk", { headers: { "Content-Type": "text/javascript" } }),
    initialCaches: [["chipre-shell-old", [[oldUrl, cachedOld]]]]
  });
  const response = await runFetch(worker, scriptRequest(oldUrl));
  assert.equal(await response.text(), "new chunk");
});

test("legacy-tab navigation bypasses a stale cached app document", async () => {
  const url = "https://app.hotels-pms.com/huespedes";
  const fetchOptions = [];
  const worker = createWorker({
    fetchImpl: async (_request, options) => {
      fetchOptions.push(options);
      return new Response("current app document");
    },
    initialCaches: [["chipre-shell-old", [[url, new Response("stale app document")]]]]
  });

  const response = await runFetch(worker, navigationRequest(url));
  assert.equal(JSON.stringify(fetchOptions), JSON.stringify([{ cache: "no-store" }]));
  assert.equal(await response.text(), "current app document");
});

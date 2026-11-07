// No vite-plugin-pwa dependency is installed and there is no build-time
// precache manifest -- this caches the app shell (HTML/JS/CSS/icons) the
// first time each asset is actually requested by the browser, instead of
// hardcoding Vite's content-hashed filenames (which would go stale on every
// deploy without a build step to regenerate this file). Never caches /api
// or /health, so operators always see live PMS data, never a stale
// reservation/room state. No offline write queue -- critical writes must
// never queue offline, per this project's own plan.
const BUILD_SHA = "__APP_BUILD_SHA__";
const CACHE_PREFIX = "chipre-shell-";
const CACHE_NAME = `${CACHE_PREFIX}${BUILD_SHA}`;
const NEVER_CACHE_PREFIXES = ["/api", "/health", "/build-meta.json"];

function staleChunkRecoveryResponse() {
  const source = `(() => {
    const build = ${JSON.stringify(BUILD_SHA)};
    const key = "chipre:stale-chunk-recovery:" + build;
    const spanish = /^es(?:-|$)/i.test(navigator.language || "");
    const message = spanish
      ? "La aplicación se actualizó y este archivo ya no está disponible. Recargar puede descartar cambios sin guardar. ¿Querés recargar ahora?"
      : "The app was updated and this file is no longer available. Reloading may discard unsaved changes. Reload now?";
    let alreadyShown = false;
    try {
      alreadyShown = sessionStorage.getItem(key) === "1";
      sessionStorage.setItem(key, "1");
    } catch {
      // Storage can be unavailable in private or restricted browser contexts.
    }
    if (!alreadyShown) {
      if (window.confirm(message)) {
        const url = new URL(window.location.href);
        url.searchParams.set("__app_reload", String(Date.now()));
        window.location.replace(url.toString());
      }
    }
    throw new Error("Failed to fetch dynamically imported module after an app update. Reload this page to continue.");
  })();`;
  return new Response(source, {
    status: 200,
    headers: {
      "Content-Type": "text/javascript; charset=utf-8",
      "Cache-Control": "no-store"
    }
  });
}

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: "window", includeUncontrolled: true }))
      .then((clients) => {
        for (const client of clients) {
          client.postMessage({ type: "HOTEL_CHIPRE_APP_UPDATE", codeSha: BUILD_SHA });
        }
      })
  );
});

// Backend's RealWebPushAdapter is currently a stub (see app/services/
// push_adapter.py) -- no push message is actually sent yet. This handler
// exists so the subscribe flow is functionally complete on the frontend side
// the moment that adapter ships; until then it simply never fires. Payload
// shape (title/body/url) is the frontend's own choice, not a backend
// contract -- keep it in sync with whatever RealWebPushAdapter eventually
// sends. No guest/reservation detail belongs in a push payload beyond what
// the in-app inbox already exposes (see api/notifications.ts's NotificationItem
// non-disclosure comment) -- entity_type/entity_id/title only.
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: "Hotel Chipre PMS", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Hotel Chipre PMS";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || "",
      icon: "/brand/icon-192.png",
      badge: "/brand/icon-192.png",
      data: { url: data.url || "/" }
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((client) => "focus" in client);
      if (existing) {
        existing.navigate(url);
        return existing.focus();
      }
      return self.clients.openWindow(url);
    })
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (NEVER_CACHE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) return;

  // Page navigations: network-first so a stale index.html can never strand
  // an operator on an old build; cache is only a fallback for fully offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request, { cache: "no-store" }).catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
    );
    return;
  }

  // Hashed assets are network-first so an update cannot silently revive an
  // older UI from the shell cache. The versioned cache is an offline fallback.
  event.respondWith(
    fetch(request, { cache: "no-store" })
      .then((response) => {
        const isAppChunk = url.pathname.startsWith("/assets/") && request.destination === "script";
        const contentType = response.headers.get("content-type") || "";
        if (isAppChunk && (!response.ok || contentType.includes("text/html"))) {
          return staleChunkRecoveryResponse();
        }
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async (error) => {
        if (error instanceof TypeError && url.pathname.startsWith("/assets/") && request.destination === "script") {
          const cached = await caches.match(request);
          if (cached) return cached;
        }
        const cached = await caches.match(request);
        if (cached) return cached;
        throw error;
      })
  );
});

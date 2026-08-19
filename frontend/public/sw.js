// ponytail: no vite-plugin-pwa dependency (not installed) and no build-time
// precache manifest -- this caches the app shell (HTML/JS/CSS/icons) the
// first time each asset is actually requested by the browser, instead of
// hardcoding Vite's content-hashed filenames (which would go stale on every
// deploy without a build step to regenerate this file). Never caches /api
// or /health, so operators always see live PMS data, never a stale
// reservation/room state. No offline write queue -- critical writes must
// never queue offline, per this project's own plan.
const CACHE_NAME = "chipre-shell-v1";
const NEVER_CACHE_PREFIXES = ["/api", "/health"];

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
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
      fetch(request).catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
    );
    return;
  }

  // Static shell assets (hashed JS/CSS, icons, manifest): cache-first, fill
  // the cache opportunistically on first use.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});

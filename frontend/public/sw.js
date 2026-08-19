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

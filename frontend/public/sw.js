/*
 * Jeevia service worker — offline-first intake for rural camps.
 *  - Kiosk shell + static chunks are cached so intake works with no network.
 *  - Completed intakes are queued in IndexedDB by the page (lib/offline/outbox.ts);
 *    Background Sync wakes the page to flush them when connectivity returns.
 *  - API calls are never cached (clinical data must not linger in caches).
 */
const VERSION = "jeevia-v2";
const SHELL = ["/kiosk", "/offline", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(VERSION)
      .then((c) => Promise.all(SHELL.map((u) => c.add(new Request(u, { cache: "reload" })).catch(() => null))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isApi(url) {
  return url.pathname.startsWith("/api/") || url.origin !== self.location.origin;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (isApi(url)) return; // network only

  // Immutable build assets: cache-first
  if (url.pathname.startsWith("/_next/static/") || /\.(png|svg|woff2?|ico)$/.test(url.pathname)) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(VERSION).then((c) => c.put(req, copy));
            }
            return res;
          }),
      ),
    );
    return;
  }

  // Pages: network-first, fall back to cache, then the kiosk shell / offline page
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(async () => (await caches.match(req)) || (url.pathname.startsWith("/kiosk") ? await caches.match("/kiosk") : null) || (await caches.match("/offline"))),
    );
    return;
  }

  // Everything else (RSC payloads, etc.): stale-while-revalidate
  event.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || net;
    }),
  );
});

// Pages ask us to keep what they need for offline use (see lib/offline/precache.ts).
self.addEventListener("message", (event) => {
  if (event.data?.type !== "precache" || !Array.isArray(event.data.urls)) return;
  const urls = event.data.urls.filter((u) => typeof u === "string" && u.startsWith("/") && !u.startsWith("/api/")).slice(0, 300);
  event.waitUntil(
    caches.open(VERSION).then((c) =>
      Promise.all(
        urls.map(async (u) => {
          if (!u.startsWith("/_next/static/") && !u.startsWith("/k/") && !u.startsWith("/kiosk")) return u.includes(".") ? c.add(u).catch(() => null) : null;
          if (u.startsWith("/_next/static/") && (await c.match(u))) return null;
          return c.add(new Request(u, { cache: "reload" })).catch(() => null);
        }),
      ),
    ),
  );
});

self.addEventListener("sync", (event) => {
  if (event.tag === "jeevia-outbox") {
    event.waitUntil(
      self.clients.matchAll({ includeUncontrolled: true }).then((clients) => clients.forEach((c) => c.postMessage({ type: "flush-outbox" }))),
    );
  }
});

/* HumanArchive service worker.
 *
 * Chiến lược:
 *   - Precache: static assets (HTML/CSS/JS/i18n/icons)
 *   - Runtime cache: archive data (graph.json, rag_index.json)
 *                    dùng stale-while-revalidate
 *   - Offline fallback: nếu navigation fail → offline.html
 *   - KHÔNG cache submit results (form là client-only, output là download)
 *
 * Privacy: SW không track, không telemetry, không third-party. Chỉ same-origin.
 */

const VERSION = "v0.8.1";
const STATIC_CACHE = `ha-static-${VERSION}`;
const RUNTIME_CACHE = `ha-runtime-${VERSION}`;

const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./submit.html",
  "./offline.html",
  "./style.css",
  "./app.js",
  "./submit.js",
  "./i18n.js",
  "./hash_embed.js",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-maskable.svg",
  "./i18n/vi.json",
  "./i18n/en.json",
];

// CDN Mermaid — cache khi fetch lần đầu
const MERMAID_PATTERN = /cdn\.jsdelivr\.net.*mermaid/;

// Archive data — stale-while-revalidate
const ARCHIVE_PATTERN = /\/archive\/.*\.json$/;

// --------------------------------------------------------------------------

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((k) => k !== STATIC_CACHE && k !== RUNTIME_CACHE)
          .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Không intercept POST, PUT, DELETE — form luôn client-only
  if (req.method !== "GET") return;

  // Cross-origin (CDN): cache-first với fallback
  if (url.origin !== location.origin) {
    if (MERMAID_PATTERN.test(url.href)) {
      event.respondWith(cacheFirst(req, RUNTIME_CACHE));
    }
    return;
  }

  // Archive data: stale-while-revalidate
  if (ARCHIVE_PATTERN.test(url.pathname)) {
    event.respondWith(staleWhileRevalidate(req, RUNTIME_CACHE));
    return;
  }

  // Navigation request: network-first với offline fallback
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("./offline.html"))
    );
    return;
  }

  // Static assets: cache-first
  event.respondWith(cacheFirst(req, STATIC_CACHE));
});

// --------------------------------------------------------------------------
// Caching strategies
// --------------------------------------------------------------------------

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    // Network fail — return cached nếu có, hoặc throw
    const fallback = await caches.match(request);
    if (fallback) return fallback;
    throw err;
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => cached);
  return cached || fetchPromise;
}

// --------------------------------------------------------------------------
// Messages từ page (manual cache invalidate)
// --------------------------------------------------------------------------

self.addEventListener("message", (event) => {
  if (event.data === "skipWaiting") {
    self.skipWaiting();
  }
  if (event.data === "clearCache") {
    caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))));
  }
});

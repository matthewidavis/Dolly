/* Dolly service worker.
 *
 * Dolly is one self-contained HTML file with no external requests, so the
 * whole app is the shell and offline support is total rather than partial.
 *
 * BUMP CACHE ON EVERY DEPLOY. A service worker serves the cached copy to
 * returning visitors, so without a new cache name a push goes unseen —
 * the classic way a PWA ships an update nobody receives.
 */
const CACHE = "dolly-v1";

const SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-192-maskable.png",
  "./icon-512-maskable.png",
  "./favicon.png",
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL))
      // Activate immediately instead of waiting for every tab to close.
      // Paired with clients.claim() below so an update lands on the next
      // load rather than the next browser restart.
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;

  // Only GETs are cacheable, and only our own origin. Anything else goes
  // straight to the network untouched.
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) {
    return;
  }

  // Navigations: network first, so a deployed update is picked up while
  // online; fall back to the cached shell when offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put("./index.html", copy));
          return res;
        })
        .catch(() => caches.match("./index.html").then(r => r || caches.match("./")))
    );
    return;
  }

  // Everything else (icons, manifest): cache first — these are small,
  // versioned with the cache name, and never need to be fresher than it.
  event.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res && res.status === 200 && res.type === "basic") {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
      }
      return res;
    }))
  );
});

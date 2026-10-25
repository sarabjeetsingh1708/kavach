// Kavach service worker: makes the page installable and opens the app shell even on a flaky connection.
// Network first (always the latest page when online), cached copy as fallback. The live listening itself
// needs the server, so nothing else is cached.
const CACHE = "kavach-shell-v3";  // bump when icons or the shell change, so installed phones refresh
const SHELL = ["/", "/manifest.webmanifest?v=2", "/icons/icon-192.png?v=2", "/icons/icon-512.png?v=2",
               "/icons/mark-256.png?v=2"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || !SHELL.includes(url.pathname + url.search)) return;
  e.respondWith(
    fetch(e.request)
      .then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return res; })
      .catch(() => caches.match(e.request))
  );
});

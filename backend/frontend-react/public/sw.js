const CACHE_NAME = 'erp_solution-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

/** Serve cached GET responses with network fallback, bypassing URLs containing /api/. */
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  // Skip API requests - don't cache authenticated responses
  if (event.request.url.includes('/api/')) {
    // Let API requests go directly to network
    return;
  }

  // Cache static assets
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});
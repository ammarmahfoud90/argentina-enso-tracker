/*
 * Service Worker — Argentina ENSO Impact Tracker
 *
 * Strategy: stale-while-revalidate for data files,
 * cache-first for static assets (CSS, JS, fonts).
 * Serves cached data when offline.
 */

const CACHE_NAME = 'enso-tracker-v1';
const DATA_CACHE = 'enso-data-v1';

const STATIC_ASSETS = [
  './',
  './index.html',
  './css/tokens.css',
  './js/advice.js',
  './js/main.js',
  './favicon.svg',
  './manifest.json',
];

const DATA_URLS = [
  './data/enso.json',
  './data/enso-history.json',
  './data/sst_map.json',
];

/* Install — pre-cache static shell */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

/* Activate — clean old caches */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== DATA_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

/* Fetch — stale-while-revalidate for data, cache-first for static */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  /* Data files: serve cache immediately, update in background */
  if (DATA_URLS.some((d) => url.pathname.endsWith(d.replace('./', '')))) {
    event.respondWith(
      caches.open(DATA_CACHE).then((cache) =>
        cache.match(event.request).then((cached) => {
          const fetchPromise = fetch(event.request)
            .then((response) => {
              if (response.ok) {
                cache.put(event.request, response.clone());
              }
              return response;
            })
            .catch(() => cached);

          return cached || fetchPromise;
        })
      )
    );
    return;
  }

  /* Static assets + CDN: cache-first */
  if (
    event.request.destination === 'style' ||
    event.request.destination === 'script' ||
    event.request.destination === 'font' ||
    event.request.destination === 'image' ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.svg')
  ) {
    event.respondWith(
      caches.match(event.request).then(
        (cached) =>
          cached ||
          fetch(event.request).then((response) => {
            if (response.ok) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            }
            return response;
          })
      )
    );
    return;
  }

  /* Everything else: network-first with cache fallback */
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && event.request.method === 'GET') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

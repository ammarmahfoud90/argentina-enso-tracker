/*
 * Service Worker — Argentina ENSO Impact Tracker
 *
 * Strategy: network-first for local application and data files,
 * cache-first for third-party static assets.
 * Serves cached data when offline.
 */

const CACHE_NAME = 'enso-tracker-climate-v4';
const DATA_CACHE = 'enso-data-climate-v4';

const STATIC_ASSETS = [
  './',
  './index.html',
  './css/tokens.css',
  './js/i18n.js',
  './js/scientific.js',
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
    caches.open(CACHE_NAME).then((cache) =>
      cache.addAll(STATIC_ASSETS.map((asset) => new Request(asset, { cache: 'reload' })))
    )
  );
  self.skipWaiting();
});

/* Activate — clean old caches */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith('enso-') && k !== CACHE_NAME && k !== DATA_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

/* Fetch — current local files online, cached files offline */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  /* Local code and data must belong to the current published version. */
  if (url.origin === self.location.origin && event.request.method === 'GET') {
    const isData = DATA_URLS.some((d) => url.pathname.endsWith(d.replace('./', '')));
    event.respondWith(
      caches.open(isData ? DATA_CACHE : CACHE_NAME).then(async (cache) => {
        try {
          const response = await fetch(event.request, { cache: 'no-cache' });
          if (response.ok) {
            await cache.put(event.request, response.clone());
            return response;
          }
          return (await cache.match(event.request)) || response;
        } catch (error) {
          const cached = await cache.match(event.request);
          if (cached) return cached;
          throw error;
        }
      })
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

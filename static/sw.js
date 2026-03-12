const CACHE_NAME = 'gisl-schools-v2';
const URLS = [
  '/',
  '/index.html',
  '/css/style.css',
  '/css/animations.css',
  '/js/app.js',
  '/js/logger.js',
  '/gisl_logo.png',
  '/manifest.json'
];

function shouldHandleWithCache(request) {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  // Never cache API/auth responses. They are user/session-specific and can
  // otherwise replay stale 401 responses that force unexpected logouts.
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') return false;
  return true;
}

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  if (!shouldHandleWithCache(event.request)) {
    return; // Let the network handle API and other dynamic requests directly.
  }

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request)
        .then(response => {
          // Cache only successful same-origin responses.
          if (response && response.ok && response.type === 'basic') {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => {
          if (event.request.mode === 'navigate') return caches.match('/index.html');
          return caches.match(event.request);
        });
    })
  );
});
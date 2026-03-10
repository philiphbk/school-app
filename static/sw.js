const CACHE_NAME = 'gisl-schools-v1';
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

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(URLS)));
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match('/index.html'));
    })
  );
});
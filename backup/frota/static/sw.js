const CACHE_NAME = 'combustivel-cache-v1';
const URLS_TO_CACHE = [
  '/lancar_abastecimento', // URL inicial do nosso app
  '/static/css/bootstrap.min.css',
  '/static/js/bootstrap.bundle.min.js',
  '/offline'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(URLS_TO_CACHE))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request).catch(() => caches.match('/offline'));
    })
  );
});
// static/sw.js - Service Worker for offline caching
const CACHE_NAME = 'toilet-map-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/manifest.json',
  '/static/mobile.css',
];
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS_TO_CACHE))
  );
});
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => Promise.all(
      names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
    ))
  );
});
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  self.registration.showNotification(data.title || 'トイレマップ', {
    body: data.body || '',
    icon: '/static/icon-192.png',
  });
});

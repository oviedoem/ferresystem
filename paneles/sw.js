// FerreSystem — Service Worker
// Scope: /paneles/  (registrado desde cada panel HTML)
// Estrategia: cache-first para HTML del panel, network-first para datos JSON.

const CACHE = 'ferresystem-paneles-v1';

const PRECACHE_URLS = [
  'panel-admin.html',
  'panel-vendedor.html',
  'panel-cliente.html',
  'panel-operador.html',
  'demo.html',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const { request } = e;
  const url = new URL(request.url);

  // Network-first para JSONs de datos — siempre queremos el dato fresco.
  if (url.pathname.includes('/data/')) {
    e.respondWith(
      fetch(request)
        .then(r => {
          if (r.ok) caches.open(CACHE).then(c => c.put(request, r.clone()));
          return r;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Cache-first para los paneles HTML y demás assets estáticos.
  e.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).then(r => {
        if (r.ok) caches.open(CACHE).then(c => c.put(request, r.clone()));
        return r;
      });
    })
  );
});

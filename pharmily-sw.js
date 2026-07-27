// Service worker de Pharmily: permite instalar la app y seguir usándola sin conexión.
// Estrategia "red primero, caché de reserva" — si hay internet siempre se usa la versión más
// reciente del archivo; si no hay, se sirve la última copia guardada en este dispositivo.
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => self.clients.claim());
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        const copia = resp.clone();
        caches.open('pharmily-v1').then((cache) => cache.put(event.request, copia));
        return resp;
      })
      .catch(() => caches.match(event.request))
  );
});

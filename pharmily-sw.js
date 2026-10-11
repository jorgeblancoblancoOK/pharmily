// Service worker de Pharmily: permite instalar la app y seguir usándola sin conexión.
// Estrategia "red primero, caché de reserva" — si hay internet siempre se usa la versión más
// reciente del archivo; si no hay, se sirve la última copia guardada en este dispositivo.
// Solo se cachean los archivos de la propia app y la librería supabase-js: nunca respuestas de
// la API de Supabase, que contienen datos de los empleados y no deben quedarse en el dispositivo.
const CACHEABLES_EXTERNOS = ['https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js'];
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => self.clients.claim());
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin && !CACHEABLES_EXTERNOS.includes(url.href)) return;
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        if (resp.ok) {
          const copia = resp.clone();
          caches.open('pharmily-v1').then((cache) => cache.put(event.request, copia));
        }
        return resp;
      })
      .catch(() => caches.match(event.request))
  );
});

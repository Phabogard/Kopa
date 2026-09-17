/* =====================================================================
   Carnet de dettes — Service Worker
   ===================================================================== */
const VERSION = 'carnet-v1';
const CACHE_SHELL = `${VERSION}-shell`;
const CACHE_EXTERNE = `${VERSION}-externe`;
const SHELL = ['/', '/index.html', '/manifest.json', '/icons/icone-192.png', '/icons/icone-512.png', '/icons/icone-maskable-512.png'];
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_SHELL).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((noms) => Promise.all(noms.filter((n) => !n.startsWith(VERSION)).map((n) => caches.delete(n)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (event) => {
  const requete = event.request;
  if (requete.method !== 'GET') return;
  const url = new URL(requete.url);
  if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(requete).catch(() => new Response(JSON.stringify({ detail: 'Hors ligne : impossible de joindre le serveur.' }), { status: 503, headers: { 'Content-Type': 'application/json' } })));
    return;
  }
  if (requete.mode === 'navigate') {
    event.respondWith(fetch(requete).then((reponse) => { const copie = reponse.clone(); caches.open(CACHE_SHELL).then((c) => c.put('/index.html', copie)); return reponse; }).catch(() => caches.match('/index.html')));
    return;
  }
  if (url.origin !== self.location.origin) {
    event.respondWith(caches.open(CACHE_EXTERNE).then(async (cache) => { const enCache = await cache.match(requete); const reseau = fetch(requete).then((reponse) => { if (reponse.ok || reponse.type === 'opaque') cache.put(requete, reponse.clone()); return reponse; }).catch(() => enCache); return enCache || reseau; }));
    return;
  }
  event.respondWith(caches.match(requete).then((enCache) => enCache || fetch(requete).then((reponse) => { if (reponse.ok) { const copie = reponse.clone(); caches.open(CACHE_SHELL).then((c) => c.put(requete, copie)); } return reponse; })));
});
self.addEventListener('message', (event) => { if (event.data === 'ACTIVER_MAINTENANT') self.skipWaiting(); });
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const cible = event.notification.data?.url || '/';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((liste) => { const fenetre = liste.find((c) => c.url.includes(self.location.origin)); if (fenetre) return fenetre.focus(); return self.clients.openWindow(cible); }));
});

/*
 * Service Worker do PWA do Slitherlink.
 *
 * O jogo é 100% client-side, então dá para cachear o "shell" inteiro e rodar
 * OFFLINE. Estratégia:
 *  - navegação (HTML): rede primeiro (pega a versão nova quando há deploy),
 *    com o cache como reserva offline;
 *  - demais assets (css/js/ícones, já versionados por ?v=): cache primeiro.
 *
 * IMPORTANTE: ao mudar core.js/game.js/worker.js, suba a VERSION aqui JUNTO
 * com a de game.js e os ?v= do index.html — o novo nome de cache força a
 * reinstalação do shell.
 */
const VERSION = '14';
const CACHE = 'slither-' + VERSION;

const SHELL = [
  './',
  './index.html',
  './css/style.css',
  './js/core.js?v=' + VERSION,
  './js/game.js?v=' + VERSION,
  './js/worker.js?v=' + VERSION,
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (new URL(req.url).origin !== location.origin) return;

  // HTML: rede primeiro (atualiza), cache no offline
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((r) => { const cp = r.clone(); caches.open(CACHE).then((c) => c.put('./index.html', cp)); return r; })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  // assets: cache primeiro, rede de reserva (e cacheia o que vier)
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((r) => {
      const cp = r.clone();
      caches.open(CACHE).then((c) => c.put(req, cp));
      return r;
    }))
  );
});

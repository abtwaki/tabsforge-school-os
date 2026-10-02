/* TabsForge service worker — offline-first shell + attendance queue support.
 *
 * Strategy:
 *  - Navigations (HTML): NETWORK-FIRST. The shell HTML references hashed
 *    assets, so it must never be served stale; falls back to the cached
 *    shell when offline so the app still opens.
 *  - /assets/* (hashed, immutable): cache-first.
 *  - Roster/lookup GET APIs: network-first, cached copy as offline fallback.
 *  - Everything else: pass through.
 *
 * Bump the cache suffix on every deploy to evict stale shells. */

const SHELL_CACHE = 'tf-shell-v3'
const DATA_CACHE = 'tf-data-v3'
const SHELL_ASSETS = ['/manifest.json', '/favicon.svg']

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(cache => cache.addAll(SHELL_ASSETS.concat(['/index.html'])))
      .then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => ![SHELL_CACHE, DATA_CACHE].includes(k)).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', event => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== location.origin) return

  // SPA navigations + the shell HTML: network-first so new deploys are
  // picked up immediately; offline → cached shell.
  if (request.mode === 'navigate' || url.pathname === '/' || url.pathname === '/index.html') {
    event.respondWith(
      fetch(request).then(res => {
        if (res.ok) {
          const copy = res.clone()
          caches.open(SHELL_CACHE).then(c => c.put('/index.html', copy))
        }
        return res
      }).catch(() => caches.match('/index.html'))
    )
    return
  }

  // Hashed build assets + small shell files: cache-first (immutable).
  if (url.pathname.startsWith('/assets/') || SHELL_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then(hit => hit || fetch(request).then(res => {
        const copy = res.clone()
        caches.open(SHELL_CACHE).then(c => c.put(request, copy))
        return res
      }))
    )
    return
  }

  // Read-only roster/lookup APIs used for offline attendance: network-first,
  // fall back to the last cached copy when offline.
  if (url.pathname.startsWith('/api/students') || url.pathname.startsWith('/api/classes')
      || url.pathname.startsWith('/api/sections') || url.pathname.startsWith('/api/enrollments')
      || url.pathname.startsWith('/api/attendance')) {
    event.respondWith(
      fetch(request).then(res => {
        if (res.ok) {
          const copy = res.clone()
          caches.open(DATA_CACHE).then(c => c.put(request, copy))
        }
        return res
      }).catch(() => caches.match(request).then(hit => hit || new Response(
        JSON.stringify({ detail: 'offline', results: [] }),
        { status: 503, headers: { 'Content-Type': 'application/json' } }
      )))
    )
    return
  }
})

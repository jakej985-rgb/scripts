const CACHE_NAME = 'infernal-cache-v1';
const OFFLINE_URL = '/Force404'; // Using Limbo as offline page for now

const ASSETS_TO_CACHE = [
    '/',
    '/css/site.css',
    '/js/site.js',
    '/lib/bootstrap/dist/css/bootstrap.min.css',
    '/lib/bootstrap/dist/js/bootstrap.bundle.min.js',
    OFFLINE_URL
];

// Install Event
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                return cache.addAll(ASSETS_TO_CACHE);
            })
    );
    self.skipWaiting();
});

// Activate Event
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch Event
self.addEventListener('fetch', (event) => {
    // Skip cross-origin requests
    if (!event.request.url.startsWith(self.location.origin)) return;

    // Network First, fall back to Cache, then Offline Page
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Check if valid reference to cache
                if (!response || response.status !== 200 || response.type !== 'basic') {
                    return response;
                }

                // Clone response to cache it
                const responseToCache = response.clone();
                caches.open(CACHE_NAME)
                    .then((cache) => {
                        cache.put(event.request, responseToCache);
                    });

                return response;
            })
            .catch(() => {
                return caches.match(event.request)
                    .then((response) => {
                        if (response) {
                            return response;
                        }
                        // If both fail, show offline page for HTML requests
                        if (event.request.mode === 'navigate') {
                            return caches.match(OFFLINE_URL);
                        }
                    });
            })
    );
});

const CACHE_NAME = 'taskcore-cache-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/login',
  '/static/css/styles.css',
  '/static/manifest.json',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png'
];

// Instalar el Service Worker y cachear recursos esenciales
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Cacheando recursos principales...');
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

// Activar el Service Worker y limpiar cachés antiguas
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[Service Worker] Limpiando caché antigua:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Interceptar peticiones para servir desde caché si está fuera de línea
self.addEventListener('fetch', (event) => {
  // Evitar interceptar llamadas a APIs locales (/api/...) o subidas de archivos
  if (event.request.url.includes('/api/')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).catch(() => {
        // Fallback si no hay conexión
        if (event.request.mode === 'navigate') {
          return caches.match('/login');
        }
      });
    })
  );
});

// =================================================================
// NOTIFICACIONES PUSH EN SEGUNDO PLANO (WEB PUSH)
// =================================================================
self.addEventListener('push', (event) => {
  let data = {
    title: 'TaskCore Alerta',
    body: 'Hay una actualización importante en el sistema.',
    icon: '/static/img/icon-192.png',
    badge: '/static/img/icon-192.png',
    tag: 'taskcore-notificacion'
  };

  if (event.data) {
    try {
      const payload = event.data.json();
      data = {
        title: payload.title || data.title,
        body: payload.body || data.body,
        icon: payload.icon || data.icon,
        badge: payload.badge || data.badge,
        tag: payload.tag || data.tag,
        data: payload.data || null
      };
    } catch (e) {
      // Si el payload es texto plano en vez de JSON
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon,
    badge: data.badge,
    tag: data.tag,
    vibrate: [200, 100, 200],
    data: data.data,
    actions: [
      { action: 'open', title: 'Ver Detalles' },
      { action: 'close', title: 'Ignorar' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Manejar clic en las notificaciones
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  // Redireccionar al dashboard o una orden específica si el payload trae datos
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      let targetUrl = '/dashboard';
      if (event.notification.data && event.notification.data.url) {
        targetUrl = event.notification.data.url;
      }
      
      // Si la ventana ya está abierta, hacer focus y navegar
      for (const client of clientList) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      // Si no, abrir una pestaña nueva
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

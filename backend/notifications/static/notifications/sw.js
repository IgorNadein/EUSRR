/**
 * Service Worker для обработки Web Push уведомлений
 * 
 * Этот файл должен находиться в корне static/ для правильного scope.
 * Service Worker перехватывает push-события от браузера и показывает
 * нативные уведомления даже когда страница закрыта.
 */

// Версия Service Worker (для обновления кэша при изменениях)
const SW_VERSION = '1.0.0';

// Настройки по умолчанию для уведомлений (без project-specific путей!)
// Все пути к ресурсам (icon, badge, image) должны приходить с сервера
const DEFAULT_NOTIFICATION_OPTIONS = {
    vibrate: [100, 50, 100],
    requireInteraction: false,
    renotify: true,
};

/**
 * Событие установки Service Worker
 */
self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker installing, version:', SW_VERSION);
    // Немедленно активировать новую версию
    self.skipWaiting();
});

/**
 * Событие активации Service Worker
 */
self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker activated, version:', SW_VERSION);
    // Захватить все клиенты без перезагрузки
    event.waitUntil(self.clients.claim());
});

/**
 * Обработка входящих push-уведомлений
 * 
 * Формат данных с сервера:
 * {
 *   "title": "Заголовок уведомления",
 *   "body": "Текст уведомления",
 *   "icon": "/static/img/...",  // опционально
 *   "badge": "/static/img/...", // опционально
 *   "tag": "notification-id",   // для группировки
 *   "data": {
 *     "url": "/path/to/page",   // куда перейти при клике
 *     "notification_id": 123,
 *     "category": "requests",
 *     ...
 *   }
 * }
 */
self.addEventListener('push', (event) => {
    console.log('[SW] 🔔 Push received:', event);
    console.log('[SW] 🔔 Has data:', !!event.data);
    
    let notificationData = {
        title: 'Новое уведомление',
        body: '',
        ...DEFAULT_NOTIFICATION_OPTIONS,
        data: {}
    };
    
    if (event.data) {
        try {
            const payload = event.data.json();
            console.log('[SW] 🔔 Push payload:', payload);
            
            notificationData = {
                ...notificationData,
                title: payload.title || notificationData.title,
                body: payload.body || payload.message || '',
                tag: payload.tag || `notification-${Date.now()}`,
                data: payload.data || {}
            };
            
            // Опциональные ресурсы (только если пришли с сервера)
            if (payload.icon) {
                notificationData.icon = payload.icon;
            }
            if (payload.badge) {
                notificationData.badge = payload.badge;
            }
            if (payload.image) {
                notificationData.image = payload.image;
            }
            if (payload.actions) {
                notificationData.actions = payload.actions;
            }
            if (payload.requireInteraction !== undefined) {
                notificationData.requireInteraction = payload.requireInteraction;
            }
            
        } catch (e) {
            // Если данные не JSON, используем как текст
            console.log('[SW] Push data is not JSON, using as text');
            notificationData.body = event.data.text();
        }
    }
    
    console.log('[SW] 🔔 Showing notification:', notificationData.title);
    
    // Показываем уведомление
    const promiseChain = self.registration.showNotification(
        notificationData.title,
        {
            body: notificationData.body,
            icon: notificationData.icon,
            badge: notificationData.badge,
            tag: notificationData.tag,
            data: notificationData.data,
            vibrate: notificationData.vibrate,
            requireInteraction: notificationData.requireInteraction,
            renotify: notificationData.renotify,
            image: notificationData.image,
            actions: notificationData.actions,
        }
    ).then(() => {
        console.log('[SW] ✅ Notification shown successfully:', notificationData.title);
    }).catch((error) => {
        console.error('[SW] ❌ Failed to show notification:', error);
    });
    
    event.waitUntil(promiseChain);
});

/**
 * Обработка клика по уведомлению
 */
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification click:', event);
    
    event.notification.close();
    
    // Получаем URL для перехода
    const notificationData = event.notification.data || {};
    let urlToOpen = notificationData.url || '/';
    
    // Обработка действий (action buttons)
    if (event.action) {
        console.log('[SW] Action clicked:', event.action);
        // Можно добавить обработку разных действий
        if (notificationData.actions && notificationData.actions[event.action]) {
            urlToOpen = notificationData.actions[event.action].url || urlToOpen;
        }
    }
    
    // Открываем или фокусируем окно
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Ищем уже открытое окно с нашим сайтом
                for (const client of clientList) {
                    const clientUrl = new URL(client.url);
                    const targetUrl = new URL(urlToOpen, self.location.origin);
                    
                    // Если найдено окно с тем же origin - фокусируем и переходим
                    if (clientUrl.origin === targetUrl.origin && 'focus' in client) {
                        return client.navigate(urlToOpen).then(() => client.focus());
                    }
                }
                
                // Если нет открытого окна - открываем новое
                if (self.clients.openWindow) {
                    return self.clients.openWindow(urlToOpen);
                }
            })
    );
});

/**
 * Обработка закрытия уведомления без клика
 */
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] Notification closed:', event.notification.tag);
    
    // Можно отправить на сервер информацию о закрытии
    // Например, для аналитики
    const notificationData = event.notification.data || {};
    if (notificationData.notification_id) {
        // fetch('/api/v1/notifications/' + notificationData.notification_id + '/dismissed/', {
        //     method: 'POST',
        //     credentials: 'include'
        // }).catch(() => {});
    }
});

/**
 * Получение сообщений от основной страницы
 */
self.addEventListener('message', (event) => {
    console.log('[SW] Message received:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('[SW] Service Worker loaded, version:', SW_VERSION);

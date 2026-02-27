/**
 * Service Worker для обработки Web Push уведомлений
 * 
 * Этот файл должен находиться в /public/ для Next.js.
 * Service Worker перехватывает push-события от браузера и показывает
 * нативные уведомления даже когда страница закрыта.
 */

const SW_VERSION = '2.0.0';

// Настройки по умолчанию для уведомлений
const DEFAULT_NOTIFICATION_OPTIONS = {
    icon: '/logo.png',
    badge: '/logo.png',
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
 *   "icon": "/logo.png",
 *   "badge": "/logo.png",
 *   "tag": "notification-id",
 *   "data": {
 *     "url": "/path/to/page",
 *     "notification_id": 123,
 *     "category": "requests",
 *   }
 * }
 */
self.addEventListener('push', (event) => {
    console.log('[SW] Push received:', event);
    
    let notificationData = {
        title: 'Новое уведомление',
        body: '',
        ...DEFAULT_NOTIFICATION_OPTIONS,
        data: {}
    };
    
    if (event.data) {
        try {
            const payload = event.data.json();
            console.log('[SW] Push payload:', payload);
            
            notificationData = {
                ...notificationData,
                title: payload.title || notificationData.title,
                body: payload.body || payload.message || '',
                icon: payload.icon || notificationData.icon,
                badge: payload.badge || notificationData.badge,
                tag: payload.tag || `notification-${Date.now()}`,
                data: payload.data || {}
            };
            
            // Дополнительные опции
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
            console.log('[SW] Push data is not JSON, using as text');
            notificationData.body = event.data.text();
        }
    }
    
    // Показываем уведомление
    const { title, ...options } = notificationData;
    
    event.waitUntil(
        self.registration.showNotification(title, options)
            .then(() => {
                console.log('[SW] Notification shown:', title);
            })
            .catch((error) => {
                console.error('[SW] Failed to show notification:', error);
            })
    );
});

/**
 * Обработка клика по уведомлению
 */
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification clicked:', event.notification.tag);
    
    event.notification.close();
    
    // Получаем URL из данных уведомления
    const urlToOpen = event.notification.data?.url || '/';
    
    // Открываем или фокусируемся на странице
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((windowClients) => {
                // Ищем уже открытую вкладку с нашим сайтом
                for (let client of windowClients) {
                    if (client.url.includes(self.location.origin) && 'focus' in client) {
                        return client.focus().then((client) => {
                            // Отправляем сообщение для навигации
                            if ('navigate' in client) {
                                return client.navigate(urlToOpen);
                            }
                            return client.postMessage({
                                type: 'NOTIFICATION_CLICK',
                                url: urlToOpen,
                                notificationId: event.notification.data?.notification_id
                            });
                        });
                    }
                }
                
                // Если открытой вкладки нет, открываем новую
                if (clients.openWindow) {
                    return clients.openWindow(urlToOpen);
                }
            })
    );
});

/**
 * Обработка закрытия уведомления
 */
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] Notification closed:', event.notification.tag);
    
    // Можно отправить статистику на сервер
    if (event.notification.data?.notification_id) {
        // fetch('/api/v1/notifications/stats/closed/', {
        //     method: 'POST',
        //     body: JSON.stringify({ id: event.notification.data.notification_id })
        // });
    }
});

console.log('[SW] Service Worker loaded, version:', SW_VERSION);

/**
 * Web Push Notifications Module
 * 
 * Модуль для управления подпиской на Web Push уведомления.
 * Регистрирует Service Worker и управляет push-подписками.
 * 
 * @module notifications/push-notifications
 */

/**
 * Класс для управления Web Push подписками
 */
class PushNotificationsManager {
    /**
     * Создает экземпляр менеджера push-уведомлений
     */
    constructor() {
        this.swRegistration = null;
        this.vapidPublicKey = null;
        this.isSubscribed = false;
        this.isSupported = this._checkSupport();
    }
    
    /**
     * Проверяет поддержку Push API браузером
     * @returns {boolean} true если поддерживается
     */
    _checkSupport() {
        if (!('serviceWorker' in navigator)) {
            console.warn('[PushNotifications] Service Worker не поддерживается');
            return false;
        }
        if (!('PushManager' in window)) {
            console.warn('[PushNotifications] Push API не поддерживается');
            return false;
        }
        if (!('Notification' in window)) {
            console.warn('[PushNotifications] Notification API не поддерживается');
            return false;
        }
        return true;
    }
    
    /**
     * Инициализирует менеджер push-уведомлений
     * @returns {Promise<boolean>} Успешность инициализации
     */
    async init() {
        if (!this.isSupported) {
            return false;
        }
        
        try {
            // Получаем VAPID ключ с сервера
            await this._fetchVapidKey();
            
            // Регистрируем Service Worker
            await this._registerServiceWorker();
            
            // Проверяем текущий статус подписки
            await this._checkSubscription();
            
            console.log('[PushNotifications] Инициализация завершена, подписка:', this.isSubscribed);
            return true;
            
        } catch (error) {
            console.error('[PushNotifications] Ошибка инициализации:', error);
            return false;
        }
    }
    
    /**
     * Получает VAPID ключ с сервера
     * @private
     */
    async _fetchVapidKey() {
        const response = await fetch('/api/v1/notifications/push/vapid-key/', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error(`Не удалось получить VAPID ключ: ${response.status}`);
        }
        
        const data = await response.json();
        this.vapidPublicKey = data.vapid_public_key;
        
        if (!this.vapidPublicKey) {
            throw new Error('VAPID ключ отсутствует в ответе сервера');
        }
    }
    
    /**
     * Регистрирует Service Worker
     * @private
     */
    async _registerServiceWorker() {
        // Service Worker находится в корне для правильного scope
        this.swRegistration = await navigator.serviceWorker.register('/sw.js', {
            scope: '/'
        });
        
        console.log('[PushNotifications] Service Worker зарегистрирован:', this.swRegistration.scope);
        
        // Ждем активации
        if (this.swRegistration.installing) {
            await new Promise((resolve) => {
                this.swRegistration.installing.addEventListener('statechange', (e) => {
                    if (e.target.state === 'activated') {
                        resolve();
                    }
                });
            });
        }
    }
    
    /**
     * Проверяет текущий статус подписки
     * ТОЛЬКО ЧТЕНИЕ - не модифицирует подписку
     * @private
     */
    async _checkSubscription() {
        const subscription = await this.swRegistration.pushManager.getSubscription();
        this.isSubscribed = subscription !== null;
        
        if (this.isSubscribed) {
            console.log('[PushNotifications] ✅ Активная подписка найдена');
        } else {
            console.log('[PushNotifications] ℹ️ Подписка отсутствует');
        }
    }
    
    /**
     * Конвертирует base64 строку в Uint8Array для applicationServerKey
     * @param {string} base64String - Base64 encoded VAPID key
     * @returns {Uint8Array}
     * @private
     */
    _urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        
        return outputArray;
    }
    
    /**
     * Запрашивает разрешение на уведомления
     * @returns {Promise<string>} Статус разрешения: 'granted', 'denied', 'default'
     */
    async requestPermission() {
        if (!this.isSupported) {
            return 'unsupported';
        }
        
        const permission = await Notification.requestPermission();
        console.log('[PushNotifications] Разрешение:', permission);
        return permission;
    }
    
    /**
     * Подписывается на push-уведомления
     * @returns {Promise<boolean>} Успешность подписки
     */
    async subscribe() {
        if (!this.isSupported || !this.swRegistration || !this.vapidPublicKey) {
            console.error('[PushNotifications] Менеджер не инициализирован');
            return false;
        }
        
        // Проверяем разрешение
        if (Notification.permission === 'denied') {
            console.warn('[PushNotifications] Уведомления заблокированы');
            return false;
        }
        
        if (Notification.permission === 'default') {
            const permission = await this.requestPermission();
            if (permission !== 'granted') {
                return false;
            }
        }
        
        // Проверяем, не подписаны ли уже
        if (this.isSubscribed) {
            console.log('[PushNotifications] ℹ️ Уже подписан, пропускаем');
            return true;
        }
        
        try {
            // Создаем push-подписку (браузер сам управляет существующими подписками)
            const subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this._urlBase64ToUint8Array(this.vapidPublicKey)
            });
            
            console.log('[PushNotifications] ✅ Push-подписка создана:', subscription.endpoint.substring(0, 50) + '...');
            
            // Отправляем подписку на сервер (update_or_create)
            await this._sendSubscriptionToServer(subscription);
            
            this.isSubscribed = true;
            return true;
            
        } catch (error) {
            console.error('[PushNotifications] ❌ Ошибка подписки:', error.name, error.message);
            
            // Если AbortError - показываем инструкцию по recovery
            if (error.name === 'AbortError') {
                console.error(
                    '[PushNotifications] ⚠️ AbortError обнаружен!\n' +
                    'Это означает конфликт с предыдущей подпиской.\n' +
                    'Решение: вызовите window.pushNotifications.resetEverything() и обновите страницу.'
                );
            }
            
            return false;
        }
    }
    
    /**
     * Отправляет подписку на сервер
     * @param {PushSubscription} subscription
     * @private
     */
    async _sendSubscriptionToServer(subscription) {
        const subscriptionJson = subscription.toJSON();
        
        // Получаем CSRF токен
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value 
            || document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        
        const response = await fetch('/api/v1/notifications/push/subscribe/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            credentials: 'include',
            body: JSON.stringify({
                endpoint: subscriptionJson.endpoint,
                keys: subscriptionJson.keys,
                user_agent: navigator.userAgent,
                device_name: this._getDeviceName()
            })
        });
        
        if (!response.ok) {
            throw new Error('Не удалось сохранить подписку на сервере');
        }
        
        const data = await response.json();
        console.log('[PushNotifications] Подписка сохранена на сервере:', data);
    }
    
    /**
     * Определяет название устройства
     * @returns {string}
     * @private
     */
    _getDeviceName() {
        const ua = navigator.userAgent;
        
        if (/iPhone|iPad|iPod/.test(ua)) {
            return 'iOS Device';
        }
        if (/Android/.test(ua)) {
            return 'Android Device';
        }
        if (/Windows/.test(ua)) {
            if (/Edge/.test(ua)) return 'Windows (Edge)';
            if (/Chrome/.test(ua)) return 'Windows (Chrome)';
            if (/Firefox/.test(ua)) return 'Windows (Firefox)';
            return 'Windows';
        }
        if (/Mac/.test(ua)) {
            if (/Chrome/.test(ua)) return 'macOS (Chrome)';
            if (/Safari/.test(ua)) return 'macOS (Safari)';
            if (/Firefox/.test(ua)) return 'macOS (Firefox)';
            return 'macOS';
        }
        if (/Linux/.test(ua)) {
            return 'Linux';
        }
        
        return 'Unknown Device';
    }
    
    /**
     * Отписывается от push-уведомлений
     * @returns {Promise<boolean>} Успешность отписки
     */
    async unsubscribe() {
        if (!this.swRegistration) {
            return true;
        }
        
        try {
            const subscription = await this.swRegistration.pushManager.getSubscription();
            
            if (!subscription) {
                this.isSubscribed = false;
                return true;
            }
            
            // Отписываемся в браузере
            await subscription.unsubscribe();
            
            // Удаляем подписку на сервере
            await this._removeSubscriptionFromServer(subscription.endpoint);
            
            this.isSubscribed = false;
            console.log('[PushNotifications] Отписка выполнена');
            return true;
            
        } catch (error) {
            console.error('[PushNotifications] Ошибка отписки:', error);
            return false;
        }
    }
    
    /**
     * Удаляет подписку с сервера
     * @param {string} endpoint
     * @private
     */
    async _removeSubscriptionFromServer(endpoint) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value 
            || document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        
        const response = await fetch('/api/v1/notifications/push/unsubscribe/', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            credentials: 'include',
            body: JSON.stringify({ endpoint })
        });
        
        if (!response.ok) {
            console.warn('[PushNotifications] Не удалось удалить подписку с сервера');
        }
    }
    
    /**
     * 🔄 ПОЛНАЯ ОЧИСТКА Service Worker и подписок
     * 
     * Используйте ТОЛЬКО для recovery после критических ошибок:
     * - AbortError при подписке
     * - Конфликт VAPID ключей
     * - Некорректное состояние Service Worker
     * 
     * После вызова ОБЯЗАТЕЛЬНО обновите страницу: location.reload()
     * 
     * @returns {Promise<boolean>}
     */
    async resetEverything() {
        try {
            console.log('[PushNotifications] 🔄 ПОЛНАЯ ОЧИСТКА начата...');
            console.log('[PushNotifications] Это действие удалит Service Worker и все подписки');
            
            // 1. Удаляем подписку из браузера
            if (this.swRegistration) {
                try {
                    const subscription = await this.swRegistration.pushManager.getSubscription();
                    if (subscription) {
                        await subscription.unsubscribe();
                        console.log('[PushNotifications] ✅ Подписка удалена из браузера');
                    }
                } catch (e) {
                    console.warn('[PushNotifications] ⚠️ Не удалось удалить подписку:', e.message);
                }
                
                // 2. Удаляем Service Worker
                try {
                    const unregistered = await this.swRegistration.unregister();
                    if (unregistered) {
                        console.log('[PushNotifications] ✅ Service Worker удален');
                    }
                } catch (e) {
                    console.warn('[PushNotifications] ⚠️ Не удалось удалить Service Worker:', e.message);
                }
            }
            
            // 3. Очищаем localStorage
            localStorage.removeItem('push_endpoint');
            console.log('[PushNotifications] ✅ localStorage очищен');
            
            // 4. Ждем 2 секунды для обработки Push Service
            console.log('[PushNotifications] ⏳ Ожидание 2 сек для обработки Push Service...');
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // 5. Перерегистрируем Service Worker
            try {
                await this._registerServiceWorker();
                console.log('[PushNotifications] ✅ Service Worker перерегистрирован');
            } catch (e) {
                console.error('[PushNotifications] ❌ Не удалось перерегистрировать Service Worker:', e);
                throw e;
            }
            
            this.isSubscribed = false;
            this.swRegistration = await navigator.serviceWorker.getRegistration('/');
            
            console.log('[PushNotifications] ✅ Полная очистка завершена!');
            console.log('[PushNotifications] 📍 ОБНОВИТЕ СТРАНИЦУ (F5) и попробуйте подписаться снова');
            
            return true;
            
        } catch (error) {
            console.error('[PushNotifications] ❌ Критическая ошибка при сбросе:', error);
            console.error('[PushNotifications] Попробуйте очистить данные сайта вручную:');
            console.error('[PushNotifications] DevTools → Application → Clear storage → Clear site data');
            return false;
        }
    }
    
    /**
     * Возвращает текущий статус разрешения
     * @returns {string} 'granted', 'denied', 'default', или 'unsupported'
     */
    getPermissionStatus() {
        if (!this.isSupported) {
            return 'unsupported';
        }
        return Notification.permission;
    }
    
    /**
     * Проверяет, подписан ли пользователь
     * @returns {boolean}
     */
    getSubscriptionStatus() {
        return this.isSubscribed;
    }
}

// Создаем глобальный экземпляр
const pushNotifications = new PushNotificationsManager();

// Экспортируем для использования в других модулях
export { PushNotificationsManager, pushNotifications };

// Также делаем доступным глобально для совместимости
window.pushNotifications = pushNotifications;

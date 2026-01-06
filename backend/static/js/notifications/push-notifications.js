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
     * @private
     */
    async _checkSubscription() {
        const subscription = await this.swRegistration.pushManager.getSubscription();
        this.isSubscribed = subscription !== null;
        
        if (this.isSubscribed) {
            // Проверяем, нужна ли синхронизация с сервером
            const lastEndpoint = localStorage.getItem('push_endpoint');
            const currentEndpoint = subscription.endpoint;
            
            // Отправляем на сервер только если endpoint изменился или не сохранён
            if (lastEndpoint !== currentEndpoint) {
                try {
                    await this._sendSubscriptionToServer(subscription);
                    localStorage.setItem('push_endpoint', currentEndpoint);
                } catch (error) {
                    console.warn('[PushNotifications] Ошибка синхронизации, переподписываемся:', error);
                
                // Если ошибка - возможно VAPID ключи изменились
                // Удаляем старую подписку и создаём новую
                try {
                    await subscription.unsubscribe();
                    console.log('[PushNotifications] Старая подписка удалена');
                    
                    // Создаём новую подписку с новыми VAPID ключами
                    const newSubscription = await this.swRegistration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: this._urlBase64ToUint8Array(this.vapidPublicKey)
                    });
                    
                    await this._sendSubscriptionToServer(newSubscription);
                    localStorage.setItem('push_endpoint', newSubscription.endpoint);
                    console.log('[PushNotifications] ✅ Автоматически переподписались');
                    this.isSubscribed = true;
                } catch (resubscribeError) {
                    console.error('[PushNotifications] Ошибка переподписки:', resubscribeError);
                    this.isSubscribed = false;
                }
            }
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
        
        try {
            // Удаляем старую подписку, если есть
            const existingSubscription = await this.swRegistration.pushManager.getSubscription();
            if (existingSubscription) {
                await existingSubscription.unsubscribe();
            }
            
            // Создаем новую подписку
            const subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this._urlBase64ToUint8Array(this.vapidPublicKey)
            });
            
            // Отправляем подписку на сервер
            await this._sendSubscriptionToServer(subscription);
            
            this.isSubscribed = true;
            console.log('[PushNotifications] ✅ Подписка успешна');
            return true;
            
        } catch (error) {
            console.error('[PushNotifications] Ошибка подписки:', error);
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

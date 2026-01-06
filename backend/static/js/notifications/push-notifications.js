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
        console.log('[PushNotifications][DEBUG] 🔍 Запрос VAPID ключа с сервера...');
        
        const response = await fetch('/api/v1/notifications/push/vapid-key/', {
            credentials: 'include'
        });
        
        console.log('[PushNotifications][DEBUG] 📡 Ответ сервера:', response.status, response.statusText);
        
        if (!response.ok) {
            throw new Error(`Не удалось получить VAPID ключ: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('[PushNotifications][DEBUG] 📦 Данные от сервера:', data);
        
        this.vapidPublicKey = data.vapid_public_key;
        
        if (!this.vapidPublicKey) {
            throw new Error('VAPID ключ отсутствует в ответе сервера');
        }
        
        console.log('[PushNotifications][DEBUG] ✅ VAPID ключ получен, длина:', this.vapidPublicKey.length);
        console.log('[PushNotifications][DEBUG] 🔑 VAPID ключ:', this.vapidPublicKey.substring(0, 20) + '...');
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
        console.log('[PushNotifications][DEBUG] 🔧 _urlBase64ToUint8Array вход:', {
            length: base64String.length,
            first20: base64String.substring(0, 20),
            last20: base64String.substring(base64String.length - 20)
        });
        
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        console.log('[PushNotifications][DEBUG] 🔧 Добавлено паддинга:', padding.length);
        
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        
        console.log('[PushNotifications][DEBUG] 🔧 После замены символов, длина:', base64.length);
        
        const rawData = window.atob(base64);
        console.log('[PushNotifications][DEBUG] 🔧 После atob, длина:', rawData.length);
        
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        
        console.log('[PushNotifications][DEBUG] 🔧 Uint8Array готов, длина:', outputArray.length);
        console.log('[PushNotifications][DEBUG] 🔧 Первые 10 байт:', Array.from(outputArray.slice(0, 10)));
        
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
        console.log('[PushNotifications][DEBUG] 🚀 Начало процесса подписки');
        
        if (!this.isSupported || !this.swRegistration || !this.vapidPublicKey) {
            console.error('[PushNotifications][DEBUG] ❌ Менеджер не инициализирован:', {
                isSupported: this.isSupported,
                swRegistration: !!this.swRegistration,
                vapidPublicKey: !!this.vapidPublicKey
            });
            return false;
        }
        
        // Проверяем разрешение
        console.log('[PushNotifications][DEBUG] 🔐 Проверка разрешений, текущее:', Notification.permission);
        
        if (Notification.permission === 'denied') {
            console.warn('[PushNotifications][DEBUG] ❌ Уведомления заблокированы пользователем');
            return false;
        }
        
        if (Notification.permission === 'default') {
            console.log('[PushNotifications][DEBUG] ❓ Запрос разрешения у пользователя...');
            const permission = await this.requestPermission();
            if (permission !== 'granted') {
                console.log('[PushNotifications][DEBUG] ❌ Разрешение не получено:', permission);
                return false;
            }
        }
        
        try {
            // Удаляем старую подписку, если есть (на случай смены VAPID ключей)
            const existingSubscription = await this.swRegistration.pushManager.getSubscription();
            console.log('[PushNotifications][DEBUG] 🔍 Существующая подписка:', existingSubscription ? 'найдена' : 'отсутствует');
            
            if (existingSubscription) {
                console.log('[PushNotifications][DEBUG] 🗑️ Удаляем старую подписку:', existingSubscription.endpoint.substring(0, 50) + '...');
                await existingSubscription.unsubscribe();
                console.log('[PushNotifications][DEBUG] ✅ Старая подписка удалена');
            }
            
            // Конвертируем VAPID ключ
            console.log('[PushNotifications][DEBUG] 🔄 Конвертация VAPID ключа в Uint8Array...');
            const applicationServerKey = this._urlBase64ToUint8Array(this.vapidPublicKey);
            console.log('[PushNotifications][DEBUG] ✅ Uint8Array создан, длина:', applicationServerKey.length);
            console.log('[PushNotifications][DEBUG] 🔢 Первые байты:', Array.from(applicationServerKey.slice(0, 5)));
            
            // Создаем push-подписку
            console.log('[PushNotifications][DEBUG] 📝 Создание новой подписки...');
            console.log('[PushNotifications][DEBUG] 🌐 Push Manager:', this.swRegistration.pushManager);
            
            // Проверяем поддерживаемые функции
            const pushManager = this.swRegistration.pushManager;
            console.log('[PushNotifications][DEBUG] 🔍 Push Manager возможности:', {
                hasGetSubscription: typeof pushManager.getSubscription === 'function',
                hasSubscribe: typeof pushManager.subscribe === 'function',
                hasPermissionState: typeof pushManager.permissionState === 'function'
            });
            
            const subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            
            console.log('[PushNotifications][DEBUG] ✅ Push-подписка создана успешно!');
            console.log('[PushNotifications][DEBUG] 🌐 Endpoint:', subscription.endpoint.substring(0, 70) + '...');
            console.log('[PushNotifications][DEBUG] 🔑 Keys:', Object.keys(subscription.toJSON().keys));
            
            // Отправляем подписку на сервер
            console.log('[PushNotifications][DEBUG] 📤 Отправка подписки на сервер...');
            await this._sendSubscriptionToServer(subscription);
            
            this.isSubscribed = true;
            console.log('[PushNotifications][DEBUG] 🎉 Подписка завершена успешно!');
            return true;
            
        } catch (error) {
            console.error('[PushNotifications][DEBUG] ❌ ОШИБКА ПОДПИСКИ:', error);
            console.error('[PushNotifications][DEBUG] 📋 Тип ошибки:', error.name);
            console.error('[PushNotifications][DEBUG] 💬 Сообщение:', error.message);
            console.error('[PushNotifications][DEBUG] 📚 Stack:', error.stack);
            
            // Дополнительная диагностика
            if (error.name === 'AbortError') {
                console.error('[PushNotifications][DEBUG] 🔍 AbortError обычно означает:');
                console.error('[PushNotifications][DEBUG] 1. Невалидный VAPID ключ');
                console.error('[PushNotifications][DEBUG] 2. Проблема с push-сервисом (FCM/Mozilla)');
                console.error('[PushNotifications][DEBUG] 3. Неправильный формат applicationServerKey');
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

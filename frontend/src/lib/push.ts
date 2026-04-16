/**
 * Web Push утилиты для управления подписками
 */

import { registerAppServiceWorker } from "@/lib/pwa";

/**
 * Конвертирует base64 строку в Uint8Array для applicationServerKey
 */
export function urlBase64ToUint8Array(base64String: string): Uint8Array {
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
 * Проверяет поддержку Web Push браузером
 */
export function isPushSupported(): boolean {
    if (typeof window === 'undefined') return false;
    
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
 * Получает текущее разрешение на уведомления
 */
export function getNotificationPermission(): NotificationPermission {
    if (typeof window === 'undefined' || !('Notification' in window)) {
        return 'default';
    }
    return Notification.permission;
}

/**
 * Запрашивает разрешение на уведомления
 */
export async function requestNotificationPermission(): Promise<NotificationPermission> {
    if (typeof window === 'undefined' || !('Notification' in window)) {
        return 'default';
    }
    
    return await Notification.requestPermission();
}

/**
 * Регистрирует Service Worker
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration> {
    const registration = await registerAppServiceWorker();
    if (!registration) {
        throw new Error('Service Worker не поддерживается');
    }

    console.log('[PushNotifications] Service Worker зарегистрирован:', registration.scope);
    return registration;
}

/**
 * Получает или создает push подписку
 */
export async function subscribeToPush(
    registration: ServiceWorkerRegistration,
    vapidPublicKey: string
): Promise<PushSubscription> {
    const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);
    
    const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey as BufferSource
    });
    
    console.log('[PushNotifications] Push подписка создана');
    return subscription;
}

/**
 * Отписывается от push уведомлений
 */
export async function unsubscribeFromPush(
    registration: ServiceWorkerRegistration
): Promise<boolean> {
    const subscription = await registration.pushManager.getSubscription();
    
    if (!subscription) {
        return false;
    }
    
    const success = await subscription.unsubscribe();
    console.log('[PushNotifications] Push подписка удалена');
    return success;
}

/**
 * Получает текущую push подписку
 */
export async function getCurrentSubscription(
    registration: ServiceWorkerRegistration
): Promise<PushSubscription | null> {
    return await registration.pushManager.getSubscription();
}

/**
 * Конвертирует PushSubscription в формат для отправки на сервер
 */
export function serializeSubscription(subscription: PushSubscription) {
    const key = subscription.getKey('p256dh');
    const token = subscription.getKey('auth');
    
    return {
        endpoint: subscription.endpoint,
        keys: {
            p256dh: key ? btoa(String.fromCharCode(...new Uint8Array(key))) : '',
            auth: token ? btoa(String.fromCharCode(...new Uint8Array(token))) : ''
        }
    };
}

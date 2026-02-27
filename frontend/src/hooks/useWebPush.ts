/**
 * React хук для управления Web Push уведомлениями
 */

import { useState, useEffect, useCallback } from 'react';
import {
    isPushSupported,
    getNotificationPermission,
    requestNotificationPermission,
    registerServiceWorker,
    subscribeToPush,
    unsubscribeFromPush,
    getCurrentSubscription,
    serializeSubscription,
} from '@/lib/push';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';

interface UseWebPushReturn {
    isSupported: boolean;
    isSubscribed: boolean;
    isLoading: boolean;
    permission: NotificationPermission;
    subscribe: () => Promise<boolean>;
    unsubscribe: () => Promise<boolean>;
    requestPermission: () => Promise<NotificationPermission>;
}

/**
 * Хук для управления Web Push подписками
 */
export function useWebPush(): UseWebPushReturn {
    const [isSupported] = useState(() => isPushSupported());
    const [isSubscribed, setIsSubscribed] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [permission, setPermission] = useState<NotificationPermission>('default');
    const [swRegistration, setSwRegistration] = useState<ServiceWorkerRegistration | null>(null);
    const [vapidPublicKey, setVapidPublicKey] = useState<string | null>(null);

    // Инициализация: проверка поддержки и текущего статуса
    useEffect(() => {
        if (!isSupported) {
            setIsLoading(false);
            return;
        }

        async function init() {
            try {
                // Получаем разрешение
                const perm = getNotificationPermission();
                setPermission(perm);

                // Получаем VAPID ключ
                const response = await apiClient.getVapidPublicKey();
                setVapidPublicKey(response.vapid_public_key);

                // Регистрируем Service Worker
                const registration = await registerServiceWorker();
                setSwRegistration(registration);

                // Проверяем текущую подписку
                const subscription = await getCurrentSubscription(registration);
                setIsSubscribed(subscription !== null);

                console.log('[useWebPush] Инициализация завершена, подписка:', subscription !== null);
            } catch (error) {
                console.error('[useWebPush] Ошибка инициализации:', error);
                toast.error('Не удалось инициализировать уведомления');
            } finally {
                setIsLoading(false);
            }
        }

        init();
    }, [isSupported]);

    // Запрос разрешения на уведомления
    const requestPermission = useCallback(async (): Promise<NotificationPermission> => {
        const perm = await requestNotificationPermission();
        setPermission(perm);
        return perm;
    }, []);

    // Подписаться на push уведомления
    const subscribe = useCallback(async (): Promise<boolean> => {
        if (!isSupported || !swRegistration || !vapidPublicKey) {
            toast.error('Web Push не поддерживается');
            return false;
        }

        setIsLoading(true);

        try {
            // Запрашиваем разрешение если нужно
            if (permission !== 'granted') {
                const perm = await requestPermission();
                if (perm !== 'granted') {
                    toast.error('Разрешение на уведомления отклонено');
                    return false;
                }
            }

            // Создаем подписку
            const subscription = await subscribeToPush(swRegistration, vapidPublicKey);
            const subscriptionData = serializeSubscription(subscription);

            // Отправляем на сервер
            await apiClient.subscribePush({
                ...subscriptionData,
                device_name: getBrowserInfo(),
            });

            setIsSubscribed(true);
            toast.success('Подписка на уведомления активирована');
            return true;
        } catch (error) {
            console.error('[useWebPush] Ошибка подписки:', error);
            toast.error('Не удалось подписаться на уведомления');
            return false;
        } finally {
            setIsLoading(false);
        }
    }, [isSupported, swRegistration, vapidPublicKey, permission, requestPermission]);

    // Отписаться от push уведомлений
    const unsubscribe = useCallback(async (): Promise<boolean> => {
        if (!isSupported || !swRegistration) {
            return false;
        }

        setIsLoading(true);

        try {
            // Удаляем локальную подписку
            const success = await unsubscribeFromPush(swRegistration);

            if (success) {
                // Удаляем на сервере
                await apiClient.unsubscribePush();

                setIsSubscribed(false);
                toast.success('Подписка отменена');
                return true;
            }

            return false;
        } catch (error) {
            console.error('[useWebPush] Ошибка отписки:', error);
            toast.error('Не удалось отписаться от уведомлений');
            return false;
        } finally {
            setIsLoading(false);
        }
    }, [isSupported, swRegistration]);

    return {
        isSupported,
        isSubscribed,
        isLoading,
        permission,
        subscribe,
        unsubscribe,
        requestPermission,
    };
}

/**
 * Получает информацию о браузере для device_name
 */
function getBrowserInfo(): string {
    if (typeof window === 'undefined') return 'Unknown';

    const ua = navigator.userAgent;
    let browser = 'Unknown';

    if (ua.indexOf('Firefox') > -1) {
        browser = 'Firefox';
    } else if (ua.indexOf('Edge') > -1) {
        browser = 'Edge';
    } else if (ua.indexOf('Chrome') > -1) {
        browser = 'Chrome';
    } else if (ua.indexOf('Safari') > -1) {
        browser = 'Safari';
    }

    return browser;
}

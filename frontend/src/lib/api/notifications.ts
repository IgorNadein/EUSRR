/* eslint-disable @typescript-eslint/no-explicit-any */
import type { RequestFn } from './utils';

export type UnreadNotificationsSummary = {
    total: number;
    verbs: Array<{
        verb: string;
        unread: number;
    }>;
    procurement_requests?: Array<{
        request_id: number;
        unread: number;
    }>;
};

export function createNotificationsApi(request: RequestFn) {
    return {
        getNotifications: (params?: { page?: number; page_size?: number; unread_only?: boolean }) => {
            const qp = new URLSearchParams();
            if (params?.page) qp.append('page', String(params.page));
            if (params?.page_size) qp.append('page_size', String(params.page_size));
            if (params?.unread_only) qp.append('unread_only', 'true');
            const qs = qp.toString();
            return request(qs ? `/api/v1/notifications/?${qs}` : '/api/v1/notifications/');
        },
        getUnreadNotificationsCount: (): Promise<{ count: number }> => request('/api/v1/notifications/count/'),
        getUnreadNotificationsSummary: (): Promise<UnreadNotificationsSummary> => request('/api/v1/notifications/summary/'),
        markNotificationAsRead: (id: number): Promise<void> => request(`/api/v1/notifications/${id}/read/`, { method: 'POST' }),
        markAllNotificationsAsRead: (): Promise<void> => request('/api/v1/notifications/read-all/', { method: 'POST' }),
        markCategoryAsRead: async (category: string): Promise<{ status: string; count: number }> => {
            const { getVerbsByCategory } = await import('../verbTranslations');
            const verbs = getVerbsByCategory(category);
            return request('/api/v1/notifications/category/read/', { method: 'POST', body: JSON.stringify({ verbs, category }) });
        },
        // Push
        getVapidPublicKey: (): Promise<{ vapid_public_key: string }> => request('/api/v1/notifications/push/vapid-key/'),
        subscribePush: (data: { endpoint: string; keys: { p256dh: string; auth: string }; device_name?: string }): Promise<{ status: string; message: string; created: boolean }> =>
            request('/api/v1/notifications/push/subscribe/', { method: 'POST', body: JSON.stringify(data) }),
        unsubscribePush: (endpoint?: string): Promise<{ status: string; message: string }> =>
            request('/api/v1/notifications/push/unsubscribe/', { method: 'DELETE', body: JSON.stringify({ endpoint }) }),
        getPushSubscriptions: (): Promise<{ subscriptions: any[] }> => request('/api/v1/notifications/push/subscriptions/'),
        // CRUD
        deleteNotification: (id: number): Promise<void> => request(`/api/v1/notifications/${id}/`, { method: 'DELETE' }),
        deleteAllReadNotifications: (): Promise<{ status: string; count: number }> => request('/api/v1/notifications/delete-all-read/', { method: 'DELETE' }),
        // Preferences
        getNotificationPreferences: () => request('/api/v1/notifications/preferences/'),
        updateNotificationPreferences: (data: Record<string, any>) => request('/api/v1/notifications/preferences/', { method: 'PUT', body: JSON.stringify(data) }),
        getVerbTypes: (): Promise<{ verb_types: any[] }> => request('/api/v1/notifications/verb-types/'),
    };
}

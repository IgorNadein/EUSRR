"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import apiClient from '@/lib/api';
import wsManager from '@/lib/websocketManager';
import { getVerbCategory } from '@/lib/verbTranslations';

const NOTIFICATIONS_SYNC_INTERVAL_MS = 30000;
const UNREAD_NOTIFICATIONS_PAGE_SIZE = 50;

export type NotificationItem = {
  id: number;
  is_read?: boolean;
  unread?: boolean;
  category?: string;
  title?: string;
  verb?: string;
  description?: string;
  short_message?: string;
  message?: string;
  timestamp?: string;
  created_at?: string;
  action_url?: string;
  data?: Record<string, unknown> | null;
  [key: string]: unknown;
};

type NotificationSocketEvent = {
  type: string;
  notification?: NotificationItem;
  notification_id?: number;
  notification_ids?: number[];
  unread_count?: number;
  count?: number;
};

interface NotificationsContextType {
  notifications: NotificationItem[];
  unreadCount: number;
  unreadCategoryCounts: Record<string, number>;
  unreadProcurementRequestCounts: Record<number, number>;
  loading: boolean;
  error: Error | null;
  refreshUnreadSummary: () => Promise<void>;
  markAsRead: (id: number) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  markCategoryAsRead: (category: string) => Promise<void>;
  deleteNotification: (id: number) => Promise<void>;
  deleteAllRead: () => Promise<number>;
}

const NotificationsContext = createContext<NotificationsContextType | undefined>(undefined);

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [unreadCategoryCounts, setUnreadCategoryCounts] = useState<Record<string, number>>({});
  const [unreadProcurementRequestCounts, setUnreadProcurementRequestCounts] = useState<Record<number, number>>({});
  const [isWsConnected, setIsWsConnected] = useState(
    typeof window !== 'undefined' && wsManager.getState() === WebSocket.OPEN
  );
  const fetchInFlightRef = useRef<Promise<void> | null>(null);
  const summaryInFlightRef = useRef<Promise<void> | null>(null);

  const applyUnreadSummary = useCallback((summary: {
    total?: number;
    verbs?: Array<{ verb?: string; unread?: number }>;
    procurement_requests?: Array<{ request_id?: number; unread?: number }>;
  }) => {
    const nextCategoryCounts: Record<string, number> = {};
    const nextProcurementRequestCounts: Record<number, number> = {};
    const verbs = Array.isArray(summary.verbs) ? summary.verbs : [];
    const procurementRequests = Array.isArray(summary.procurement_requests)
      ? summary.procurement_requests
      : [];

    verbs.forEach((item) => {
      if (!item.verb || typeof item.unread !== 'number' || item.unread <= 0) {
        return;
      }
      const category = getVerbCategory(item.verb);
      nextCategoryCounts[category] = (nextCategoryCounts[category] || 0) + item.unread;
    });

    procurementRequests.forEach((item) => {
      const requestId = Number(item.request_id);
      if (!Number.isFinite(requestId) || requestId <= 0 || typeof item.unread !== 'number' || item.unread <= 0) {
        return;
      }
      nextProcurementRequestCounts[requestId] = item.unread;
    });

    setUnreadCategoryCounts(nextCategoryCounts);
    setUnreadProcurementRequestCounts(nextProcurementRequestCounts);
    setUnreadCount(typeof summary.total === 'number' ? summary.total : verbs.reduce((sum, item) => sum + (item.unread || 0), 0));
  }, []);

  const syncUnreadNotifications = useCallback(async (showLoader = false) => {
    if (fetchInFlightRef.current) {
      return fetchInFlightRef.current;
    }

    const request = (async () => {
      if (showLoader) {
        setLoading(true);
      }

      try {
        const data = await apiClient.getNotifications({
          page_size: UNREAD_NOTIFICATIONS_PAGE_SIZE,
          unread_only: true,
        });
        const notifs = data.notifications || data.results || data;
        const notificationsArray = Array.isArray(notifs) ? notifs : [];
        setNotifications(notificationsArray);
        setUnreadCount(data.unread_count ?? notificationsArray.length);
        setError(null);
      } catch (err) {
        setError(err as Error);
        if (showLoader) {
          setNotifications([]);
        }
      } finally {
        if (showLoader) {
          setLoading(false);
        }
        fetchInFlightRef.current = null;
      }
    })();

    fetchInFlightRef.current = request;
    return request;
  }, []);

  const syncUnreadSummary = useCallback(async () => {
    if (summaryInFlightRef.current) {
      return summaryInFlightRef.current;
    }

    const request = (async () => {
      try {
        const summary = await apiClient.getUnreadNotificationsSummary();
        applyUnreadSummary(summary);
        setError(null);
      } catch (err) {
        setError(err as Error);
      } finally {
        summaryInFlightRef.current = null;
      }
    })();

    summaryInFlightRef.current = request;
    return request;
  }, [applyUnreadSummary]);

  // Загрузка начальных данных
  useEffect(() => {
    void syncUnreadNotifications(true);
    void syncUnreadSummary();
  }, [syncUnreadNotifications, syncUnreadSummary]);

  // ЕДИНСТВЕННЫЙ WebSocket через singleton manager
  useEffect(() => {
    if (typeof window === 'undefined' || !localStorage.getItem('access_token')) {
      console.log('[NotificationsContext] WebSocket disabled: not in browser or not authenticated');
      return;
    }

    const unsubscribeMessages = wsManager.subscribe((event) => {
      const data = event as NotificationSocketEvent;

      if (['ping', 'list_update', 'new_message', 'marked_read', 'message_edited', 'reaction_added', 'reaction_removed', 'poll_update'].includes(data.type)) {
        return;
      }

      const incomingNotification = data.notification;

      if (data.type === 'notification' && incomingNotification) {
        setNotifications(prev => {
          if (prev.some(n => n.id === incomingNotification.id)) {
            return prev;
          }
          return [incomingNotification, ...prev];
        });

        const isRead = incomingNotification.is_read ?? !incomingNotification.unread;
        if (!isRead) {
          setUnreadCount(prev => prev + 1);
          if (incomingNotification.verb) {
            const category = getVerbCategory(incomingNotification.verb);
            setUnreadCategoryCounts(prev => ({
              ...prev,
              [category]: (prev[category] || 0) + 1,
            }));
            if (category === 'Закупки') {
              const requestId = Number(incomingNotification.data?.request_id);
              if (Number.isFinite(requestId) && requestId > 0) {
                setUnreadProcurementRequestCounts(prev => ({
                  ...prev,
                  [requestId]: (prev[requestId] || 0) + 1,
                }));
              }
            }
          }
        }
        return;
      }

      if (data.type === 'notification_read' && typeof data.notification_id === 'number') {
        setNotifications(prev =>
          prev.map(n => (n.id === data.notification_id ? { ...n, is_read: true, unread: false } : n))
        );
        if (typeof data.unread_count === 'number') {
          setUnreadCount(data.unread_count);
        }
        void syncUnreadSummary();
        return;
      }

      if (data.type === 'notifications_read_all') {
        const ids = Array.isArray(data.notification_ids) ? new Set<number>(data.notification_ids) : null;
        setNotifications(prev =>
          prev.map((notification) => {
            if (!ids || ids.has(notification.id)) {
              return { ...notification, is_read: true, unread: false };
            }
            return notification;
          })
        );
        if (typeof data.unread_count === 'number') {
          setUnreadCount(data.unread_count);
        }
        void syncUnreadSummary();
        return;
      }

      if (['unread_count', 'notification_count_update'].includes(data.type) && typeof data.count === 'number') {
        setUnreadCount(data.count);
        void syncUnreadSummary();
        void syncUnreadNotifications(false);
      }
    });

    const unsubscribeStatus = wsManager.subscribeStatus((status) => {
      setIsWsConnected(status.isConnected);
    });

    return () => {
      unsubscribeMessages();
      unsubscribeStatus();
    };
  }, [syncUnreadNotifications, syncUnreadSummary]);

  // Регулярная сверка с API нужна даже при живом WebSocket: часть событий может не дойти по сокету.
  useEffect(() => {
    if (typeof window === 'undefined' || !localStorage.getItem('access_token')) {
      return;
    }

    const sync = () => {
      void syncUnreadSummary();
      void syncUnreadNotifications(false);
    };

    sync();

    const intervalId = window.setInterval(sync, NOTIFICATIONS_SYNC_INTERVAL_MS);
    const handleFocus = () => sync();
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        sync();
      }
    };

    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [syncUnreadNotifications, syncUnreadSummary]);

  useEffect(() => {
    if (!isWsConnected) {
      return;
    }

    void syncUnreadSummary();
    void syncUnreadNotifications(false);
  }, [isWsConnected, syncUnreadNotifications, syncUnreadSummary]);

  const markAsRead = useCallback(async (id: number) => {
    await apiClient.markNotificationAsRead(id);
    let readVerb: string | undefined;
    setNotifications(prev =>
      prev.map(n => {
        if (n.id !== id) {
          return n;
        }
        if (!n.is_read && n.unread !== false) {
          readVerb = n.verb;
        }
        return { ...n, is_read: true, unread: false };
      })
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
    if (readVerb) {
      const category = getVerbCategory(readVerb);
      setUnreadCategoryCounts(prev => ({
        ...prev,
        [category]: Math.max(0, (prev[category] || 0) - 1),
      }));
    }
    void syncUnreadSummary();
  }, [syncUnreadSummary]);

  const markAllAsRead = useCallback(async () => {
    await apiClient.markAllNotificationsAsRead();
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true, unread: false })));
    setUnreadCount(0);
    setUnreadCategoryCounts({});
    setUnreadProcurementRequestCounts({});
    void syncUnreadSummary();
  }, [syncUnreadSummary]);

  const markCategoryAsRead = useCallback(async (category: string) => {
    await apiClient.markCategoryAsRead(category);
    setNotifications(prev => {
      const updatedNotifications = prev.map(n =>
        n.verb && getVerbCategory(n.verb) === category
          ? { ...n, is_read: true, unread: false }
          : n
      );
      const newUnreadCount = updatedNotifications.filter(n => !n.is_read && n.unread !== false).length;
      setUnreadCount(newUnreadCount);
      return updatedNotifications;
    });
    setUnreadCategoryCounts(prev => {
      const next = { ...prev };
      delete next[category];
      return next;
    });
    if (category === 'Закупки') {
      setUnreadProcurementRequestCounts({});
    }
    void syncUnreadSummary();
  }, [syncUnreadSummary]);

  const deleteNotification = useCallback(async (id: number) => {
    await apiClient.deleteNotification(id);
    setNotifications(prev => prev.filter(n => n.id !== id));
    void syncUnreadSummary();
  }, [syncUnreadSummary]);

  const deleteAllRead = useCallback(async (): Promise<number> => {
    const result = await apiClient.deleteAllReadNotifications();
    setNotifications(prev => prev.filter(n => !n.is_read));
    return result.count;
  }, []);

  const value = {
    notifications,
    unreadCount,
    unreadCategoryCounts,
    unreadProcurementRequestCounts,
    loading,
    error,
    refreshUnreadSummary: syncUnreadSummary,
    markAsRead,
    markAllAsRead,
    markCategoryAsRead,
    deleteNotification,
    deleteAllRead,
  };

  return (
    <NotificationsContext.Provider value={value}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within NotificationsProvider');
  }
  return context;
}

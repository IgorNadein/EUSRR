"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import apiClient from '@/lib/api';
import wsManager from '@/lib/websocketManager';

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
  loading: boolean;
  error: Error | null;
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
  const [isWsConnected, setIsWsConnected] = useState(
    typeof window !== 'undefined' && wsManager.getState() === WebSocket.OPEN
  );
  const fetchInFlightRef = useRef<Promise<void> | null>(null);

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
          page_size: 50,
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

  // Загрузка начальных данных
  useEffect(() => {
    void syncUnreadNotifications(true);
  }, [syncUnreadNotifications]);

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
        return;
      }

      if (data.type === 'unread_count' && typeof data.count === 'number') {
        setUnreadCount(data.count);
      }
    });

    const unsubscribeStatus = wsManager.subscribeStatus((status) => {
      setIsWsConnected(status.isConnected);
    });

    return () => {
      unsubscribeMessages();
      unsubscribeStatus();
    };
  }, []);

  // API fallback на время разрыва WebSocket и при возврате фокуса
  useEffect(() => {
    if (typeof window === 'undefined' || isWsConnected || !localStorage.getItem('access_token')) {
      return;
    }

    const sync = () => {
      void syncUnreadNotifications(false);
    };

    sync();

    const intervalId = window.setInterval(sync, 15000);
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
  }, [isWsConnected, syncUnreadNotifications]);

  useEffect(() => {
    if (!isWsConnected) {
      return;
    }

    void syncUnreadNotifications(false);
  }, [isWsConnected, syncUnreadNotifications]);

  const markAsRead = useCallback(async (id: number) => {
    await apiClient.markNotificationAsRead(id);
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, is_read: true, unread: false } : n))
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
  }, []);

  const markAllAsRead = useCallback(async () => {
    await apiClient.markAllNotificationsAsRead();
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true, unread: false })));
    setUnreadCount(0);
  }, []);

  const markCategoryAsRead = useCallback(async (category: string) => {
    await apiClient.markCategoryAsRead(category);
    setNotifications(prev => {
      const updatedNotifications = prev.map(n =>
        n.category === category ? { ...n, is_read: true, unread: false } : n
      );
      const newUnreadCount = updatedNotifications.filter(n => !n.is_read && n.unread !== false).length;
      setUnreadCount(newUnreadCount);
      return updatedNotifications;
    });
  }, []);

  const deleteNotification = useCallback(async (id: number) => {
    await apiClient.deleteNotification(id);
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const deleteAllRead = useCallback(async (): Promise<number> => {
    const result = await apiClient.deleteAllReadNotifications();
    setNotifications(prev => prev.filter(n => !n.is_read));
    return result.count;
  }, []);

  const value = {
    notifications,
    unreadCount,
    loading,
    error,
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

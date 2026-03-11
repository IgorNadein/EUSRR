"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import apiClient from '@/lib/api';
import wsManager from '@/lib/websocketManager';

interface NotificationsContextType {
  notifications: any[];
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
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);

  // Загрузка начальных данных
  useEffect(() => {
    async function fetchNotifications() {
      try {
        const data = await apiClient.getNotifications({ 
          page_size: 50, 
          unread_only: true 
        });
        const notifs = data.notifications || data.results || data;
        const notificationsArray = Array.isArray(notifs) ? notifs : [];
        setNotifications(notificationsArray);
        setUnreadCount(data.unread_count ?? notificationsArray.length);
      } catch (err) {
        setError(err as Error);
        setNotifications([]);
      } finally {
        setLoading(false);
      }
    }

    fetchNotifications();
  }, []);

  // ЕДИНСТВЕННЫЙ WebSocket через singleton manager
  useEffect(() => {
    if (typeof window === 'undefined' || !localStorage.getItem('access_token')) {
      console.log('[NotificationsContext] WebSocket disabled: not in browser or not authenticated');
      return;
    }

    let unsubscribe: (() => void) | null = null;

    const setupWebSocket = () => {
      // Подписываемся на сообщения через singleton
      unsubscribe = wsManager.subscribe((data) => {
        // Игнорируем служебные события
        if (['ping', 'list_update', 'new_message', 'marked_read', 'message_edited', 'reaction_added', 'reaction_removed', 'poll_update'].includes(data.type)) {
          return;
        }

        // Новое уведомление
        if (data.type === 'notification' && data.notification) {
          console.log('[NotificationsContext] New notification:', data.notification);
          
          setNotifications(prev => {
            if (prev.some(n => n.id === data.notification.id)) {
              return prev;
            }
            return [data.notification, ...prev];
          });

          if (!data.notification.is_read) {
            setUnreadCount(prev => prev + 1);
          }
        }

        // Обновление счетчика
        if (data.type === 'unread_count' && typeof data.count === 'number') {
          console.log('[NotificationsContext] Unread count update:', data.count);
          setUnreadCount(data.count);
        }
      });
    };

    setupWebSocket();

    return () => {
      if (unsubscribe) {
        unsubscribe();
      }
    };
  }, []);

  // Синхронизация между вкладками через CustomEvent
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleMarkedRead = (e: Event) => {
      const customEvent = e as CustomEvent;
      const { id } = customEvent.detail;
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    };

    const handleAllMarkedRead = () => {
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    };

    window.addEventListener('notification-marked-read', handleMarkedRead);
    window.addEventListener('all-notifications-marked-read', handleAllMarkedRead);

    return () => {
      window.removeEventListener('notification-marked-read', handleMarkedRead);
      window.removeEventListener('all-notifications-marked-read', handleAllMarkedRead);
    };
  }, []);

  const markAsRead = useCallback(async (id: number) => {
    await apiClient.markNotificationAsRead(id);
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, is_read: true } : n))
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
    
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('notification-marked-read', { detail: { id } }));
    }
  }, []);

  const markAllAsRead = useCallback(async () => {
    await apiClient.markAllNotificationsAsRead();
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnreadCount(0);
    
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('all-notifications-marked-read'));
    }
  }, []);

  const markCategoryAsRead = useCallback(async (category: string) => {
    await apiClient.markCategoryAsRead(category);
    const updatedNotifications = notifications.map(n =>
      n.category === category ? { ...n, is_read: true } : n
    );
    setNotifications(updatedNotifications);
    const newUnreadCount = updatedNotifications.filter(n => !n.is_read).length;
    setUnreadCount(newUnreadCount);
  }, [notifications]);

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

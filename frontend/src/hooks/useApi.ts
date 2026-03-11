"use client";

import { useEffect, useState } from 'react';
import apiClient from '@/lib/api';
import type { User, Post, PaginatedResponse } from '@/types/api';

export function useCurrentUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchUser() {
      try {
        const data = await apiClient.getCurrentUser();
        setUser(data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchUser();
  }, []);

  return { user, loading, error };
}

export function useEmployees(params?: { search?: string; department?: string }) {
  const [employees, setEmployees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchEmployees() {
      try {
        setLoading(true);
        const data = await apiClient.getEmployees(params);
        setEmployees(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchEmployees();
  }, [params?.search, params?.department]);

  return { employees, loading, error, refetch: () => {} };
}

export function useDepartments() {
  const [departments, setDepartments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchDepartments() {
      try {
        const data = await apiClient.getDepartments();
        setDepartments(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchDepartments();
  }, []);

  return { departments, loading, error };
}

export function usePosts(params?: { page?: number; search?: string }) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    async function fetchPosts() {
      try {
        setLoading(true);
        const data: PaginatedResponse<Post> = await apiClient.getPosts(params);
        setPosts(data.results);
        setHasMore(!!data.next);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchPosts();
  }, [params?.page, params?.search]);

  return { posts, loading, error, hasMore, refetch: () => {} };
}

export function useDocuments(params?: { search?: string; type?: string }) {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchDocuments() {
      try {
        const data = await apiClient.getDocuments(params);
        setDocuments(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchDocuments();
  }, [params?.search, params?.type]);

  return { documents, loading, error };
}

export function useRequests(params?: { status?: string; type?: string }) {
  const [requests, setRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchRequests() {
      try {
        const data = await apiClient.getRequests(params);
        setRequests(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchRequests();
  }, [params?.status, params?.type]);

  return { requests, loading, error };
}

export function useChats() {
  const [chats, setChats] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchChats() {
      try {
        const data = await apiClient.getChats();
        setChats(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchChats();
  }, []);

  return { chats, loading, error };
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);

  // Загрузка начальных данных
  useEffect(() => {
    async function fetchNotifications() {
      try {
        // Для бейджей загружаем только непрочитанные (первые 50)
        const data = await apiClient.getNotifications({ 
          page_size: 50, 
          unread_only: true 
        });
        // Бэкенд возвращает { notifications: [...], unread_count: N }
        const notifs = data.notifications || data.results || data;
        // Убеждаемся что notifs это массив
        const notificationsArray = Array.isArray(notifs) ? notifs : [];
        setNotifications(notificationsArray);
        // Используем unread_count из API или считаем сами
        setUnreadCount(data.unread_count ?? notificationsArray.length);
      } catch (err) {
        setError(err as Error);
        setNotifications([]); // В случае ошибки устанавливаем пустой массив
      } finally {
        setLoading(false);
      }
    }

    fetchNotifications();
  }, []);

  // WebSocket для realtime обновлений
  useEffect(() => {
    // Проверяем что мы в браузере и пользователь авторизован
    if (typeof window === 'undefined' || !localStorage.getItem('access_token')) {
      console.log('[Notifications] WebSocket disabled: not in browser or not authenticated');
      return;
    }

    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;

    const connect = () => {
      try {
        // Используем функцию getWebSocketUrl для определения URL
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:9000';
        const protocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:';
        const host = backendUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
        let wsUrl = `${protocol}//${host}/ws/`;

        // Добавляем токен
        const token = localStorage.getItem('access_token');
        if (token) {
          wsUrl += `?token=${token}`;
        }

        console.log('[Notifications] WebSocket connecting to:', wsUrl);
        console.log('[Notifications] Backend URL:', backendUrl);
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('[Notifications] WebSocket connected');
          reconnectAttempts = 0;
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            // Игнорируем служебные события
            if (['ping', 'list_update', 'new_message', 'marked_read', 'message_edited', 'reaction_added', 'reaction_removed', 'poll_update'].includes(data.type)) {
              return;
            }

            // Новое уведомление
            if (data.type === 'notification' && data.notification) {
              console.log('[Notifications] New notification:', data.notification);
              
              // Добавляем в начало списка если это новое
              setNotifications(prev => {
                // Проверяем не дубликат ли
                if (prev.some(n => n.id === data.notification.id)) {
                  return prev;
                }
                return [data.notification, ...prev];
              });

              // Обновляем счетчик если непрочитанное
              if (!data.notification.is_read) {
                setUnreadCount(prev => prev + 1);
              }
            }

            // Обновление счетчика
            if (data.type === 'unread_count' && typeof data.count === 'number') {
              console.log('[Notifications] Unread count update:', data.count);
              setUnreadCount(data.count);
            }
          } catch (error) {
            console.error('[Notifications] Parse error:', error);
          }
        };

        ws.onerror = (error) => {
          console.error('[Notifications] WebSocket error:', error);
          console.error('[Notifications] WebSocket URL was:', wsUrl);
          console.error('[Notifications] WebSocket state:', ws?.readyState);
        };

        ws.onclose = () => {
          console.log('[Notifications] WebSocket disconnected');
          ws = null;

          // Автоматический reconnect
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
            console.log(`[Notifications] Reconnecting in ${delay}ms... (${reconnectAttempts}/${maxReconnectAttempts})`);
            reconnectTimeout = setTimeout(connect, delay);
          }
        };
      } catch (error) {
        console.error('[Notifications] Connection failed:', error);
      }
    };

    connect();

    // Cleanup
    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (ws) {
        ws.close();
      }
    };
  }, []);

  // Синхронизация между экземплярами хука через CustomEvent
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

    const handleCategoryMarkedRead = async (e: Event) => {
      const customEvent = e as CustomEvent;
      const { category, verbs } = customEvent.detail;
      
      // Используем переданные verb'ы для проверки
      setNotifications(prev => {
        const updated = prev.map(n => {
          const isInCategory = verbs.includes(n.verb);
          return isInCategory ? { ...n, is_read: true } : n;
        });
        
        // Пересчитываем счетчик
        const newUnreadCount = updated.filter(n => !n.is_read).length;
        setUnreadCount(newUnreadCount);
        
        return updated;
      });
    };

    const handleDeleted = (e: Event) => {
      const customEvent = e as CustomEvent;
      const { id, wasUnread } = customEvent.detail;
      setNotifications(prev => prev.filter(n => n.id !== id));
      if (wasUnread) {
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    };

    window.addEventListener('notification-marked-read', handleMarkedRead);
    window.addEventListener('notifications-all-marked-read', handleAllMarkedRead);
    window.addEventListener('category-marked-read', handleCategoryMarkedRead);
    window.addEventListener('notification-deleted', handleDeleted);

    return () => {
      window.removeEventListener('notification-marked-read', handleMarkedRead);
      window.removeEventListener('notifications-all-marked-read', handleAllMarkedRead);
      window.removeEventListener('category-marked-read', handleCategoryMarkedRead);
      window.removeEventListener('notification-deleted', handleDeleted);
    };
  }, []);

  const markAsRead = async (id: number) => {
    try {
      await apiClient.markNotificationAsRead(id);
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
      
      // Синхронизация между экземплярами хука через CustomEvent
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('notification-marked-read', { 
          detail: { id } 
        }));
      }
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  };

  const markAllAsRead = async () => {
    try {
      await apiClient.markAllNotificationsAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
      
      // Синхронизация между экземплярами хука через CustomEvent
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('notifications-all-marked-read'));
      }
    } catch (err) {
      console.error('Failed to mark all notifications as read:', err);
    }
  };

  const deleteNotification = async (id: number) => {
    try {
      await apiClient.deleteNotification(id);
      
      // Проверяем было ли непрочитанным ДО удаления
      const deletedNotif = notifications.find(n => n.id === id);
      const wasUnread = deletedNotif && !deletedNotif.is_read;
      
      setNotifications(prev => prev.filter(n => n.id !== id));
      if (wasUnread) {
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
      
      // Синхронизация между экземплярами хука через CustomEvent
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('notification-deleted', { 
          detail: { id, wasUnread } 
        }));
      }
    } catch (err) {
      console.error('Failed to delete notification:', err);
    }
  };

  const deleteAllRead = async () => {
    try {
      const result = await apiClient.deleteAllReadNotifications();
      setNotifications(prev => prev.filter(n => !n.is_read));
      return result.count;
    } catch (err) {
      console.error('Failed to delete all read notifications:', err);
      return 0;
    }
  };

  const markCategoryAsRead = async (category: string) => {
    try {
      const result = await apiClient.markCategoryAsRead(category);
      
      // Импортируем getVerbCategory, getVerbsByCategory для обработки
      const { getVerbCategory, getVerbsByCategory } = await import('@/lib/verbTranslations');
      const categoryVerbs = getVerbsByCategory(category);
      
      // Помечаем уведомления этой категории как прочитанные
      setNotifications(prev =>
        prev.map(n => {
          const isInCategory = categoryVerbs.includes(n.verb);
          return isInCategory ? { ...n, is_read: true } : n;
        })
      );
      
      // Пересчитываем счетчик непрочитанных
      setNotifications(prev => {
        const newUnreadCount = prev.filter(n => !n.is_read).length;
        setUnreadCount(newUnreadCount);
        return prev;
      });
      
      // Синхронизация между экземплярами хука через CustomEvent
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('category-marked-read', { 
          detail: { category, verbs: categoryVerbs } 
        }));
      }
      
      return result.count;
    } catch (err) {
      console.error('Failed to mark category as read:', err);
      return 0;
    }
  };

  return { 
    notifications, 
    loading, 
    error, 
    unreadCount, 
    markAsRead, 
    markAllAsRead, 
    markCategoryAsRead,
    deleteNotification, 
    deleteAllRead 
  };
}

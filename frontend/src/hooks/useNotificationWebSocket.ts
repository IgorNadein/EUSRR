/**
 * WebSocket хук для realtime уведомлений
 * Подключается к UserConsumer на /ws/ и слушает события уведомлений
 */
import { useEffect, useRef, useCallback } from 'react';
import { getWebSocketUrl } from '@/lib/url';

interface NotificationMessage {
  type: 'notification' | 'unread_count' | 'ping' | 'list_update' | 'new_message' | 'marked_read';
  notification?: any;
  count?: number;
}

interface UseNotificationWebSocketOptions {
  onNotification: (notification: any) => void;
  onUnreadCountUpdate: (count: number) => void;
  enabled?: boolean;
}

export function useNotificationWebSocket({
  onNotification,
  onUnreadCountUpdate,
  enabled = true
}: UseNotificationWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;

  const connect = useCallback(() => {
    if (!enabled || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      let wsUrl = getWebSocketUrl();

      // Добавляем токен
      const token = localStorage.getItem('access_token');
      if (token) {
        wsUrl += `${wsUrl.includes('?') ? '&' : '?'}token=${token}`;
      }

      console.log('[NotificationWS] Connecting to:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[NotificationWS] Connected');
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data: NotificationMessage = JSON.parse(event.data);
          
          // Игнорируем ping и другие события
          if (data.type === 'ping' || 
              data.type === 'list_update' || 
              data.type === 'new_message' ||
              data.type === 'marked_read') {
            return;
          }

          console.log('[NotificationWS] Message:', data);

          // Обрабатываем уведомления
          if (data.type === 'notification' && data.notification) {
            onNotification(data.notification);
          }

          // Обрабатываем счетчик
          if (data.type === 'unread_count' && typeof data.count === 'number') {
            onUnreadCountUpdate(data.count);
          }
        } catch (error) {
          console.error('[NotificationWS] Parse error:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[NotificationWS] Error:', error);
      };

      ws.onclose = () => {
        console.log('[NotificationWS] Disconnected');
        wsRef.current = null;

        // Автоматический reconnect
        if (enabled && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          console.log(`[NotificationWS] Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
          reconnectTimeoutRef.current = setTimeout(connect, reconnectDelay);
        }
      };
    } catch (error) {
      console.error('[NotificationWS] Connection failed:', error);
    }
  }, [enabled, onNotification, onUnreadCountUpdate]);

  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, connect]);

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    reconnect: connect,
  };
}

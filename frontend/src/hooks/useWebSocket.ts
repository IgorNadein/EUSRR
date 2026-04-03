import { useEffect, useRef, useState, useCallback } from 'react';
import { getWebSocketUrl } from '@/lib/url';
import type { Message } from '@/types/api';

type ReactionsSummary = Record<string, { count: number; users?: number[]; user_names?: string[] }>;

interface WebSocketMessage {
  type: string;
  payload?: Record<string, unknown>;
  message?: Message;
  message_id?: number;
  user_id?: number;
  chat_id?: number;
  last_read_message_id?: number;
  reader_user_id?: number;
  reactions_summary?: ReactionsSummary;
  [key: string]: unknown;
}

interface WebSocketHandlers {
  onMessage: (data: WebSocketMessage) => void;
  onTyping: (userId: number) => void;
  onError: (error: Event) => void;
  onConnect: () => void;
  onDisconnect: () => void;
}

interface UseWebSocketOptions {
  chatId: number | null;
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  onReconnectExhausted?: (details: {
    chatId: number | null;
    reconnectAttempts: number;
  }) => void;
}

export function useWebSocket({
  chatId,
  autoConnect = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5,
  onReconnectExhausted,
}: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(autoConnect);
  const connectRef = useRef<() => void>(() => {});

  const handlers = useRef<WebSocketHandlers>({
    onMessage: () => {},
    onTyping: () => {},
    onError: () => {},
    onConnect: () => {},
    onDisconnect: () => {},
  });

  const connect = useCallback(() => {
    if (!chatId || isConnectingRef.current || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    shouldReconnectRef.current = autoConnect;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    isConnectingRef.current = true;

    try {
      // Используем функцию для построения WebSocket URL
      let wsUrl = getWebSocketUrl();

      // // Если нет протокола - добавляем
      // if (!wsUrl.startsWith('ws://') && !wsUrl.startsWith('wss://')) {
      //   const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      //   wsUrl = `${protocol}//${wsUrl}`;
      // }

      // Добавляем токен
      const token = localStorage.getItem('access_token');
      if (token) {
        wsUrl += `${wsUrl.includes('?') ? '&' : '?'}token=${token}`;
      }

      console.log('🔄 WebSocket URL:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        setReconnectAttempts(0);
        isConnectingRef.current = false;

        // Открываем чат на сервере
        ws.send(JSON.stringify({
          action: 'open_chat',
          chat_id: chatId,
          load_history: false
        }));

        handlers.current.onConnect();
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          console.log('📨 WebSocket message:', data);

          // Обработка специфичных событий
          if (data.type === 'chat_user_typing' && data.user_id) {
            handlers.current.onTyping(data.user_id);
          }

          // Общий обработчик
          handlers.current.onMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        handlers.current.onError(error);
        isConnectingRef.current = false;
      };

      ws.onclose = () => {
        setIsConnected(false);
        isConnectingRef.current = false;
        wsRef.current = null;
        handlers.current.onDisconnect();

        // Автоматическое переподключение
        if (shouldReconnectRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const nextAttempt = reconnectAttemptsRef.current + 1;
          reconnectAttemptsRef.current = nextAttempt;
          setReconnectAttempts(nextAttempt);
          console.log(`🔄 Reconnecting... (attempt ${nextAttempt}/${maxReconnectAttempts})`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connectRef.current();
          }, reconnectInterval);
        } else if (shouldReconnectRef.current && reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('❌ Max reconnection attempts reached. Backend may not support WebSocket.');
          onReconnectExhausted?.({
            chatId,
            reconnectAttempts: reconnectAttemptsRef.current,
          });
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      isConnectingRef.current = false;
    }
  }, [chatId, autoConnect, reconnectInterval, maxReconnectAttempts, onReconnectExhausted]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      const ws = wsRef.current;

      if (ws.readyState === WebSocket.OPEN && chatId) {
        ws.send(JSON.stringify({
          action: 'close_chat',
          chat_id: chatId
        }));
      }

      ws.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);
    isConnectingRef.current = false;
  }, [chatId]);

  const sendTyping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'typing'
      }));
    }
  }, []);

  const sendMessage = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Cannot send message.');
    }
  }, []);

  // Подключение при монтировании или изменении chatId
  useEffect(() => {
    shouldReconnectRef.current = autoConnect;

    if (autoConnect && chatId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [chatId, autoConnect, connect, disconnect]);

  // Очистка при размонтировании
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  return {
    isConnected,
    reconnectAttempts,
    handlers,
    connect,
    disconnect,
    sendTyping,
    sendMessage,
  };
}

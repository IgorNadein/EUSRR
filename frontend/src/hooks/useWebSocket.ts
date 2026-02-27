import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketMessage {
  type: string;
  payload?: any;
  message_id?: number;
  user_id?: number;
  [key: string]: any;
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
}

export function useWebSocket({
  chatId,
  autoConnect = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5
}: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);

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

    isConnectingRef.current = true;

    try {
      // Простую логику построения URL
      let wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:9000/ws/';

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
        console.warn('⚠️  WebSocket не может подключиться. Убедитесь что backend запущен через Daphne:');
        console.warn('   cd backend && c:/Users/igor_/Dev/EUSRR/.venv/Scripts/python -m daphne -p 9000 eusrr_backend.asgi:application');
        handlers.current.onError(error);
        isConnectingRef.current = false;
      };

      ws.onclose = () => {
        setIsConnected(false);
        isConnectingRef.current = false;
        handlers.current.onDisconnect();

        // Автоматическое переподключение
        if (autoConnect && reconnectAttempts < maxReconnectAttempts) {
          console.log(`🔄 Reconnecting... (attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts(prev => prev + 1);
            connect();
          }, reconnectInterval);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          console.error('❌ Max reconnection attempts reached. Backend may not support WebSocket.');
          console.warn('⚠️  Запустите backend через Daphne для WebSocket:');
          console.warn('   cd C:/Users/igor_/Dev/EUSRR/backend');
          console.warn('   c:/Users/igor_/Dev/EUSRR/.venv/Scripts/python -m daphne -p 9000 eusrr_backend.asgi:application');
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      isConnectingRef.current = false;
    }
  }, [chatId, autoConnect, reconnectInterval, maxReconnectAttempts, reconnectAttempts]);

  const disconnect = useCallback(() => {
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

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Cannot send message.');
    }
  }, []);

  // Подключение при монтировании или изменении chatId
  useEffect(() => {
    if (autoConnect && chatId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [chatId, autoConnect]);

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

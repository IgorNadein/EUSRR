/**
 * Singleton WebSocket Manager
 * Управляет единственным WebSocket соединением для всего приложения
 */

type RealtimeEvent = {
  type: string;
  [key: string]: unknown;
};
type MessageHandler = (data: RealtimeEvent) => void;
type ConnectionStatus = {
  isConnected: boolean;
  isConnecting: boolean;
  reconnectAttempts: number;
};
type StatusHandler = (status: ConnectionStatus) => void;

class WebSocketManager {
  private static instance: WebSocketManager | null = null;
  private ws: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private messageHandlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private isConnecting = false;
  private shouldReconnect = false;

  private constructor() {}

  static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  private hasSubscribers(): boolean {
    return this.messageHandlers.size > 0 || this.statusHandlers.size > 0;
  }

  private getConnectionStatus(): ConnectionStatus {
    return {
      isConnected: this.ws?.readyState === WebSocket.OPEN,
      isConnecting: this.isConnecting,
      reconnectAttempts: this.reconnectAttempts,
    };
  }

  private notifyStatus() {
    const status = this.getConnectionStatus();
    this.statusHandlers.forEach((handler) => {
      try {
        handler(status);
      } catch (error) {
        console.error('[WS Manager] Status handler error:', error);
      }
    });
  }

  connect() {
    // Если уже подключены или подключаемся, не создаем новое соединение
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      console.log('[WS Manager] Already connected or connecting');
      return;
    }

    if (!this.hasSubscribers()) {
      this.shouldReconnect = false;
      return;
    }

    // Проверяем что мы в браузере и пользователь авторизован
    if (typeof window === 'undefined' || !localStorage.getItem('access_token')) {
      console.log('[WS Manager] Not in browser or not authenticated');
      this.notifyStatus();
      return;
    }

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    this.shouldReconnect = true;
    this.isConnecting = true;
    this.notifyStatus();

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:9000';
      const protocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:';
      const host = backendUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
      let wsUrl = `${protocol}//${host}/ws/`;

      const token = localStorage.getItem('access_token');
      if (token) {
        wsUrl += `?token=${token}`;
      }

      console.log('[WS Manager] Backend URL:', backendUrl);
      console.log('[WS Manager] Protocol:', protocol);
      console.log('[WS Manager] Host:', host);
      console.log('[WS Manager] Full WS URL:', wsUrl);
      console.log('[WS Manager] Has token:', !!token);
      
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[WS Manager] Connected');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.notifyStatus();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Отправляем сообщение всем подписчикам
          this.messageHandlers.forEach(handler => {
            try {
              handler(data);
            } catch (err) {
              console.error('[WS Manager] Handler error:', err);
            }
          });
        } catch (error) {
          console.error('[WS Manager] Parse error:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WS Manager] Error event:', error);
        console.error('[WS Manager] WebSocket state:', this.ws?.readyState);
        console.error('[WS Manager] WebSocket URL was:', this.ws?.url);
        this.isConnecting = false;
        this.notifyStatus();
      };

      this.ws.onclose = (event) => {
        console.log('[WS Manager] Disconnected');
        console.log('[WS Manager] Close event code:', event.code);
        console.log('[WS Manager] Close event reason:', event.reason);
        console.log('[WS Manager] Close event wasClean:', event.wasClean);
        this.isConnecting = false;
        this.ws = null;
        this.notifyStatus();

        // Автоматический reconnect
        if (this.shouldReconnect && this.hasSubscribers() && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          this.notifyStatus();
          const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
          console.log(`[WS Manager] Reconnecting in ${delay}ms... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
          this.reconnectTimeout = setTimeout(() => this.connect(), delay);
        }
      };
    } catch (error) {
      console.error('[WS Manager] Connection failed:', error);
      this.isConnecting = false;
      this.notifyStatus();
    }
  }

  disconnect() {
    this.shouldReconnect = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    this.isConnecting = false;
    this.reconnectAttempts = 0;
    this.notifyStatus();
  }

  subscribe(handler: MessageHandler) {
    this.messageHandlers.add(handler);
    this.shouldReconnect = true;
    
    // Если есть подписчик и нет соединения, подключаемся
    if (this.hasSubscribers() && !this.ws && !this.isConnecting) {
      this.connect();
    }
    
    // Возвращаем функцию отписки
    return () => {
      this.messageHandlers.delete(handler);
      
      // Если больше нет подписчиков, отключаемся
      if (!this.hasSubscribers()) {
        console.log('[WS Manager] No more subscribers, disconnecting');
        this.disconnect();
      }
    };
  }

  subscribeStatus(handler: StatusHandler) {
    this.statusHandlers.add(handler);
    handler(this.getConnectionStatus());
    this.shouldReconnect = true;

    if (this.hasSubscribers() && !this.ws && !this.isConnecting) {
      this.connect();
    }

    return () => {
      this.statusHandlers.delete(handler);

      if (!this.hasSubscribers()) {
        console.log('[WS Manager] No more subscribers, disconnecting');
        this.disconnect();
      }
    };
  }

  getState(): number {
    return this.ws?.readyState ?? 3;
  }
}

export default WebSocketManager.getInstance();

/**
 * @fileoverview Централизованная конфигурация чат-модуля
 * @module config/chatConfig
 */

/**
 * Конфигурация загрузчика сообщений
 */
export const LOADER_CONFIG = {
    /** Количество сообщений для начальной загрузки */
    INITIAL_LIMIT: 30,
    
    /** Количество сообщений для загрузки истории */
    HISTORY_LIMIT: 20,
    
    /** Максимальное количество попыток при ошибке */
    MAX_RETRIES: 3,
    
    /** Базовая задержка между попытками (мс) */
    RETRY_DELAY_BASE: 1000,
    
    /** Таймаут запроса (мс) */
    REQUEST_TIMEOUT: 15000,
    
    /** Дебаунс для загрузки истории (мс) */
    HISTORY_DEBOUNCE: 150
};

/**
 * Конфигурация скролла
 */
export const SCROLL_CONFIG = {
    /** Порог в px для определения "пользователь внизу" */
    BOTTOM_THRESHOLD: 100,
    
    /** Порог в px для триггера загрузки истории */
    HISTORY_TRIGGER_THRESHOLD: 140,
    
    /** Отступ для IntersectionObserver (px) */
    OBSERVER_ROOT_MARGIN: '100px 0px 0px 0px',
    
    /** Порог видимости для IntersectionObserver (0-1) */
    OBSERVER_THRESHOLD: 0.1,
    
    /** Задержка перед восстановлением позиции скролла (мс) */
    SCROLL_RESTORE_DELAY: 50
};

/**
 * Конфигурация рендеринга
 */
export const RENDER_CONFIG = {
    /** Использовать visibility:hidden при рендеринге */
    USE_VISIBILITY_HIDING: true,
    
    /** Задержка перед скроллом после рендеринга (мс) */
    POST_RENDER_DELAY: 50,
    
    /** Максимальное количество сообщений в DOM */
    MAX_DOM_MESSAGES: 500,
    
    /** Количество сообщений для виртуализации */
    VIRTUALIZATION_BUFFER: 50
};

/**
 * Конфигурация WebSocket
 */
export const WS_CONFIG = {
    /** Таймаут ожидания подключения (мс) */
    CONNECTION_TIMEOUT: 10000,
    
    /** Интервал ping (мс) */
    PING_INTERVAL: 30000,
    
    /** Максимальное время ожидания pong (мс) */
    PONG_TIMEOUT: 5000
};

/**
 * Типы событий Store
 * @enum {string}
 */
export const STORE_EVENTS = {
    MESSAGE_ADDED: 'message_added',
    MESSAGE_UPDATED: 'message_updated',
    MESSAGE_REMOVED: 'message_removed',
    MESSAGES_LOADED: 'messages_loaded',
    CHAT_CLEARED: 'chat_cleared',
    OPTIMISTIC_CONFIRMED: 'optimistic_confirmed',
    OPTIMISTIC_FAILED: 'optimistic_failed'
};

/**
 * Типы событий чата (для window events)
 * @enum {string}
 */
export const CHAT_EVENTS = {
    INITIALIZED: 'chat:initialized',
    MESSAGE_ADDED: 'chat:message-added',
    MESSAGE_UPDATED: 'chat:message-updated',
    MESSAGE_REMOVED: 'chat:message-removed',
    HISTORY_LOADED: 'chat:history-loaded',
    SCROLL_TO_BOTTOM: 'chat:scroll-to-bottom',
    ERROR: 'chat:error'
};

/**
 * Типы WebSocket событий
 * @enum {string}
 */
export const WS_EVENTS = {
    NEW_MESSAGE: 'ws:new-message',
    MESSAGE_EDITED: 'ws:message-edited',
    MESSAGE_REMOVED: 'ws:message-removed',
    REACTION_ADDED: 'ws:reaction-added',
    REACTION_REMOVED: 'ws:reaction-removed'
};

/**
 * Статусы сообщения
 * @enum {string}
 */
export const MESSAGE_STATUS = {
    SENDING: 'sending',
    SENT: 'sent',
    FAILED: 'failed',
    READ: 'read'
};

/**
 * API endpoints (шаблоны)
 */
export const API_ENDPOINTS = {
    /** Получить сообщения чата */
    MESSAGES: (chatId) => `/api/v1/communications/chats/${chatId}/messages/`,
    
    /** Получить сообщения вокруг конкретного ID */
    MESSAGES_AROUND: (chatId) => `/api/v1/communications/chats/${chatId}/messages/around/`,
    
    /** Отметить сообщения как прочитанные */
    MARK_READ: (chatId) => `/api/v1/communications/chats/${chatId}/mark-read/`,
    
    /** Отправить сообщение */
    SEND_MESSAGE: (chatId) => `/api/v1/communications/chats/${chatId}/messages/`,
    
    /** Загрузить файл */
    UPLOAD_FILE: (chatId) => `/api/v1/communications/chats/${chatId}/upload/`
};

/**
 * Генерирует URL с query параметрами
 * @param {string} baseUrl - Базовый URL
 * @param {Object} params - Параметры запроса
 * @returns {string} URL с параметрами
 */
export function buildUrl(baseUrl, params = {}) {
    const url = new URL(baseUrl, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
            url.searchParams.set(key, String(value));
        }
    });
    return url.toString();
}

/**
 * Создает заголовки для AJAX запросов
 * @returns {Object} Заголовки
 */
export function getRequestHeaders() {
    return {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/json'
    };
}

export default {
    LOADER_CONFIG,
    SCROLL_CONFIG,
    RENDER_CONFIG,
    WS_CONFIG,
    STORE_EVENTS,
    CHAT_EVENTS,
    WS_EVENTS,
    MESSAGE_STATUS,
    API_ENDPOINTS,
    buildUrl,
    getRequestHeaders
};

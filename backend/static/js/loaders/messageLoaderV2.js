/**
 * @fileoverview MessageLoader V2 - оптимизированный загрузчик сообщений
 * @module loaders/messageLoaderV2
 * 
 * РЕФАКТОРИНГ:
 * - Единый API для всех типов загрузки
 * - Retry-логика с exponential backoff
 * - AbortController для отмены запросов
 * - Чистое разделение ответственности
 * - Нет дублирования кода
 */

import { 
    LOADER_CONFIG, 
    API_ENDPOINTS, 
    buildUrl, 
    getRequestHeaders,
    MESSAGE_STATUS 
} from '../config/chatConfig.js';

/**
 * @typedef {Object} LoadResult
 * @property {Array<Message>} messages - Загруженные сообщения
 * @property {number|null} anchorId - ID якорного сообщения
 * @property {boolean} hasMoreBefore - Есть ли ещё старые сообщения
 * @property {boolean} hasMoreAfter - Есть ли ещё новые сообщения
 */

/**
 * @typedef {Object} LoadingState
 * @property {boolean} initial - Идет начальная загрузка
 * @property {boolean} history - Идет загрузка истории
 * @property {boolean} newer - Идет загрузка новых сообщений
 * @property {string} status - Статус: 'idle' | 'loading' | 'loaded' | 'error'
 * @property {Error|null} lastError - Последняя ошибка
 */

/**
 * MessageLoader V2 - современный загрузчик сообщений
 */
export class MessageLoaderV2 {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {MessageStore} options.store - Экземпляр MessageStore
     * @param {Object} [options.wsConnection] - WebSocket соединение
     * @param {number} options.currentUserId - ID текущего пользователя
     * @param {Object} [options.config] - Переопределение конфигурации
     */
    constructor(options) {
        if (!options.store) {
            throw new Error('[MessageLoaderV2] MessageStore is required');
        }

        this.store = options.store;
        this.ws = options.wsConnection || null;
        this.currentUserId = options.currentUserId;
        
        // Конфигурация с возможностью переопределения
        this.config = { ...LOADER_CONFIG, ...options.config };
        
        /** @type {number|null} ID текущего открытого чата */
        this.currentChatId = null;
        
        /** @type {Map<number, LoadingState>} Состояние загрузки по чатам */
        this.loadingStates = new Map();
        
        /** @type {Map<number, {hasMoreBefore: boolean, hasMoreAfter: boolean, oldestId: number|null, newestId: number|null}>} */
        this.chatBoundaries = new Map();
        
        /** @type {Map<string, AbortController>} Активные запросы */
        this.pendingRequests = new Map();
        
        console.log('[MessageLoaderV2] Initialized');
    }

    // ==================== Публичное API ====================

    /**
     * Загружает начальные сообщения для чата
     * @param {number} chatId - ID чата
     * @param {Object} [options] - Опции загрузки
     * @param {number} [options.aroundMessageId] - Загрузить вокруг этого сообщения
     * @param {number} [options.limit] - Количество сообщений
     * @returns {Promise<LoadResult>}
     */
    async loadInitial(chatId, options = {}) {
        const requestKey = `initial_${chatId}`;
        
        // Отменяем предыдущий запрос если есть
        this._abortRequest(requestKey);
        
        const state = this._getLoadingState(chatId);
        if (state.initial) {
            console.log('[MessageLoaderV2] Initial load already in progress for chat:', chatId);
            return { messages: [], anchorId: null, hasMoreBefore: false, hasMoreAfter: false };
        }

        this.currentChatId = chatId;
        state.initial = true;
        state.status = 'loading';

        try {
            const { aroundMessageId, limit = this.config.INITIAL_LIMIT } = options;
            
            console.log('[MessageLoaderV2] 🔍 Load decision:', {
                aroundMessageId,
                type: typeof aroundMessageId,
                isPositive: aroundMessageId > 0,
                willLoadAround: !!(aroundMessageId && aroundMessageId > 0)
            });
            
            let result;
            if (aroundMessageId && aroundMessageId > 0) {
                result = await this._loadAround(chatId, aroundMessageId, limit, requestKey);
            } else {
                result = await this._loadLatest(chatId, limit, requestKey);
            }

            // Сохраняем в Store
            this._processMessages(chatId, result.messages);
            
            // Обновляем границы чата
            this._updateBoundaries(chatId, result);

            state.status = 'loaded';
            state.lastError = null;
            
            console.log('[MessageLoaderV2] Initial load complete:', result.messages.length, 'messages');
            
            return result;

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[MessageLoaderV2] Initial load aborted for chat:', chatId);
                state.status = 'idle';
                return { messages: [], anchorId: null, hasMoreBefore: false, hasMoreAfter: false };
            }
            
            console.error('[MessageLoaderV2] Initial load failed:', error);
            state.status = 'error';
            state.lastError = error;
            throw error;
            
        } finally {
            state.initial = false;
            this._cleanupRequest(requestKey);
        }
    }

    /**
     * Загружает историю (старые сообщения)
     * @param {number} chatId - ID чата
     * @param {Object} [options] - Опции
     * @param {number} [options.limit] - Количество сообщений
     * @returns {Promise<Array<Message>>}
     */
    async loadHistory(chatId, options = {}) {
        const requestKey = `history_${chatId}`;
        
        const state = this._getLoadingState(chatId);
        const boundaries = this._getBoundaries(chatId);
        
        if (state.history) {
            console.log('[MessageLoaderV2] History load already in progress');
            return [];
        }
        
        if (!boundaries.hasMoreBefore) {
            console.log('[MessageLoaderV2] No more history available');
            return [];
        }
        
        if (!boundaries.oldestId) {
            console.log('[MessageLoaderV2] No oldest ID for history loading');
            return [];
        }

        this._abortRequest(requestKey);
        state.history = true;

        try {
            const limit = options.limit || this.config.HISTORY_LIMIT;
            const result = await this._fetchWithRetry(
                buildUrl(API_ENDPOINTS.MESSAGES(chatId), {
                    before_id: boundaries.oldestId,
                    limit
                }),
                requestKey
            );

            const messages = this._extractMessages(result);
            
            if (messages.length > 0) {
                // Определяем какие сообщения НОВЫЕ (не были в Store)
                const existingIds = new Set(
                    this.store.getMessagesForChat(chatId).map(m => m.id)
                );
                const newMessages = messages.filter(m => !existingIds.has(m.id));
                
                console.log('[MessageLoaderV2] Filtering messages:', {
                    total: messages.length,
                    existing: messages.length - newMessages.length,
                    new: newMessages.length
                });
                
                // Добавляем в Store БЕЗ событий (silent mode)
                // Отрисовка будет через prependMessages
                this._processMessages(chatId, messages, { silent: true });
                
                // Обновляем границы
                const oldestMessage = this.store.getOldestMessage(chatId);
                this._updateBoundaries(chatId, {
                    hasMoreBefore: result.has_more !== false,
                    oldestId: oldestMessage?.id || null
                });
                
                // Возвращаем только НОВЫЕ сообщения
                return newMessages;
            } else {
                this._updateBoundaries(chatId, { hasMoreBefore: false });
            }

            console.log('[MessageLoaderV2] History loaded:', messages.length, 'messages');
            return [];

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[MessageLoaderV2] History load aborted');
                return [];
            }
            console.error('[MessageLoaderV2] History load failed:', error);
            throw error;
            
        } finally {
            state.history = false;
            this._cleanupRequest(requestKey);
        }
    }

    /**
     * Загружает новые сообщения (после текущего newest)
     * Используется для синхронизации после reconnect
     * @param {number} chatId - ID чата
     * @returns {Promise<Array<Message>>}
     */
    async loadNewer(chatId) {
        const requestKey = `newer_${chatId}`;
        
        const state = this._getLoadingState(chatId);
        const boundaries = this._getBoundaries(chatId);
        
        if (state.newer || !boundaries.newestId) {
            return [];
        }

        this._abortRequest(requestKey);
        state.newer = true;

        try {
            const result = await this._fetchWithRetry(
                buildUrl(API_ENDPOINTS.MESSAGES(chatId), {
                    after_id: boundaries.newestId,
                    limit: this.config.HISTORY_LIMIT
                }),
                requestKey
            );

            const messages = this._extractMessages(result);
            
            if (messages.length > 0) {
                this._processMessages(chatId, messages);
                
                const newestMessage = this.store.getNewestMessage(chatId);
                this._updateBoundaries(chatId, {
                    hasMoreAfter: result.has_more !== false,
                    newestId: newestMessage?.id || null
                });
            }

            return messages;

        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('[MessageLoaderV2] Newer load failed:', error);
            }
            return [];
            
        } finally {
            state.newer = false;
            this._cleanupRequest(requestKey);
        }
    }

    // ==================== WebSocket обработчики ====================

    /**
     * Обрабатывает новое сообщение из WebSocket
     * @param {Object} message - Сообщение с сервера
     */
    handleNewMessage(message) {
        if (!this._validateMessage(message)) return;

        // Устанавливаем chat_id если отсутствует
        if (!message.chat_id && this.currentChatId) {
            message.chat_id = this.currentChatId;
        }

        // Проверяем - это подтверждение оптимистичного сообщения?
        if (message.temp_id && this.store.optimisticMessages.has(message.temp_id)) {
            console.log('[MessageLoaderV2] Confirming optimistic:', message.temp_id);
            this.store.confirmOptimisticMessage(message.temp_id, message);
            return;
        }

        // Добавляем как обычное сообщение
        this.store.addMessage(message);
        
        // Обновляем newestId
        const boundaries = this._getBoundaries(message.chat_id);
        if (!boundaries.newestId || message.id > boundaries.newestId) {
            this._updateBoundaries(message.chat_id, { newestId: message.id });
        }
    }

    /**
     * Обрабатывает редактирование сообщения
     * @param {Object} data - Данные редактирования
     */
    handleMessageEdited(data) {
        const message = data.message || data;
        if (!message?.id) {
            console.error('[MessageLoaderV2] Invalid edit data');
            return;
        }
        this.store.updateMessage(message.id, message);
    }

    /**
     * Обрабатывает удаление сообщения
     * @param {Object} data - Данные удаления
     */
    handleMessageRemoved(data) {
        const messageId = data.message_id || data.messageId;
        if (!messageId) {
            console.error('[MessageLoaderV2] Invalid remove data');
            return;
        }
        this.store.removeMessage(messageId);
    }

    /**
     * Обрабатывает изменение реакций
     * @param {Object} data - Данные реакции
     */
    handleReactionChange(data) {
        const { message_id, reactions_summary } = data;
        if (!message_id) return;
        
        const message = this.store.getMessage(message_id);
        if (message) {
            this.store.updateMessage(message_id, { reactions_summary });
        }
    }

    // ==================== Отправка сообщений ====================

    /**
     * Отправляет сообщение оптимистично
     * @param {number} chatId - ID чата
     * @param {string} content - Текст сообщения
     * @param {Object} [options] - Дополнительные опции
     * @returns {string} Временный ID сообщения
     */
    sendOptimistic(chatId, content, options = {}) {
        const tempId = this._generateTempId();
        
        const optimisticMessage = {
            id: tempId,
            temp_id: tempId,
            chat_id: chatId,
            author_id: this.currentUserId,
            content: content.trim(),
            created_ts: Date.now(),
            status: MESSAGE_STATUS.SENDING,
            is_edited: false,
            reactions_summary: {},
            ...options
        };

        // Добавляем в Store
        this.store.addMessage(optimisticMessage, true);

        // Отправляем через WebSocket
        if (this.ws?.send) {
            try {
                this.ws.send({
                    type: 'send_message',
                    chat_id: chatId,
                    content: content.trim(),
                    temp_id: tempId,
                    ...options
                });
            } catch (error) {
                console.error('[MessageLoaderV2] WS send failed:', error);
                this.store.failOptimisticMessage(tempId);
            }
        } else {
            console.warn('[MessageLoaderV2] WebSocket not available');
            this.store.failOptimisticMessage(tempId);
        }

        return tempId;
    }

    // ==================== Проверки состояния ====================

    /**
     * Проверяет, есть ли еще история для загрузки
     * @param {number} chatId - ID чата
     * @returns {boolean}
     */
    hasMoreHistory(chatId) {
        return this._getBoundaries(chatId).hasMoreBefore;
    }

    /**
     * Проверяет, идет ли сейчас какая-либо загрузка
     * @param {number} chatId - ID чата
     * @returns {boolean}
     */
    isLoading(chatId) {
        const state = this._getLoadingState(chatId);
        return state.initial || state.history || state.newer;
    }

    /**
     * Получает полное состояние загрузки
     * @param {number} chatId - ID чата
     * @returns {Object}
     */
    getStatus(chatId) {
        return {
            ...this._getLoadingState(chatId),
            ...this._getBoundaries(chatId)
        };
    }

    /**
     * Отменяет все активные запросы для чата
     * @param {number} chatId - ID чата
     */
    cancelAll(chatId) {
        const prefixes = [`initial_${chatId}`, `history_${chatId}`, `newer_${chatId}`];
        prefixes.forEach(key => this._abortRequest(key));
    }

    // ==================== Приватные методы - HTTP ====================

    /**
     * Загружает сообщения вокруг указанного ID
     * @private
     */
    async _loadAround(chatId, aroundId, limit, requestKey) {
        console.log('[MessageLoaderV2] Loading around message:', aroundId);
        
        const result = await this._fetchWithRetry(
            buildUrl(API_ENDPOINTS.MESSAGES_AROUND(chatId), {
                around_id: aroundId,
                limit
            }),
            requestKey
        );

        console.log('[MessageLoaderV2] 🔍 API response:', {
            anchor_id: result.anchor_id,
            anchor_index: result.anchor_index,
            messages_count: result.messages?.length || result.results?.length || 0
        });

        const messages = this._extractMessages(result);
        
        // ВАЖНО: Сначала добавляем в Store, затем берем границы из Store
        this._processMessages(chatId, messages);
        
        const oldestMessage = this.store.getOldestMessage(chatId);
        const newestMessage = this.store.getNewestMessage(chatId);

        const loadResult = {
            messages,
            anchorId: result.anchor_id || aroundId,
            anchorIndex: result.anchor_index || null,
            hasMoreBefore: result.has_more_before !== false,
            hasMoreAfter: result.has_more_after !== false,
            oldestId: oldestMessage?.id || null,
            newestId: newestMessage?.id || null
        };
        
        console.log('[MessageLoaderV2] 🔍 Returning loadResult:', {
            anchorId: loadResult.anchorId,
            anchorIndex: loadResult.anchorIndex,
            messagesCount: loadResult.messages.length
        });
        
        return loadResult;
    }

    /**
     * Загружает последние сообщения
     * @private
     */
    async _loadLatest(chatId, limit, requestKey) {
        console.log('[MessageLoaderV2] Loading latest messages');
        
        const result = await this._fetchWithRetry(
            buildUrl(API_ENDPOINTS.MESSAGES(chatId), { limit }),
            requestKey
        );

        const messages = this._extractMessages(result);
        
        // ВАЖНО: Сначала добавляем в Store, затем берем границы из Store
        // Store гарантирует правильную сортировку по timestamp
        this._processMessages(chatId, messages);
        
        const oldestMessage = this.store.getOldestMessage(chatId);
        const newestMessage = this.store.getNewestMessage(chatId);

        return {
            messages,
            anchorId: null,
            hasMoreBefore: result.has_more !== false,
            hasMoreAfter: false,
            oldestId: oldestMessage?.id || null,
            newestId: newestMessage?.id || null
        };
    }

    /**
     * Выполняет fetch с retry-логикой
     * @private
     */
    async _fetchWithRetry(url, requestKey, attempt = 1) {
        const controller = new AbortController();
        this.pendingRequests.set(requestKey, controller);
        
        // Таймаут
        const timeoutId = setTimeout(
            () => controller.abort(), 
            this.config.REQUEST_TIMEOUT
        );

        try {
            const response = await fetch(url, {
                headers: getRequestHeaders(),
                credentials: 'same-origin',
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();

        } catch (error) {
            clearTimeout(timeoutId);
            
            // Не ретраим при отмене
            if (error.name === 'AbortError') {
                throw error;
            }
            
            // Retry с exponential backoff
            if (attempt < this.config.MAX_RETRIES) {
                const delay = this.config.RETRY_DELAY_BASE * Math.pow(2, attempt - 1);
                console.log(`[MessageLoaderV2] Retry ${attempt}/${this.config.MAX_RETRIES} after ${delay}ms`);
                
                await this._delay(delay);
                return this._fetchWithRetry(url, requestKey, attempt + 1);
            }
            
            throw error;
        }
    }

    // ==================== Приватные методы - State ====================

    /**
     * Получает или создает состояние загрузки для чата
     * @private
     */
    _getLoadingState(chatId) {
        if (!this.loadingStates.has(chatId)) {
            this.loadingStates.set(chatId, {
                initial: false,
                history: false,
                newer: false,
                status: 'idle',
                lastError: null
            });
        }
        return this.loadingStates.get(chatId);
    }

    /**
     * Получает или создает границы чата
     * @private
     */
    _getBoundaries(chatId) {
        if (!this.chatBoundaries.has(chatId)) {
            this.chatBoundaries.set(chatId, {
                hasMoreBefore: true,
                hasMoreAfter: false,
                oldestId: null,
                newestId: null
            });
        }
        return this.chatBoundaries.get(chatId);
    }

    /**
     * Обновляет границы чата
     * @private
     */
    _updateBoundaries(chatId, updates) {
        const current = this._getBoundaries(chatId);
        Object.assign(current, updates);
    }

    // ==================== Приватные методы - Helpers ====================

    /**
     * Обрабатывает и сохраняет сообщения в Store
     * @private
     * @param {number} chatId
     * @param {Array} messages
     * @param {Object} [options]
     * @param {boolean} [options.silent=false] - Не emit'ить события
     */
    _processMessages(chatId, messages, options = {}) {
        // Добавляем chat_id если отсутствует
        messages.forEach(msg => {
            if (!msg.chat_id) {
                msg.chat_id = chatId;
            }
        });
        
        this.store.addMessages(messages, options);
    }

    /**
     * Извлекает массив сообщений из ответа API
     * @private
     */
    _extractMessages(response) {
        return response.messages || response.results || [];
    }

    /**
     * Валидирует сообщение
     * @private
     */
    _validateMessage(message) {
        if (!message || !message.id) {
            console.error('[MessageLoaderV2] Invalid message:', message);
            return false;
        }
        return true;
    }

    /**
     * Генерирует временный ID
     * @private
     */
    _generateTempId() {
        return `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Отменяет запрос
     * @private
     */
    _abortRequest(key) {
        const controller = this.pendingRequests.get(key);
        if (controller) {
            controller.abort();
            this.pendingRequests.delete(key);
        }
    }

    /**
     * Очищает ссылку на запрос
     * @private
     */
    _cleanupRequest(key) {
        this.pendingRequests.delete(key);
    }

    /**
     * Возвращает Promise с задержкой
     * @private
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

export default MessageLoaderV2;

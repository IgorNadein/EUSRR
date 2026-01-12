/**
 * @fileoverview MessageLoader - единый загрузчик сообщений
 * @module loaders/messageLoader
 * 
 * Отвечает за ВСЕ операции загрузки сообщений:
 * - Начальная загрузка при открытии чата
 * - История при scroll up
 * - Новые сообщения через WebSocket
 * - Оптимистичная отправка
 * 
 * Все данные сохраняются в MessageStore.
 */

/**
 * MessageLoader - единый загрузчик сообщений
 */
export class MessageLoader {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {MessageStore} options.store - Экземпляр MessageStore
     * @param {Object} options.wsConnection - WebSocket соединение (userWebSocket)
     * @param {number} options.currentUserId - ID текущего пользователя
     */
    constructor(options) {
        if (!options.store) {
            throw new Error('[MessageLoader] MessageStore is required');
        }

        this.store = options.store;
        this.ws = options.wsConnection;
        this.currentUserId = options.currentUserId;
        this.currentChatId = null; // Текущий открытый чат

        /** @type {Map<number, {initial: boolean, history: boolean, status: string}>} */
        this.loadingState = new Map();

        /** @type {Map<number, {hasMore: boolean, oldestId: number|null}>} */
        this.chatState = new Map();

        console.log('[MessageLoader] Initialized');
    }

    // ==================== Загрузка начальных сообщений ====================

    /**
     * Загружает начальные сообщения для чата
     * НОВАЯ АРХИТЕКТУРА: Загружает ВОКРУГ last_read_message_id
     * @param {number} chatId - ID чата
     * @param {Object} options - Опции
     * @param {number} [options.limit=50] - Количество сообщений (по умолчанию 50)
     * @param {number} [options.lastReadMessageId] - ID последнего прочитанного (для around)
     * @returns {Promise<Object>} Результат загрузки
     */
    async loadInitialMessages(chatId, options = {}) {
        const state = this._getLoadingState(chatId);
        
        if (state.initial) {
            return { messages: [], anchorId: null };
        }

        try {
            this.currentChatId = chatId;
            state.initial = true;
            state.status = 'loading';

            const limit = options.limit || 50;
            const lastReadId = options.lastReadMessageId;

            // Используем /around/ если есть lastReadId (и он > 0)
            let url;
            if (lastReadId && lastReadId > 0) {
                url = new URL(`/api/v1/communications/chats/${chatId}/messages/around/`, window.location.origin);
                url.searchParams.set('around_id', String(lastReadId));
                url.searchParams.set('limit', String(limit));
            } else {
                // Fallback: загружаем последние сообщения
                url = new URL(`/api/v1/communications/chats/${chatId}/messages/`, window.location.origin);
                url.searchParams.set('limit', String(limit));
            }

            const response = await fetch(url.toString(), {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            const messages = data.messages || data.results || [];

            console.log('[MessageLoader] Loaded', messages.length, 'initial messages');

            // Добавляем chat_id к каждому сообщению (API не возвращает его в ответе)
            messages.forEach(msg => {
                if (!msg.chat_id) {
                    msg.chat_id = chatId;
                }
            });

            // Сохраняем в Store
            this.store.addMessages(messages);

            // Обновляем состояние чата
            // Важно: oldestId берем из Store, а не из messages[0], тк Store гарантирует правильную сортировку
            const oldestMessage = this.store.getOldestMessage(chatId);
            this._updateChatState(chatId, {
                hasMore: data.has_more !== false || data.has_more_before !== false,
                oldestId: oldestMessage ? oldestMessage.id : null
            });

            state.status = 'loaded';
            
            return {
                messages,
                anchorId: data.anchor_id || null,
                anchorIndex: data.anchor_index || null,
                hasMoreBefore: data.has_more_before || false,
                hasMoreAfter: data.has_more_after || false
            };

        } catch (error) {
            console.error('[MessageLoader] Failed to load initial messages:', error);
            state.status = 'error';
            throw error;
        } finally {
            state.initial = false;
        }
    }

    // ==================== Загрузка истории ====================

    /**
     * Загружает историю сообщений (при scroll up)
     * @param {number} chatId - ID чата
     * @param {Object} options - Опции
     * @param {number|string} [options.beforeId] - Загрузить до этого сообщения
     * @param {number} [options.limit=20] - Количество сообщений
     * @returns {Promise<Array>} Массив сообщений
     */
    async loadHistoryBefore(chatId, options = {}) {
        const state = this._getLoadingState(chatId);
        const chatState = this._getChatState(chatId);

        if (state.history) {
            return [];
        }

        if (!chatState.hasMore) {
            return [];
        }

        try {
            state.history = true;

            const beforeId = options.beforeId || chatState.oldestId;
            if (!beforeId) {
                console.warn('[MessageLoader] No beforeId for history loading');
                return [];
            }

            const url = new URL(`/api/v1/communications/chats/${chatId}/messages/`, window.location.origin);
            url.searchParams.set('before_id', String(beforeId));
            url.searchParams.set('limit', String(options.limit || 50)); // Telegram-стиль: больше сообщений

            const response = await fetch(url.toString(), {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            const messages = data.messages || data.results || [];

            // Добавляем chat_id к каждому сообщению
            messages.forEach(msg => {
                if (!msg.chat_id) {
                    msg.chat_id = chatId;
                }
            });

            // Сохраняем в Store и получаем количество РЕАЛЬНО добавленных
            const addedCount = messages.length > 0 ? this.store.addMessages(messages) : 0;

            // Обновляем состояние чата
            if (addedCount > 0) {
                // Обновляем oldestId - берем из Store
                const oldestMessage = this.store.getOldestMessage(chatId);
                this._updateChatState(chatId, {
                    oldestId: oldestMessage ? oldestMessage.id : null,
                    hasMore: data.has_more !== false
                });
            } else if (messages.length > 0 && addedCount === 0) {
                // API вернул сообщения, но все оказались дубликатами
                this._updateChatState(chatId, { hasMore: false });
            } else {
                // Пустой ответ от API - больше нет истории
                this._updateChatState(chatId, { hasMore: false });
            }

            // Возвращаем только реально добавленные сообщения
            return messages.filter(m => this.store.hasMessage(m.id));

        } catch (error) {
            console.error('[MessageLoader] Failed to load history:', error);
            throw error;
        } finally {
            state.history = false;
        }
    }

    // ==================== WebSocket обработчики ====================

    /**
     * Обрабатывает новое сообщение из WebSocket
     * @param {Object} message - Сообщение с сервера
     */
    handleNewMessage(message) {
        if (!message || !message.id) {
            console.error('[MessageLoader] Invalid message received:', message);
            return;
        }

        // Убеждаемся что есть chat_id
        if (!message.chat_id && this.currentChatId) {
            message.chat_id = this.currentChatId;
        }

        // Проверяем - это подтверждение оптимистичного сообщения?
        if (message.temp_id) {
            const optimistic = this.store.optimisticMessages.get(message.temp_id);
            if (optimistic) {
                this.store.confirmOptimisticMessage(message.temp_id, message);
                return;
            }
        }

        // Обычное новое сообщение
        this.store.addMessage(message);
    }

    /**
     * Обрабатывает редактирование сообщения из WebSocket
     * @param {Object} data - Данные редактирования
     */
    handleMessageEdited(data) {
        const { message } = data;
        if (!message || !message.id) {
            console.error('[MessageLoader] Invalid edit data:', data);
            return;
        }

        this.store.updateMessage(message.id, message);
    }

    /**
     * Обрабатывает удаление сообщения из WebSocket
     * @param {Object} data - Данные удаления
     */
    handleMessageRemoved(data) {
        const messageId = data.message_id || data.messageId;
        if (!messageId) {
            console.error('[MessageLoader] Invalid remove data:', data);
            return;
        }

        this.store.removeMessage(messageId);
    }

    /**
     * Обрабатывает добавление реакции
     * @param {Object} data - Данные реакции
     */
    handleReactionAdded(data) {
        const { message_id, reactions_summary } = data;
        if (!message_id) return;

        const message = this.store.getMessage(message_id);
        if (message) {
            this.store.updateMessage(message_id, { reactions_summary });
        }
    }

    /**
     * Обрабатывает удаление реакции
     * @param {Object} data - Данные реакции
     */
    handleReactionRemoved(data) {
        const { message_id, reactions_summary } = data;
        if (!message_id) return;

        const message = this.store.getMessage(message_id);
        if (message) {
            this.store.updateMessage(message_id, { reactions_summary });
        }
    }

    // ==================== Отправка сообщений ====================

    /**
     * Отправляет сообщение оптимистично (показываем до подтверждения сервера)
     * @param {number} chatId - ID чата
     * @param {string} content - Содержимое сообщения
     * @param {Object} options - Дополнительные опции
     * @returns {string} Временный ID сообщения
     */
    sendMessageOptimistically(chatId, content, options = {}) {
        const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        const optimisticMessage = {
            id: tempId,
            temp_id: tempId,
            chat_id: chatId,
            author_id: this.currentUserId,
            content,
            created_ts: Date.now(),
            status: 'sending',
            is_edited: false,
            reactions_summary: {},
            ...options
        };

        console.log('[MessageLoader] Sending optimistic message:', tempId);

        // Добавляем в Store как оптимистичное
        this.store.addMessage(optimisticMessage, true);

        // Отправляем через WebSocket (если доступен)
        if (this.ws && this.ws.send) {
            try {
                this.ws.send({
                    type: 'send_message',
                    chat_id: chatId,
                    content,
                    temp_id: tempId,
                    ...options
                });
            } catch (error) {
                console.error('[MessageLoader] Failed to send via WS:', error);
                this.store.failOptimisticMessage(tempId);
            }
        } else {
            console.warn('[MessageLoader] WebSocket not available, message not sent');
            this.store.failOptimisticMessage(tempId);
        }

        return tempId;
    }

    // ==================== Утилиты ====================

    /**
     * Проверяет можно ли загрузить больше истории
     * @param {number} chatId - ID чата
     * @returns {boolean}
     */
    hasMoreHistory(chatId) {
        const chatState = this._getChatState(chatId);
        return chatState.hasMore;
    }

    /**
     * Проверяет загружается ли что-то для чата
     * @param {number} chatId - ID чата
     * @returns {boolean}
     */
    isLoading(chatId) {
        const state = this._getLoadingState(chatId);
        return state.initial || state.history;
    }

    /**
     * Получает статус загрузки для чата
     * @param {number} chatId - ID чата
     * @returns {Object}
     */
    getLoadingStatus(chatId) {
        return {
            ...this._getLoadingState(chatId),
            ...this._getChatState(chatId)
        };
    }

    // ==================== Приватные методы ====================

    /**
     * Получает состояние загрузки для чата
     * @private
     */
    _getLoadingState(chatId) {
        if (!this.loadingState.has(chatId)) {
            this.loadingState.set(chatId, {
                initial: false,
                history: false,
                status: 'idle'
            });
        }
        return this.loadingState.get(chatId);
    }

    /**
     * Получает состояние чата
     * @private
     */
    _getChatState(chatId) {
        if (!this.chatState.has(chatId)) {
            this.chatState.set(chatId, {
                hasMore: true,
                oldestId: null
            });
        }
        return this.chatState.get(chatId);
    }

    /**
     * Обновляет состояние чата
     * @private
     */
    _updateChatState(chatId, updates) {
        const state = this._getChatState(chatId);
        Object.assign(state, updates);
    }
}

export default MessageLoader;

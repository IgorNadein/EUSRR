/**
 * @fileoverview MessageStore - централизованное хранилище сообщений
 * @module stores/messageStore
 * 
 * Реализует паттерн Single Source of Truth для всех сообщений в приложении.
 * Все операции с сообщениями проходят через Store, что обеспечивает:
 * - Отсутствие дубликатов
 * - Предсказуемое состояние
 * - Легкое кэширование
 * - Централизованные уведомления об изменениях
 */

/**
 * Тип события изменения Store
 * @typedef {'message_added' | 'message_updated' | 'message_removed' | 'messages_loaded'} StoreEvent
 */

/**
 * Формат сообщения в Store
 * @typedef {Object} Message
 * @property {number|string} id - ID сообщения
 * @property {number} chat_id - ID чата
 * @property {number} author_id - ID автора
 * @property {string} content - Содержимое сообщения
 * @property {number} created_ts - Timestamp создания (миллисекунды)
 * @property {boolean} [is_edited] - Отредактировано ли
 * @property {number} [edited_at] - Timestamp редактирования
 * @property {Object} [reactions_summary] - Реакции на сообщение
 * @property {string} [status] - Статус ('sending', 'sent', 'failed')
 * @property {string} [temp_id] - Временный ID для оптимистичных обновлений
 */

/**
 * MessageStore - централизованное хранилище сообщений
 */
export class MessageStore {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {number} options.currentUserId - ID текущего пользователя
     */
    constructor(options = {}) {
        /** @type {Map<number|string, Message>} */
        this.messages = new Map();
        
        /** @type {Map<number, Array<number|string>>} Отсортированные ID сообщений по чатам */
        this.chatMessages = new Map();
        
        /** @type {Set<Function>} Слушатели изменений */
        this.listeners = new Set();
        
        /** @type {Map<string, Message>} Оптимистичные сообщения (еще не подтверждены сервером) */
        this.optimisticMessages = new Map();
        
        this.currentUserId = options.currentUserId;
        
        console.log('[MessageStore] Initialized');
    }

    // ==================== Управление сообщениями ====================

    /**
     * Добавляет сообщение в Store
     * @param {Message} message - Сообщение для добавления
     * @param {boolean} optimistic - Является ли оптимистичным (не подтверждено сервером)
     * @returns {number} 1 если добавлено, 0 если дубликат
     */
    addMessage(message, optimistic = false) {
        if (!message || !message.id) {
            console.error('[MessageStore] Invalid message:', message);
            return 0;
        }

        // Проверяем дубликаты (тихо отклоняем - это нормальное поведение)
        if (this.messages.has(message.id)) {
            return 0;
        }

        // Нормализуем сообщение: created_at → created_ts
        const normalizedMessage = { ...message };
        if (message.created_at && !message.created_ts) {
            normalizedMessage.created_ts = new Date(message.created_at).getTime();
        }

        // Добавляем в основное хранилище
        this.messages.set(message.id, normalizedMessage);
        
        // Добавляем в оптимистичное хранилище если нужно
        if (optimistic && message.temp_id) {
            this.optimisticMessages.set(message.temp_id, normalizedMessage);
        }

        // Добавляем в список сообщений чата (сортированный)
        if (message.chat_id) {
            this._addToChatMessages(message.chat_id, message.id, normalizedMessage.created_ts);
        }
        
        // Уведомляем слушателей
        this._notify('message_added', { message, optimistic });
        
        return 1;
    }

    /**
     * Добавляет множество сообщений (batch)
     * @param {Array<Message>} messages - Массив сообщений
     * @returns {number} Количество добавленных сообщений
     */
    addMessages(messages) {
        if (!Array.isArray(messages)) {
            console.error('[MessageStore] Invalid messages array:', messages);
            return 0;
        }

        console.log('[MessageStore] addMessages: adding', messages.length, 'messages');
        let addedCount = 0;
        messages.forEach(message => {
            if (this.addMessage(message, false)) {
                addedCount++;
            }
        });

        console.log('[MessageStore] Batch added:', addedCount, 'of', messages.length, '| Total in store:', this.messages.size);
        
        // Уведомляем о batch загрузке
        this._notify('messages_loaded', { messages, count: addedCount });
        
        return addedCount;
    }

    /**
     * Обновляет существующее сообщение
     * @param {number|string} messageId - ID сообщения
     * @param {Partial<Message>} updates - Обновления
     * @returns {boolean} true если обновлено успешно
     */
    updateMessage(messageId, updates) {
        const message = this.messages.get(messageId);
        if (!message) {
            console.warn('[MessageStore] Message not found for update:', messageId);
            return false;
        }

        // Применяем обновления
        const updated = { ...message, ...updates };
        this.messages.set(messageId, updated);

        console.log('[MessageStore] Message updated:', messageId, updates);
        
        // Уведомляем слушателей
        this._notify('message_updated', { messageId, message: updated, updates });
        
        return true;
    }

    /**
     * Удаляет сообщение из Store
     * @param {number|string} messageId - ID сообщения
     * @returns {boolean} true если удалено успешно
     */
    removeMessage(messageId) {
        const message = this.messages.get(messageId);
        if (!message) {
            console.warn('[MessageStore] Message not found for removal:', messageId);
            return false;
        }

        // Удаляем из основного хранилища
        this.messages.delete(messageId);

        // Удаляем из списка чата
        if (message.chat_id) {
            const chatMsgIds = this.chatMessages.get(message.chat_id);
            if (chatMsgIds) {
                const index = chatMsgIds.indexOf(messageId);
                if (index > -1) {
                    chatMsgIds.splice(index, 1);
                }
            }
        }

        console.log('[MessageStore] Message removed:', messageId);
        
        // Уведомляем слушателей
        this._notify('message_removed', { messageId, message });
        
        return true;
    }

    // ==================== Оптимистичные обновления ====================

    /**
     * Добавляет оптимистичное сообщение (еще не подтверждено сервером)
     * @param {string} tempId - Временный ID сообщения
     * @param {Message} message - Сообщение с временным ID
     * @returns {number} 1 если добавлено, 0 если ошибка
     */
    addOptimisticMessage(tempId, message) {
        if (!tempId || !message) {
            console.error('[MessageStore] Invalid optimistic message:', tempId, message);
            return 0;
        }

        // Добавляем как обычное сообщение с флагом optimistic
        const optimisticMsg = {
            ...message,
            id: message.id || tempId,
            temp_id: tempId,
            is_optimistic: true,
            status: 'sending'
        };

        // Сохраняем в optimisticMessages Map
        this.optimisticMessages.set(tempId, optimisticMsg);

        // Добавляем в основное хранилище
        const result = this.addMessage(optimisticMsg, true);
        
        console.log('[MessageStore] Optimistic message added:', tempId);
        return result;
    }

    /**
     * Подтверждает оптимистичное сообщение (пришел ответ от сервера)
     * @param {string} tempId - Временный ID
     * @param {Message} serverMessage - Сообщение с сервера
     * @returns {boolean} true если подтверждено успешно
     */
    confirmOptimisticMessage(tempId, serverMessage) {
        const optimisticMsg = this.optimisticMessages.get(tempId);
        if (!optimisticMsg) {
            console.warn('[MessageStore] Optimistic message not found:', tempId);
            // Добавляем как обычное сообщение
            return this.addMessage(serverMessage, false);
        }

        // Удаляем временное сообщение
        this.messages.delete(optimisticMsg.id);
        this.optimisticMessages.delete(tempId);

        // Удаляем из списка чата
        if (optimisticMsg.chat_id) {
            const chatMsgIds = this.chatMessages.get(optimisticMsg.chat_id);
            if (chatMsgIds) {
                const index = chatMsgIds.indexOf(optimisticMsg.id);
                if (index > -1) {
                    chatMsgIds.splice(index, 1);
                }
            }
        }

        // Добавляем подтвержденное сообщение
        this.addMessage(serverMessage, false);

        console.log('[MessageStore] Optimistic message confirmed:', tempId, '→', serverMessage.id);
        
        return true;
    }

    /**
     * Помечает оптимистичное сообщение как failed
     * @param {string} tempId - Временный ID
     * @returns {boolean} true если обновлено успешно
     */
    failOptimisticMessage(tempId) {
        const optimisticMsg = this.optimisticMessages.get(tempId);
        if (!optimisticMsg) {
            console.warn('[MessageStore] Optimistic message not found:', tempId);
            return false;
        }

        this.updateMessage(optimisticMsg.id, { status: 'failed' });
        return true;
    }

    // ==================== Геттеры ====================

    /**
     * Получить сообщение по ID
     * @param {number|string} messageId - ID сообщения
     * @returns {Message|null}
     */
    getMessage(messageId) {
        return this.messages.get(messageId) || null;
    }

    /**
     * Получить все сообщения для чата
     * @param {number} chatId - ID чата
     * @param {Object} options - Опции
     * @param {number} [options.limit] - Ограничение количества
     * @param {number|string} [options.beforeId] - Получить сообщения до этого ID
     * @param {number|string} [options.afterId] - Получить сообщения после этого ID
     * @returns {Array<Message>}
     */
    getMessagesForChat(chatId, options = {}) {
        const messageIds = this.chatMessages.get(chatId) || [];
        let messages = messageIds.map(id => this.messages.get(id)).filter(Boolean);

        // Фильтрация по beforeId
        if (options.beforeId) {
            const beforeIndex = messages.findIndex(m => m.id === options.beforeId);
            if (beforeIndex > -1) {
                messages = messages.slice(0, beforeIndex);
            }
        }

        // Фильтрация по afterId
        if (options.afterId) {
            const afterIndex = messages.findIndex(m => m.id === options.afterId);
            if (afterIndex > -1) {
                messages = messages.slice(afterIndex + 1);
            }
        }

        // Лимит
        if (options.limit) {
            messages = messages.slice(-options.limit);
        }

        return messages;
    }

    /**
     * Получить сообщения с day-dividers
     * @param {number} chatId - ID чата
     * @returns {Array<{type: 'divider'|'message', text?: string, message?: Message}>}
     */
    getMessagesWithDividers(chatId) {
        const messages = this.getMessagesForChat(chatId);
        const result = [];
        let lastDay = null;

        messages.forEach(message => {
            const msgDate = new Date(message.created_ts);
            const msgDay = this._formatDay(msgDate);

            // Добавляем divider если день изменился
            if (msgDay !== lastDay) {
                result.push({
                    type: 'day-divider',
                    text: msgDay
                });
                lastDay = msgDay;
            }

            // Добавляем сообщение
            result.push({
                type: 'message',
                message
            });
        });

        return result;
    }

    /**
     * Проверяет наличие сообщения
     * @param {number|string} messageId - ID сообщения
     * @returns {boolean}
     */
    hasMessage(messageId) {
        return this.messages.has(messageId);
    }

    /**
     * Получить сообщение по ID
     * @param {number|string} messageId - ID сообщения
     * @returns {Message|null}
     */
    getMessage(messageId) {
        return this.messages.get(messageId) || null;
    }

    /**
     * Получить самое старое сообщение в чате
     * @param {number} chatId - ID чата
     * @returns {Message|null}
     */
    getOldestMessage(chatId) {
        const messageIds = this.chatMessages.get(chatId) || [];
        if (messageIds.length === 0) return null;
        
        return this.messages.get(messageIds[0]) || null;
    }

    /**
     * Получить самое новое сообщение в чате
     * @param {number} chatId - ID чата
     * @returns {Message|null}
     */
    getNewestMessage(chatId) {
        const messageIds = this.chatMessages.get(chatId) || [];
        if (messageIds.length === 0) return null;
        
        return this.messages.get(messageIds[messageIds.length - 1]) || null;
    }

    /**
     * Получить количество сообщений в чате
     * @param {number} chatId - ID чата
     * @returns {number}
     */
    getMessageCount(chatId) {
        const messageIds = this.chatMessages.get(chatId) || [];
        return messageIds.length;
    }

    // ==================== Подписки ====================

    /**
     * Подписаться на изменения Store
     * @param {Function} listener - Функция-слушатель (event, data) => void
     * @returns {Function} Функция отписки
     */
    subscribe(listener) {
        if (typeof listener !== 'function') {
            console.error('[MessageStore] Listener must be a function');
            return () => {};
        }

        this.listeners.add(listener);
        console.log('[MessageStore] Listener subscribed, total:', this.listeners.size);

        // Возвращаем функцию отписки
        return () => this.unsubscribe(listener);
    }

    /**
     * Отписаться от изменений Store
     * @param {Function} listener - Функция-слушатель
     */
    unsubscribe(listener) {
        this.listeners.delete(listener);
        console.log('[MessageStore] Listener unsubscribed, remaining:', this.listeners.size);
    }

    // ==================== Утилиты ====================

    /**
     * Очистить все сообщения чата
     * @param {number} chatId - ID чата
     */
    clearChat(chatId) {
        const messageIds = this.chatMessages.get(chatId) || [];
        messageIds.forEach(id => this.messages.delete(id));
        this.chatMessages.delete(chatId);
        
        console.log('[MessageStore] Chat cleared:', chatId);
        this._notify('chat_cleared', { chatId });
    }

    /**
     * Получить статистику Store
     * @returns {Object}
     */
    getStats() {
        return {
            totalMessages: this.messages.size,
            totalChats: this.chatMessages.size,
            optimisticMessages: this.optimisticMessages.size,
            listeners: this.listeners.size
        };
    }

    // ==================== Приватные методы ====================

    /**
     * Добавляет ID сообщения в отсортированный список чата
     * @private
     */
    _addToChatMessages(chatId, messageId, timestamp) {
        if (!this.chatMessages.has(chatId)) {
            this.chatMessages.set(chatId, []);
        }

        const chatMsgIds = this.chatMessages.get(chatId);
        
        // Проверяем что messageId еще нет в индексе (защита от дублей)
        if (chatMsgIds.includes(messageId)) {
            return;
        }
        
        // Ищем правильную позицию для вставки
        let insertIndex = 0; // По умолчанию вставляем в начало
        
        for (let i = 0; i < chatMsgIds.length; i++) {
            const existingMsg = this.messages.get(chatMsgIds[i]);
            if (existingMsg && existingMsg.created_ts < timestamp) {
                insertIndex = i + 1;
            } else {
                // Нашли первое сообщение с timestamp >= нового
                break;
            }
        }

        chatMsgIds.splice(insertIndex, 0, messageId);
    }

    /**
     * Форматирует дату в текст дня
     * @private
     */
    _formatDay(date) {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        const isToday = date.toDateString() === today.toDateString();
        const isYesterday = date.toDateString() === yesterday.toDateString();

        if (isToday) return 'Сегодня';
        if (isYesterday) return 'Вчера';

        const options = { day: 'numeric', month: 'long', year: 'numeric' };
        return date.toLocaleDateString('ru-RU', options);
    }

    /**
     * Уведомляет всех слушателей об изменении
     * @private
     */
    _notify(event, data) {
        this.listeners.forEach(listener => {
            try {
                listener(event, data);
            } catch (error) {
                console.error('[MessageStore] Listener error:', error);
            }
        });
    }

    // ==================== Event Listeners ====================

    /**
     * Добавляет слушателя событий
     * @param {string} event - Название события (или '*' для всех)
     * @param {Function} callback - Функция-обработчик
     */
    on(event, callback) {
        if (typeof callback !== 'function') {
            console.error('[MessageStore] Invalid callback for event:', event);
            return;
        }

        // Оборачиваем callback чтобы фильтровать по event
        const wrappedCallback = (eventName, data) => {
            if (event === '*' || event === eventName) {
                callback(data);
            }
        };

        // Сохраняем связь для off()
        wrappedCallback._original = callback;
        wrappedCallback._event = event;

        this.listeners.add(wrappedCallback);
    }

    /**
     * Удаляет слушателя событий
     * @param {string} event - Название события
     * @param {Function} callback - Функция-обработчик
     */
    off(event, callback) {
        // Ищем обернутый callback
        for (const listener of this.listeners) {
            if (listener._original === callback && listener._event === event) {
                this.listeners.delete(listener);
                break;
            }
        }
    }

    /**
     * Удаляет всех слушателей
     */
    offAll() {
        this.listeners.clear();
    }
}

export default MessageStore;

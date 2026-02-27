/**
 * @fileoverview MessageStore V2 - оптимизированное хранилище сообщений
 * @module stores/messageStoreV2
 * 
 * РЕФАКТОРИНГ:
 * - Бинарный поиск для вставки в отсортированный список
 * - Batch операции с отложенными уведомлениями
 * - WeakMap для кэширования
 * - Оптимизированные геттеры
 * - Меньше логирования
 */

import { STORE_EVENTS } from '../config/chatConfig.js';
import { DateDividerManager } from '../utils/dateDividers.js';

/**
 * @typedef {Object} Message
 * @property {number|string} id - ID сообщения
 * @property {number} chat_id - ID чата
 * @property {number} author_id - ID автора
 * @property {string} content - Текст сообщения
 * @property {number} created_ts - Timestamp создания (мс)
 * @property {boolean} [is_edited] - Редактировано ли
 * @property {number} [edited_at] - Timestamp редактирования
 * @property {Object} [reactions_summary] - Реакции
 * @property {string} [status] - Статус: 'sending' | 'sent' | 'failed'
 * @property {string} [temp_id] - Временный ID для оптимистичных сообщений
 */

/**
 * @typedef {Object} DividerItem
 * @property {'divider'} type
 * @property {string} text
 */

/**
 * @typedef {Object} MessageItem
 * @property {'message'} type
 * @property {Message} message
 */

/**
 * MessageStore V2 - централизованное хранилище сообщений
 * Реализует паттерн Single Source of Truth.
 */
export class MessageStoreV2 {
    /**
     * @param {Object} options
     * @param {number} options.currentUserId - ID текущего пользователя
     */
    constructor(options = {}) {
        /** @type {Map<number|string, Message>} Основное хранилище */
        this.messages = new Map();
        
        /** @type {Map<number, Array<number|string>>} Отсортированные ID по чатам */
        this.chatIndex = new Map();
        
        /** @type {Map<string, Message>} Оптимистичные сообщения */
        this.optimisticMessages = new Map();
        
        /** @type {Set<Function>} Подписчики */
        this.listeners = new Set();
        
        /** @type {number} */
        this.currentUserId = options.currentUserId;

        // Batch mode
        this._batchMode = false;
        this._silentMode = false;
        this._pendingNotifications = [];

        console.log('[MessageStoreV2] Initialized');
    }

    // ==================== CRUD операции ====================

    /**
     * Добавляет сообщение в Store
     * @param {Message} message - Сообщение
     * @param {boolean} [optimistic=false] - Оптимистичное ли
     * @returns {boolean} true если добавлено
     */
    addMessage(message, optimistic = false) {
        if (!this._validateMessage(message)) {
            return false;
        }

        // Проверка дубликата
        if (this.messages.has(message.id)) {
            return false;
        }

        // Сохраняем копию
        const msgCopy = { ...message };
        this.messages.set(message.id, msgCopy);
        
        // Оптимистичные
        if (optimistic && message.temp_id) {
            this.optimisticMessages.set(message.temp_id, msgCopy);
        }

        // Индексируем по чату
        if (message.chat_id) {
            this._addToIndex(message.chat_id, message.id, message.created_ts);
        }

        // Уведомляем
        this._notify(STORE_EVENTS.MESSAGE_ADDED, { message: msgCopy, optimistic });
        
        return true;
    }

    /**
     * Добавляет множество сообщений (batch)
     * @param {Array<Message>} messages - Сообщения
     * @param {Object} [options] - Опции
     * @param {boolean} [options.silent=false] - Не emit'ить события
     * @returns {number} Количество добавленных
     */
    addMessages(messages, options = {}) {
        if (!Array.isArray(messages) || messages.length === 0) {
            return 0;
        }

        const { silent = false } = options;

        // Включаем batch mode
        this._batchMode = true;
        const oldSilent = this._silentMode;
        this._silentMode = silent;
        let addedCount = 0;

        try {
            for (const message of messages) {
                if (this.addMessage(message, false)) {
                    addedCount++;
                }
            }
        } finally {
            // Выключаем batch mode и отправляем все уведомления
            this._batchMode = false;
            this._silentMode = oldSilent;
            
            if (!silent) {
                this._flushNotifications();
            }
        }

        // Отправляем групповое уведомление только если не silent
        if (!silent) {
            this._notify(STORE_EVENTS.MESSAGES_LOADED, { count: addedCount });
        }

        return addedCount;
    }

    /**
     * Обновляет сообщение
     * @param {number|string} messageId - ID сообщения
     * @param {Partial<Message>} updates - Обновления
     * @returns {boolean}
     */
    updateMessage(messageId, updates) {
        const message = this.messages.get(messageId);
        if (!message) {
            return false;
        }

        const updated = { ...message, ...updates };
        this.messages.set(messageId, updated);

        this._notify(STORE_EVENTS.MESSAGE_UPDATED, { 
            messageId, 
            message: updated, 
            updates 
        });
        
        return true;
    }

    /**
     * Удаляет сообщение
     * @param {number|string} messageId - ID сообщения
     * @returns {boolean}
     */
    removeMessage(messageId) {
        const message = this.messages.get(messageId);
        if (!message) {
            return false;
        }

        this.messages.delete(messageId);

        // Удаляем из индекса
        if (message.chat_id) {
            this._removeFromIndex(message.chat_id, messageId);
        }

        this._notify(STORE_EVENTS.MESSAGE_REMOVED, { messageId, message });
        
        return true;
    }

    // ==================== Оптимистичные обновления ====================

    /**
     * Подтверждает оптимистичное сообщение
     * @param {string} tempId - Временный ID
     * @param {Message} serverMessage - Сообщение с сервера
     * @returns {boolean}
     */
    confirmOptimisticMessage(tempId, serverMessage) {
        const optimisticMsg = this.optimisticMessages.get(tempId);
        
        if (!optimisticMsg) {
            // Просто добавляем как обычное
            return this.addMessage(serverMessage, false);
        }

        // Удаляем оптимистичное
        this.messages.delete(optimisticMsg.id);
        this.optimisticMessages.delete(tempId);
        
        if (optimisticMsg.chat_id) {
            this._removeFromIndex(optimisticMsg.chat_id, optimisticMsg.id);
        }

        // Добавляем подтвержденное
        this.addMessage(serverMessage, false);

        this._notify(STORE_EVENTS.OPTIMISTIC_CONFIRMED, { 
            tempId, 
            oldMessage: optimisticMsg, 
            newMessage: serverMessage 
        });
        
        return true;
    }

    /**
     * Помечает оптимистичное сообщение как failed
     * @param {string} tempId - Временный ID
     * @returns {boolean}
     */
    failOptimisticMessage(tempId) {
        const optimisticMsg = this.optimisticMessages.get(tempId);
        if (!optimisticMsg) {
            return false;
        }

        this.updateMessage(optimisticMsg.id, { status: 'failed' });
        
        this._notify(STORE_EVENTS.OPTIMISTIC_FAILED, { tempId, message: optimisticMsg });
        
        return true;
    }

    // ==================== Геттеры ====================

    /**
     * Получает сообщение по ID
     * @param {number|string} messageId
     * @returns {Message|null}
     */
    getMessage(messageId) {
        return this.messages.get(messageId) || null;
    }

    /**
     * Проверяет наличие сообщения
     * @param {number|string} messageId
     * @returns {boolean}
     */
    hasMessage(messageId) {
        return this.messages.has(messageId);
    }

    /**
     * Получает все сообщения чата
     * @param {number} chatId
     * @param {Object} [options]
     * @param {number} [options.limit]
     * @param {number|string} [options.beforeId]
     * @param {number|string} [options.afterId]
     * @returns {Array<Message>}
     */
    getMessagesForChat(chatId, options = {}) {
        const messageIds = this.chatIndex.get(chatId) || [];
        let messages = messageIds
            .map(id => this.messages.get(id))
            .filter(Boolean);

        // Фильтрация по beforeId
        if (options.beforeId) {
            const idx = messages.findIndex(m => m.id === options.beforeId);
            if (idx > -1) {
                messages = messages.slice(0, idx);
            }
        }

        // Фильтрация по afterId
        if (options.afterId) {
            const idx = messages.findIndex(m => m.id === options.afterId);
            if (idx > -1) {
                messages = messages.slice(idx + 1);
            }
        }

        // Лимит
        if (options.limit) {
            messages = messages.slice(-options.limit);
        }

        return messages;
    }

    /**
     * Получает сообщения с day-dividers
     * @param {number} chatId
     * @returns {Array<DividerItem|MessageItem>}
     */
    getMessagesWithDividers(chatId) {
        const messages = this.getMessagesForChat(chatId);
        const result = [];
        let lastDay = null;

        for (const message of messages) {
            const day = DateDividerManager.formatDay(new Date(message.created_ts));
            
            if (day !== lastDay) {
                result.push({ type: 'divider', text: day });
                lastDay = day;
            }
            
            result.push({ type: 'message', message });
        }

        return result;
    }

    /**
     * Получает самое старое сообщение чата
     * @param {number} chatId
     * @returns {Message|null}
     */
    getOldestMessage(chatId) {
        const ids = this.chatIndex.get(chatId);
        if (!ids || ids.length === 0) return null;
        return this.messages.get(ids[0]) || null;
    }

    /**
     * Получает самое новое сообщение чата
     * @param {number} chatId
     * @returns {Message|null}
     */
    getNewestMessage(chatId) {
        const ids = this.chatIndex.get(chatId);
        if (!ids || ids.length === 0) return null;
        return this.messages.get(ids[ids.length - 1]) || null;
    }

    /**
     * Получает количество сообщений в чате
     * @param {number} chatId
     * @returns {number}
     */
    getMessageCount(chatId) {
        return (this.chatIndex.get(chatId) || []).length;
    }

    /**
     * Получает статистику Store
     * @returns {Object}
     */
    getStats() {
        return {
            totalMessages: this.messages.size,
            totalChats: this.chatIndex.size,
            optimisticMessages: this.optimisticMessages.size,
            listeners: this.listeners.size
        };
    }

    // ==================== Подписки ====================

    /**
     * Подписаться на изменения
     * @param {Function} listener - (event, data) => void
     * @returns {Function} Функция отписки
     */
    subscribe(listener) {
        if (typeof listener !== 'function') {
            throw new Error('[MessageStoreV2] Listener must be a function');
        }
        
        this.listeners.add(listener);
        return () => this.unsubscribe(listener);
    }

    /**
     * Отписаться
     * @param {Function} listener
     */
    unsubscribe(listener) {
        this.listeners.delete(listener);
    }

    // ==================== Управление ====================

    /**
     * Очищает сообщения чата
     * @param {number} chatId
     */
    clearChat(chatId) {
        const ids = this.chatIndex.get(chatId) || [];
        
        for (const id of ids) {
            this.messages.delete(id);
        }
        
        this.chatIndex.delete(chatId);
        
        this._notify(STORE_EVENTS.CHAT_CLEARED, { chatId });
    }

    /**
     * Полная очистка Store
     */
    clear() {
        this.messages.clear();
        this.chatIndex.clear();
        this.optimisticMessages.clear();
    }

    // ==================== Приватные методы ====================

    /**
     * Валидирует сообщение
     * @private
     */
    _validateMessage(message) {
        if (!message || !message.id) {
            console.error('[MessageStoreV2] Invalid message:', message);
            return false;
        }
        return true;
    }

    /**
     * Добавляет в индекс с бинарным поиском
     * @private
     */
    _addToIndex(chatId, messageId, timestamp) {
        if (!this.chatIndex.has(chatId)) {
            this.chatIndex.set(chatId, []);
        }

        const ids = this.chatIndex.get(chatId);
        
        // Проверка дубликата в индексе
        if (ids.includes(messageId)) {
            return;
        }

        // Бинарный поиск для правильной позиции
        let left = 0;
        let right = ids.length;

        while (left < right) {
            const mid = (left + right) >>> 1;
            const midMsg = this.messages.get(ids[mid]);
            
            if (midMsg && midMsg.created_ts <= timestamp) {
                left = mid + 1;
            } else {
                right = mid;
            }
        }

        ids.splice(left, 0, messageId);
    }

    /**
     * Удаляет из индекса
     * @private
     */
    _removeFromIndex(chatId, messageId) {
        const ids = this.chatIndex.get(chatId);
        if (!ids) return;
        
        const idx = ids.indexOf(messageId);
        if (idx > -1) {
            ids.splice(idx, 1);
        }
    }

    /**
     * Уведомляет подписчиков
     * @private
     */
    _notify(event, data) {
        if (this._batchMode) {
            this._pendingNotifications.push({ event, data });
            return;
        }

        for (const listener of this.listeners) {
            try {
                listener(event, data);
            } catch (error) {
                console.error('[MessageStoreV2] Listener error:', error);
            }
        }
    }

    /**
     * Отправляет накопленные уведомления
     * @private
     */
    _flushNotifications() {
        const notifications = this._pendingNotifications;
        this._pendingNotifications = [];

        for (const { event, data } of notifications) {
            this._notify(event, data);
        }
    }
}

export default MessageStoreV2;

/**
 * @fileoverview ChatController V2 - рефакторированный координатор чата
 * @module controllers/chatControllerV2
 * 
 * РЕФАКТОРИНГ:
 * - Чистая архитектура с разделением ответственности
 * - Минимум логирования (только важные события)
 * - Улучшенная обработка ошибок
 * - Полная типизация JSDoc
 * - Поддержка отмены операций
 */

import { MessageStoreV2 } from '../stores/messageStoreV2.js';
import { MessageLoaderV2 } from '../loaders/messageLoaderV2.js';
import { MessageRendererV2 } from '../renderers/messageRendererV2.js';
import { ScrollManagerV2 } from '../managers/scrollManagerV2.js';
import { CHAT_EVENTS, WS_EVENTS, SCROLL_CONFIG, AUTOSCROLL_CONFIG } from '../config/chatConfig.js';

/**
 * @typedef {Object} ChatControllerOptions
 * @property {number} chatId - ID чата
 * @property {HTMLElement} scrollElement - Контейнер для скролла
 * @property {number} currentUserId - ID текущего пользователя
 * @property {string} [containerId='chatScroll'] - ID контейнера сообщений
 * @property {Object} [wsConnection] - WebSocket соединение
 * @property {string} [profileUrl] - URL профиля пользователя
 * @property {string} [detailUrlTemplate] - Шаблон URL детальной информации
 * @property {number|null} [lastReadMessageId] - ID последнего прочитанного сообщения
 */

/**
 * ChatController V2 - главный координатор чата
 * Единая точка входа для работы с чатом.
 */
export class ChatControllerV2 {
    /**
     * @param {ChatControllerOptions} options
     */
    constructor(options) {
        this._validateOptions(options);
        
        // Основные параметры
        this.chatId = options.chatId;
        this.currentUserId = options.currentUserId;
        this.scrollElement = options.scrollElement;
        this.containerId = options.containerId || 'chatScroll';
        this.lastReadMessageId = options.lastReadMessageId || null;

        // Создаем компоненты
        this.store = new MessageStoreV2({ currentUserId: this.currentUserId });
        
        this.loader = new MessageLoaderV2({
            store: this.store,
            wsConnection: options.wsConnection,
            currentUserId: this.currentUserId
        });

        this.renderer = new MessageRendererV2({
            store: this.store,
            containerId: this.containerId,
            currentUserId: this.currentUserId,
            profileUrl: options.profileUrl || '/employees/profile/',
            detailUrlTemplate: options.detailUrlTemplate || '/employees/detail/0/'
        });

        this.scrollManager = new ScrollManagerV2({
            scrollElement: this.scrollElement,
            loader: this.loader,
            renderer: this.renderer,
            store: this.store,
            chatId: this.chatId
        });

        // Состояние
        this._initialized = false;
        this._initializing = false;
        this._destroyed = false;
        
        // Индикатор новых сообщений (умный автоскролл)
        this._newMessagesCount = 0;
        this._newMessagesBtn = null;
        this._scrollWatcherCleanup = null;
        
        // Слушатели для cleanup
        this._eventListeners = [];

        // Подписки
        this._setupStoreSubscription();
        if (options.wsConnection) {
            this._setupWebSocketListeners();
        }

        console.log('[ChatControllerV2] Created for chat:', this.chatId);
    }

    // ==================== Публичное API - Жизненный цикл ====================

    /**
     * Инициализирует чат: загружает сообщения, рендерит, настраивает скролл
     * @returns {Promise<void>}
     */
    async init() {
        if (this._initialized) {
            console.warn('[ChatControllerV2] Already initialized');
            return;
        }
        
        if (this._initializing) {
            console.warn('[ChatControllerV2] Initialization in progress');
            return;
        }

        this._initializing = true;

        try {
            // 1. Загружаем сообщения
            const loadResult = await this.loader.loadInitial(this.chatId, {
                aroundMessageId: this.lastReadMessageId
            });

            // 2. Скрываем контейнер для плавного рендера
            this.scrollElement.style.visibility = 'hidden';

            try {
                // 3. Рендерим сообщения
                await this.renderer.render(this.chatId);

                // 4. СНАЧАЛА показываем контейнер (важно для scrollTop!)
                this.scrollElement.style.visibility = '';

                // Ждем один frame чтобы браузер применил visibility
                await new Promise(resolve => requestAnimationFrame(resolve));

                // 5. Скроллим к нужной позиции
                if (loadResult.anchorId) {
                    // Есть последнее прочитанное - скроллим к нему
                    await this._scrollToMessage(loadResult.anchorId);
                } else {
                    // Нет anchor - скроллим в самый низ (как в Telegram)
                    console.log('[ChatControllerV2] Scrolling to bottom (no anchor)...', {
                        scrollHeightBefore: this.scrollElement.scrollHeight,
                        scrollTopBefore: this.scrollElement.scrollTop,
                        clientHeight: this.scrollElement.clientHeight
                    });
                    
                    // Используем scrollTo() вместо scrollTop (более надежно)
                    await new Promise(resolve => {
                        requestAnimationFrame(() => {
                            requestAnimationFrame(() => {
                                const targetScroll = this.scrollElement.scrollHeight;
                                
                                // Используем scrollTo с auto (не smooth!)
                                this.scrollElement.scrollTo({
                                    top: targetScroll,
                                    behavior: 'auto'
                                });
                                
                                // Проверяем через setTimeout
                                setTimeout(() => {
                                    console.log('[ChatControllerV2] After scrollTo:', {
                                        scrollHeight: this.scrollElement.scrollHeight,
                                        scrollTop: this.scrollElement.scrollTop,
                                        targetScroll,
                                        success: Math.abs(this.scrollElement.scrollTop - targetScroll) < 5
                                    });
                                    resolve();
                                }, 10);
                            });
                        });
                    });
                }

                // 6. Инициализируем ScrollManager
                await this.scrollManager.init();

                // 7. Инициализируем watcher для умного автоскролла
                this._initScrollWatcher();

            } catch (error) {
                this.scrollElement.style.visibility = '';
                throw error;
            }

            this._initialized = true;
            this._initializing = false;

            // Dispatch события
            this._emit(CHAT_EVENTS.INITIALIZED, { chatId: this.chatId });
            
            console.log('[ChatControllerV2] Initialized successfully');

        } catch (error) {
            this._initializing = false;
            console.error('[ChatControllerV2] Initialization failed:', error);
            this._emit(CHAT_EVENTS.ERROR, { error, phase: 'init' });
            throw error;
        }
    }

    /**
     * Уничтожает контроллер и освобождает ресурсы
     */
    destroy() {
        if (this._destroyed) return;
        
        this._destroyed = true;

        // Отменяем активные запросы
        this.loader.cancelAll(this.chatId);

        // Уничтожаем ScrollManager
        this.scrollManager?.destroy();

        // Очищаем Store
        this.store?.clearChat(this.chatId);

        // Очищаем Renderer
        this.renderer?.clear();

        // Удаляем scroll watcher
        if (this._scrollWatcherCleanup) {
            this._scrollWatcherCleanup();
            this._scrollWatcherCleanup = null;
        }

        // Удаляем слушатели событий
        this._eventListeners.forEach(({ event, handler }) => {
            window.removeEventListener(event, handler);
        });
        this._eventListeners = [];

        console.log('[ChatControllerV2] Destroyed');
    }

    // ==================== Публичное API - Сообщения ====================

    /**
     * Отправляет сообщение
     * @param {string} content - Текст сообщения
     * @param {Object} [options] - Дополнительные опции
     * @returns {string|null} Временный ID или null при ошибке
     */
    sendMessage(content, options = {}) {
        if (!content?.trim()) {
            console.warn('[ChatControllerV2] Cannot send empty message');
            return null;
        }

        const tempId = this.loader.sendOptimistic(this.chatId, content.trim(), options);
        return tempId;
    }

    /**
     * Получает сообщение по ID
     * @param {number|string} messageId
     * @returns {Object|null}
     */
    getMessage(messageId) {
        return this.store.getMessage(messageId);
    }

    /**
     * Получает все сообщения чата
     * @param {Object} [options]
     * @returns {Array}
     */
    getMessages(options = {}) {
        return this.store.getMessagesForChat(this.chatId, options);
    }

    // ==================== Публичное API - Скролл ====================

    /**
     * Загружает больше истории
     * @returns {Promise<Array>}
     */
    async loadMoreHistory() {
        return this.scrollManager.loadMoreHistory();
    }

    /**
     * Прокручивает к последнему сообщению
     * @param {Object} [options]
     */
    scrollToBottom(options = {}) {
        this.scrollManager.scrollToBottom(options);
    }

    /**
     * Прокручивает к конкретному сообщению
     * @param {number|string} messageId
     * @param {Object} [options]
     */
    scrollToMessage(messageId, options = {}) {
        this.scrollManager.scrollToMessage(messageId, options);
    }

    /**
     * Проверяет находится ли пользователь внизу чата
     * @returns {boolean}
     */
    isNearBottom() {
        return this.scrollManager.isNearBottom();
    }

    // ==================== Публичное API - Состояние ====================

    /**
     * Получает статус контроллера
     * @returns {Object}
     */
    getStatus() {
        return {
            chatId: this.chatId,
            initialized: this._initialized,
            messageCount: this.store.getMessageCount(this.chatId),
            isLoading: this.loader.isLoading(this.chatId),
            hasMoreHistory: this.loader.hasMoreHistory(this.chatId),
            scroll: this.scrollManager.getStatus(),
            store: this.store.getStats(),
            renderer: this.renderer.getStats()
        };
    }

    /**
     * Проверяет инициализирован ли контроллер
     * @returns {boolean}
     */
    get isInitialized() {
        return this._initialized;
    }

    // ==================== Приватные методы - Подписки ====================

    /**
     * Настраивает подписку на Store
     * @private
     */
    _setupStoreSubscription() {
        this.store.subscribe((event, data) => {
            // Игнорируем события во время инициализации
            if (this._initializing) return;
            
            this._handleStoreEvent(event, data);
        });
    }

    /**
     * Обрабатывает события Store
     * @private
     */
    _handleStoreEvent(event, data) {
        switch (event) {
            case 'message_added':
                this._onMessageAdded(data);
                break;
            case 'message_updated':
                this._onMessageUpdated(data);
                break;
            case 'message_removed':
                this._onMessageRemoved(data);
                break;
        }
    }

    /**
     * Обработчик добавления сообщения
     * @private
     */
    _onMessageAdded(data) {
        const { message, optimistic } = data;
        
        if (message.chat_id !== this.chatId) return;

        // Рендерим новое сообщение
        this.renderer.appendMessage(message, this.chatId);

        // УМНЫЙ АВТОСКРОЛЛ:
        // 1. Своё сообщение - всегда скроллим
        // 2. Чужое сообщение + внизу чата - скроллим (активно читаем)
        // 3. Чужое сообщение + читаем историю - показываем индикатор
        const isMyMessage = message.author_id === this.currentUserId;
        const isAtBottom = this.scrollManager.isNearBottom();
        const shouldScroll = isMyMessage || isAtBottom;

        if (shouldScroll) {
            // Для своих сообщений - мгновенный скролл (AUTOSCROLL_CONFIG.SMOOTH_SCROLL_FOR_OWN)
            // Для чужих - проверка уже прошла выше (isAtBottom)
            this.scrollManager.scrollToBottom({ 
                instant: isMyMessage && !AUTOSCROLL_CONFIG.SMOOTH_SCROLL_FOR_OWN,
                force: isMyMessage
            });
            // Скрываем индикатор если он показан
            this._hideNewMessagesIndicator();
        } else if (!shouldScroll && !optimistic) {
            // Показываем индикатор только для НЕ-оптимистичных чужих сообщений
            this._showNewMessagesIndicator();
        }

        this._emit(CHAT_EVENTS.MESSAGE_ADDED, { messageId: message.id, chatId: this.chatId });
    }

    /**
     * Обработчик обновления сообщения
     * @private
     */
    _onMessageUpdated(data) {
        const { messageId, updates } = data;
        this.renderer.updateMessage(messageId, updates);
        this._emit(CHAT_EVENTS.MESSAGE_UPDATED, { messageId, updates, chatId: this.chatId });
    }

    /**
     * Обработчик удаления сообщения
     * @private
     */
    _onMessageRemoved(data) {
        const { messageId } = data;
        this.renderer.removeMessage(messageId);
        this._emit(CHAT_EVENTS.MESSAGE_REMOVED, { messageId, chatId: this.chatId });
    }

    /**
     * Настраивает слушатели WebSocket
     * @private
     */
    _setupWebSocketListeners() {
        const handlers = [
            [WS_EVENTS.NEW_MESSAGE, (e) => this._handleWsNewMessage(e.detail)],
            [WS_EVENTS.MESSAGE_EDITED, (e) => this._handleWsMessageEdited(e.detail)],
            [WS_EVENTS.MESSAGE_REMOVED, (e) => this._handleWsMessageRemoved(e.detail)],
            [WS_EVENTS.REACTION_ADDED, (e) => this._handleWsReaction(e.detail)],
            [WS_EVENTS.REACTION_REMOVED, (e) => this._handleWsReaction(e.detail)]
        ];

        handlers.forEach(([event, handler]) => {
            window.addEventListener(event, handler);
            this._eventListeners.push({ event, handler });
        });
    }

    /**
     * @private
     */
    _handleWsNewMessage(detail) {
        const { message, chatId } = detail;
        if (chatId === this.chatId && message) {
            this.loader.handleNewMessage(message);
        }
    }

    /**
     * @private
     */
    _handleWsMessageEdited(detail) {
        const { message, chatId } = detail;
        if (chatId === this.chatId && message) {
            this.loader.handleMessageEdited({ message });
        }
    }

    /**
     * @private
     */
    _handleWsMessageRemoved(detail) {
        const { messageId, chatId } = detail;
        if (chatId === this.chatId && messageId) {
            this.loader.handleMessageRemoved({ message_id: messageId });
        }
    }

    /**
     * @private
     */
    _handleWsReaction(detail) {
        const { messageId, reactionsSummary, chatId } = detail;
        if (chatId === this.chatId && messageId) {
            this.loader.handleReactionChange({
                message_id: messageId,
                reactions_summary: reactionsSummary
            });
        }
    }

    // ==================== Приватные методы - Утилиты ====================

    /**
     * Валидирует опции конструктора
     * @private
     */
    _validateOptions(options) {
        if (!options.chatId) {
            throw new Error('[ChatControllerV2] chatId is required');
        }
        if (!options.scrollElement) {
            throw new Error('[ChatControllerV2] scrollElement is required');
        }
        if (!options.currentUserId) {
            throw new Error('[ChatControllerV2] currentUserId is required');
        }
    }

    /**
     * Прокручивает к сообщению
     * @private
     */
    async _scrollToMessage(messageId) {
        if (!messageId) return false;

        // Ждем завершения рендера
        await new Promise(resolve => setTimeout(resolve, SCROLL_CONFIG.SCROLL_RESTORE_DELAY));

        const messageEl = this.scrollElement.querySelector(`[data-message-id="${messageId}"]`);
        
        if (messageEl) {
            messageEl.scrollIntoView({
                behavior: 'instant',
                block: 'center',
                inline: 'nearest'
            });
            return true;
        }
        
        return false;
    }

    /**
     * Отправляет событие
     * @private
     */
    _emit(eventName, detail) {
        window.dispatchEvent(new CustomEvent(eventName, { detail }));
    }

    // ==================== Умный автоскролл ====================

    /**
     * Показывает индикатор новых сообщений
     * @private
     */
    _showNewMessagesIndicator() {
        // Ищем или создаём кнопку
        if (!this._newMessagesBtn) {
            this._newMessagesBtn = this._findOrCreateNewMessagesButton();
        }

        if (!this._newMessagesBtn) {
            console.warn('[ChatControllerV2] New messages button not found');
            return;
        }

        // Увеличиваем счётчик
        this._newMessagesCount++;

        // Обновляем текст кнопки
        const badge = this._newMessagesBtn.querySelector('.badge');
        if (badge) {
            badge.textContent = this._newMessagesCount;
        }

        // Показываем кнопку
        this._newMessagesBtn.style.display = 'flex';
        this._newMessagesBtn.classList.add('show');
    }

    /**
     * Скрывает индикатор новых сообщений
     * @private
     */
    _hideNewMessagesIndicator() {
        if (!this._newMessagesBtn) {
            return;
        }

        // Сбрасываем счётчик
        this._newMessagesCount = 0;

        // Обновляем текст
        const badge = this._newMessagesBtn.querySelector('.badge');
        if (badge) {
            badge.textContent = '0';
        }

        // Скрываем кнопку
        this._newMessagesBtn.style.display = 'none';
        this._newMessagesBtn.classList.remove('show');
    }

    /**
     * Находит или создаёт кнопку новых сообщений
     * @private
     * @returns {HTMLElement|null}
     */
    _findOrCreateNewMessagesButton() {
        // Ищем существующую кнопку
        let btn = document.getElementById(AUTOSCROLL_CONFIG.NEW_MESSAGES_BTN_ID);
        
        if (btn) {
            return btn;
        }

        // Создаём новую кнопку
        btn = document.createElement('button');
        btn.id = AUTOSCROLL_CONFIG.NEW_MESSAGES_BTN_ID;
        btn.className = AUTOSCROLL_CONFIG.NEW_MESSAGES_BTN_CLASS;
        btn.style.display = 'none';
        btn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M10 14L10 6M10 14L6 10M10 14L14 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="badge">0</span> новых сообщения
        `;

        // Добавляем обработчик клика
        btn.addEventListener('click', () => {
            this.scrollManager.scrollToBottom({ 
                instant: !AUTOSCROLL_CONFIG.SMOOTH_SCROLL_ON_CLICK, 
                force: true 
            });
            this._hideNewMessagesIndicator();
        });

        // Добавляем в DOM
        const chatContainer = this.scrollElement.parentElement || document.body;
        chatContainer.appendChild(btn);

        return btn;
    }

    /**
     * Инициализирует отслеживание скролла для индикатора
     * @private
     */
    _initScrollWatcher() {
        // Слушаем скролл для автоматического скрытия индикатора
        const scrollHandler = () => {
            if (this.scrollManager.isNearBottom() && this._newMessagesCount > 0) {
                this._hideNewMessagesIndicator();
            }
        };
        
        this.scrollElement.addEventListener('scroll', scrollHandler);
        
        // Сохраняем handler для cleanup
        this._scrollWatcherCleanup = () => {
            this.scrollElement.removeEventListener('scroll', scrollHandler);
        };
    }
}

export default ChatControllerV2;

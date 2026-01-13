/**
 * @fileoverview ChatController - главный координатор чата
 * @module controllers/chatController
 * 
 * Единая точка входа для работы с чатом.
 * Координирует все компоненты: Store, Loader, Renderer, ScrollManager
 */

import { MessageStore } from '../stores/messageStore.js';
import { MessageLoader } from '../loaders/messageLoader.js';
import { MessageRendererV2 } from '../renderers/messageRendererV2.js';
import { ScrollManager } from '../managers/scrollManager.js';

/**
 * ChatController - координатор чата
 */
export class ChatController {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {number} options.chatId - ID чата
     * @param {HTMLElement} options.scrollElement - Контейнер для скролла
     * @param {string} options.containerId - ID контейнера сообщений
     * @param {number} options.currentUserId - ID текущего пользователя
     * @param {Object} options.wsConnection - WebSocket соединение
     * @param {string} [options.profileUrl] - URL профиля
     * @param {string} [options.detailUrlTemplate] - URL детальной информации
     * @param {number} [options.lastReadTimestamp] - Timestamp последнего прочитанного сообщения
     */
    constructor(options) {
        if (!options.chatId) {
            throw new Error('[ChatController] chatId is required');
        }
        if (!options.scrollElement) {
            throw new Error('[ChatController] scrollElement is required');
        }
        if (!options.currentUserId) {
            throw new Error('[ChatController] currentUserId is required');
        }

        this.chatId = options.chatId;
        this.currentUserId = options.currentUserId;
        this.scrollElement = options.scrollElement;
        this.scrollEl = options.scrollElement; // alias
        this.containerId = options.containerId || 'chatScroll';
        this.lastReadTimestamp = options.lastReadTimestamp || null;

        console.log('[ChatController] Initializing for chat:', this.chatId);

        // Создаем компоненты
        this.store = new MessageStore({ currentUserId: this.currentUserId });

        this.loader = new MessageLoader({
            store: this.store,
            wsConnection: options.wsConnection,
            currentUserId: this.currentUserId
        });

        this.renderer = new MessageRendererV2({
            store: this.store,
            containerId: this.containerId,
            currentUserId: this.currentUserId,
            profileUrl: options.profileUrl,
            detailUrlTemplate: options.detailUrlTemplate
        });

        this.scrollManager = new ScrollManager({
            scrollElement: this.scrollElement,
            messageLoader: this.loader,
            messageRenderer: this.renderer,
            messageStore: this.store,
            chatId: this.chatId
        });

        // Флаг инициализации
        this.initialized = false;
        this.isInitializing = false;

        // Индикатор новых сообщений
        this.newMessagesCount = 0;
        this.newMessagesBtn = null;

        // Подписываемся на изменения Store
        this._subscribeToStore();

        // Подписываемся на WebSocket (если есть)
        if (options.wsConnection) {
            this._subscribeToWebSocket(options.wsConnection);
        }

        console.log('[ChatController] Created');
    }

    // ==================== Инициализация ====================

    /**
     * Инициализирует чат (загружает сообщения, рендерит, скроллит)
     * @param {Object} options - Опции
     * @param {boolean} [options.scrollToBottom=true] - Прокрутить вниз после загрузки
     * @returns {Promise<void>}
     */
    async init(options = {}) {
        if (this.initialized) {
            console.warn('[ChatController] Already initialized');
            return;
        }

        try {
            console.log('[ChatController] ========================================');
            console.log('[ChatController] Initializing chat:', this.chatId);
            console.log('[ChatController] lastReadTimestamp:', this.lastReadTimestamp);
            console.log('[ChatController] lastReadTimestamp type:', typeof this.lastReadTimestamp);
            console.log('[ChatController] ========================================');

            // Устанавливаем флаг что идет начальная загрузка
            this.isInitializing = true;

            // 1. Загружаем начальные сообщения ВОКРУГ last_read
            console.log('[ChatController] Step 1: Loading messages around last read...');
            const loadResult = await this.loader.loadInitialMessages(this.chatId, {
                lastReadMessageId: this.lastReadTimestamp  // Используем как ID (нужно переименовать)
            });
            
            console.log('[ChatController] ========================================');
            console.log('[ChatController] Load result:', loadResult);
            console.log('[ChatController] ========================================');

            // 2. Скрываем контейнер чтобы избежать видимых прыжков
            console.log('[ChatController] Step 2: Hiding container for smooth render...');
            this.scrollEl.style.visibility = 'hidden';

            try {
                // 3. Рендерим (пользователь не видит процесс)
                console.log('[ChatController] Step 3: Rendering messages...');
                await this.renderer.render(this.chatId);

                // 4. ВАЖНО: Показываем контейнер ДО скролла (scrollTop не работает на hidden)
                console.log('[ChatController] Step 4: Showing container...');
                this.scrollEl.style.visibility = '';

                // 5. Прокручиваем к нужной позиции ПОСЛЕ показа контейнера
                console.log('[ChatController] Step 5: Scrolling to position...');
                console.log('[ChatController] Anchor ID from loadResult:', loadResult.anchorId);
                
                if (loadResult.anchorId) {
                    // Есть anchor - пытаемся скроллить к нему
                    const scrolled = await this._scrollToMessage(loadResult.anchorId);
                    console.log('[ChatController] Scrolled to anchor message:', loadResult.anchorId, '→', scrolled);
                    
                    if (!scrolled) {
                        // Не нашли anchor - оставляем прокрутку как есть (не скроллим автоматически)
                        console.log('[ChatController] Anchor not found, keeping scroll position');
                    }
                } else {
                    // Нет anchor (нет lastReadId) - оставляем прокрутку как есть (НЕ скроллим автоматически вниз)
                    console.log('[ChatController] No anchor, keeping scroll position');
                }
            } catch (scrollError) {
                console.error('[ChatController] ❌ Error during init:', scrollError);
                // В случае ошибки всё равно показываем контейнер
                this.scrollEl.style.visibility = '';
                throw scrollError;
            }

            // 6. Инициализируем ScrollManager ПОСЛЕ скролла
            console.log('[ChatController] Step 6: Initializing ScrollManager...');
            await this.scrollManager.init();

            // 7. Инициализируем отслеживание скролла для индикатора
            console.log('[ChatController] Step 7: Initializing scroll watcher...');
            this._initScrollWatcher();

            this.initialized = true;
            this.isInitializing = false; // Сбрасываем флаг
            console.log('[ChatController] ✅ Initialization complete');

            // Dispatch события для других компонентов
            this._dispatchEvent('chat:initialized', { chatId: this.chatId });

        } catch (error) {
            this.isInitializing = false; // ВАЖНО: Сбрасываем флаг даже при ошибке
            console.error('[ChatController] ❌ Initialization failed:', error);
            throw error;
        }
    }

    /**
     * Прокручивает к конкретному сообщению
     * @private
     * @param {number} messageId - ID сообщения
     * @param {number} [offset=100] - Отступ сверху в пикселях
     * @returns {Promise<boolean>} true если нашли и прокрутили
     */
    async _scrollToMessage(messageId, offset = 100) {
        console.log('[ChatController] ========================================');
        console.log('[ChatController] _scrollToMessage called');
        console.log('[ChatController] messageId:', messageId);
        console.log('[ChatController] offset:', offset);
        
        if (!messageId) {
            console.log('[ChatController] No messageId provided');
            console.log('[ChatController] ========================================');
            return false;
        }

        // Даём время на завершение DOM updates и browser reflow
        await new Promise(resolve => setTimeout(resolve, 150));

        // Ищем элемент в DOM
        const messageEl = this.scrollEl.querySelector(`[data-message-id="${messageId}"]`);
        console.log('[ChatController] Found element:', !!messageEl);
        
        if (messageEl) {
            console.log('[ChatController] Element classes:', messageEl.className);
            
            // Используем scrollIntoView - надежнее чем ручной scrollTop
            messageEl.scrollIntoView({
                behavior: 'instant',  // без анимации
                block: 'center',      // в центр viewport
                inline: 'nearest'
            });
            
            console.log('[ChatController] ✅ Scrolled to message:', messageId);
            console.log('[ChatController] ========================================');
            return true;
        }
        
        if (!messageEl) {
            console.warn('[ChatController] Message element not found in DOM:', messageId);
            console.log('[ChatController] Available message IDs:', 
                Array.from(this.scrollEl.querySelectorAll('[data-message-id]'))
                    .map(el => el.dataset.messageId).slice(0, 10)
            );
            console.log('[ChatController] ========================================');
            return false;
        }

        // Прокручиваем к элементу с отступом сверху
        const offsetTop = messageEl.offsetTop - offset;
        const scrollBefore = this.scrollEl.scrollTop;
        this.scrollEl.scrollTop = Math.max(0, offsetTop);
        const scrollAfter = this.scrollEl.scrollTop;

        console.log('[ChatController] Scroll details:');
        console.log('[ChatController]   Element offsetTop:', messageEl.offsetTop);
        console.log('[ChatController]   Target scrollTop:', offsetTop);
        console.log('[ChatController]   Scroll before:', scrollBefore);
        console.log('[ChatController]   Scroll after:', scrollAfter);
        console.log('[ChatController] ✅ Scrolled to message', messageId);
        console.log('[ChatController] ========================================');
        return true;
    }

    /**
     * Уничтожает контроллер и освобождает ресурсы
     */
    destroy() {
        console.log('[ChatController] Destroying...');

        // Очищаем scroll watcher
        if (this._scrollWatcherCleanup) {
            this._scrollWatcherCleanup();
            this._scrollWatcherCleanup = null;
        }

        // Останавливаем ScrollManager
        if (this.scrollManager) {
            this.scrollManager.destroy();
        }

        // Очищаем Store
        if (this.store) {
            this.store.clearChat(this.chatId);
        }

        // Очищаем рендерер
        if (this.renderer) {
            this.renderer.clear();
        }

        this.initialized = false;
        console.log('[ChatController] Destroyed');
    }

    // ==================== Подписки ====================

    /**
     * Подписывается на изменения Store
     * @private
     */
    _subscribeToStore() {
        this.store.subscribe((event, data) => {
            this._handleStoreUpdate(event, data);
        });
    }

    /**
     * Обрабатывает обновления из Store
     * @private
     */
    _handleStoreUpdate(event, data) {
        console.log('[ChatController] Store update:', event, data);

        switch (event) {
            case 'message_added':
                this._handleMessageAdded(data);
                break;

            case 'message_updated':
                this._handleMessageUpdated(data);
                break;

            case 'message_removed':
                this._handleMessageRemoved(data);
                break;

            case 'messages_loaded':
                // Batch загрузка - ничего не делаем, render() вызовется вручную
                break;

            case 'chat_cleared':
                // Чат очищен - можно обновить UI
                console.log('[ChatController] Chat cleared:', data);
                break;

            default:
                console.log('[ChatController] Unhandled store event:', event);
        }
    }

    /**
     * Обрабатывает добавление сообщения
     * @private
     */
    _handleMessageAdded(data) {
        const { message, optimistic } = data;

        // ВАЖНО: Игнорируем события во время начальной загрузки
        // Начальные сообщения рендерятся через render(), а не через appendMessage
        if (this.isInitializing) {
            console.log('[ChatController] Ignoring message_added during initialization:', message.id);
            return;
        }

        if (message.chat_id !== this.chatId) {
            console.log('[ChatController] Message for different chat:', message.chat_id, 'current:', this.chatId);
            // Сообщение для другого чата
            return;
        }

        console.log('[ChatController] ====== Processing message_added ======');
        console.log('[ChatController] Message ID:', message.id);
        console.log('[ChatController] Author ID:', message.author_id, 'Current User ID:', this.currentUserId);
        console.log('[ChatController] Optimistic:', optimistic);

        // Incremental render - добавляем только новое сообщение
        const wasEmpty = this.renderer.renderedMessages.size === 0;
        this.renderer.appendMessage(message, this.chatId);

        // Если это первое сообщение, настраиваем Observer
        if (wasEmpty) {
            this.scrollManager.setupIntersectionObserver();
        }

        // УМНЫЙ АВТОСКРОЛЛ:
        // 1. Своё сообщение - всегда скроллим
        // 2. Чужое сообщение + внизу чата - скроллим (активно читаем)
        // 3. Чужое сообщение + читаем историю - показываем индикатор
        const isMyMessage = message.author_id === this.currentUserId;
        const isAtBottom = this.scrollManager.isNearBottom();
        const shouldScroll = isMyMessage || isAtBottom;

        console.log('[ChatController] New message:', {
            id: message.id,
            isMyMessage,
            isAtBottom,
            shouldScroll,
            optimistic
        });

        // ВАЖНО: для оптимистичных сообщений тоже скроллим (если это наше сообщение)
        // Оптимистичное = только что отправленное пользователем
        if (shouldScroll) {
            // Для СВОИХ сообщений - force:true (игнорируем isNearBottom)
            // Для чужих - проверка уже прошла выше
            this.scrollManager.scrollToBottom({ 
                instant: false,
                force: isMyMessage  // Принудительно для своих сообщений
            });
            // Скрываем индикатор если он показан
            this._hideNewMessagesIndicator();
        } else if (!shouldScroll && !optimistic) {
            // Показываем индикатор "Новые сообщения" только для НЕ-оптимистичных чужих сообщений
            this._showNewMessagesIndicator();
        }

        // Dispatch события для других компонентов (reactions, context menu, etc.)
        this._dispatchEvent('chat:message-added', {
            messageId: message.id,
            chatId: this.chatId
        });
    }

    /**
     * Обрабатывает обновление сообщения
     * @private
     */
    _handleMessageUpdated(data) {
        const { messageId, updates } = data;

        // Патчим DOM
        this.renderer.updateMessage(messageId, updates);

        // Dispatch события
        this._dispatchEvent('chat:message-updated', {
            messageId,
            updates,
            chatId: this.chatId
        });
    }

    /**
     * Обрабатывает удаление сообщения
     * @private
     */
    _handleMessageRemoved(data) {
        const { messageId } = data;

        // Удаляем из DOM
        this.renderer.removeMessage(messageId);

        // Dispatch события
        this._dispatchEvent('chat:message-removed', {
            messageId,
            chatId: this.chatId
        });
    }

    /**
     * Подписывается на события WebSocket
     * @private
     */
    _subscribeToWebSocket(ws) {
        // Используем глобальные события вместо прямой подписки
        // Это позволяет userWebSocket оставаться независимым

        // ВАЖНО: ws:initial-messages НЕ обрабатываем!
        // Initial messages загружаются через HTTP в init()
        // Если обрабатывать WS initial - получим двойной render и прыжки

        // Новое сообщение
        window.addEventListener('ws:new-message', (event) => {
            const { message, chatId } = event.detail;
            if (chatId === this.chatId && message) {
                console.log('[ChatController] WS: new-message, id=%s', message.id);
                this.loader.handleNewMessage(message);
            }
        });

        // Редактирование сообщения
        window.addEventListener('ws:message-edited', (event) => {
            const { message, chatId } = event.detail;
            if (chatId === this.chatId && message) {
                console.log('[ChatController] WS: message-edited, id=%s', message.id);
                this.loader.handleMessageEdited({ message });
            }
        });

        // Удаление сообщения
        window.addEventListener('ws:message-removed', (event) => {
            const { messageId, chatId } = event.detail;
            if (chatId === this.chatId && messageId) {
                console.log('[ChatController] WS: message-removed, id=%s', messageId);
                this.loader.handleMessageRemoved({ message_id: messageId });
            }
        });

        // Добавление реакции
        window.addEventListener('ws:reaction-added', (event) => {
            const { messageId, reactionsSummary, chatId } = event.detail;
            if (chatId === this.chatId && messageId) {
                console.log('[ChatController] WS: reaction-added, msg=%s', messageId);
                this.loader.handleReactionAdded({ 
                    message_id: messageId, 
                    reactions_summary: reactionsSummary 
                });
            }
        });

        // Удаление реакции
        window.addEventListener('ws:reaction-removed', (event) => {
            const { messageId, reactionsSummary, chatId } = event.detail;
            if (chatId === this.chatId && messageId) {
                console.log('[ChatController] WS: reaction-removed, msg=%s', messageId);
                this.loader.handleReactionRemoved({ 
                    message_id: messageId, 
                    reactions_summary: reactionsSummary 
                });
            }
        });

        console.log('[ChatController] ✅ Subscribed to WebSocket events');
    }

    // ==================== Публичное API ====================

    /**
     * Отправляет сообщение
     * @param {string} content - Содержимое сообщения
     * @param {Object} options - Дополнительные опции
     * @returns {string} Временный ID сообщения
     */
    sendMessage(content, options = {}) {
        if (!content || typeof content !== 'string' || content.trim() === '') {
            console.warn('[ChatController] Cannot send empty message');
            return null;
        }

        console.log('[ChatController] Sending message...');

        const tempId = this.loader.sendMessageOptimistically(
            this.chatId,
            content.trim(),
            options
        );

        return tempId;
    }

    /**
     * Загружает больше истории
     * @returns {Promise<Array>}
     */
    async loadMoreHistory() {
        return this.scrollManager.loadMoreHistory();
    }

    /**
     * Прокручивает к последнему сообщению
     * @param {Object} options - Опции
     */
    scrollToBottom(options = {}) {
        this.scrollManager.scrollToBottom(options);
    }

    /**
     * Прокручивает к конкретному сообщению
     * @param {number|string} messageId - ID сообщения
     * @param {Object} options - Опции
     */
    scrollToMessage(messageId, options = {}) {
        this.scrollManager.scrollToMessage(messageId, options);
    }

    /**
     * Получает сообщение по ID
     * @param {number|string} messageId - ID сообщения
     * @returns {Message|null}
     */
    getMessage(messageId) {
        return this.store.getMessage(messageId);
    }

    /**
     * Получает все сообщения чата
     * @param {Object} options - Опции
     * @returns {Array<Message>}
     */
    getMessages(options = {}) {
        return this.store.getMessagesForChat(this.chatId, options);
    }

    /**
     * Проверяет находится ли пользователь внизу
     * @returns {boolean}
     */
    isNearBottom() {
        return this.scrollManager.isNearBottom();
    }

    // ==================== Индикатор новых сообщений ====================

    /**
     * Показывает индикатор новых сообщений
     * @private
     */
    _showNewMessagesIndicator() {
        console.log('[ChatController] _showNewMessagesIndicator called, count before:', this.newMessagesCount);
        console.trace('[ChatController] Stack trace');
        
        // Ищем или создаём кнопку
        if (!this.newMessagesBtn) {
            this.newMessagesBtn = this._findOrCreateNewMessagesButton();
        }

        if (!this.newMessagesBtn) {
            console.warn('[ChatController] New messages button not found');
            return;
        }

        // Увеличиваем счётчик
        this.newMessagesCount++;

        // Обновляем текст кнопки
        const badge = this.newMessagesBtn.querySelector('.badge');
        if (badge) {
            badge.textContent = this.newMessagesCount;
        }

        // Показываем кнопку
        this.newMessagesBtn.style.display = 'flex';
        this.newMessagesBtn.classList.add('show');

        console.log('[ChatController] New messages indicator shown:', this.newMessagesCount);
    }

    /**
     * Скрывает индикатор новых сообщений
     * @private
     */
    _hideNewMessagesIndicator() {
        if (!this.newMessagesBtn) {
            return;
        }

        console.log('[ChatController] _hideNewMessagesIndicator called, count before:', this.newMessagesCount);

        // Сбрасываем счётчик
        this.newMessagesCount = 0;

        // Обновляем текст
        const badge = this.newMessagesBtn.querySelector('.badge');
        if (badge) {
            badge.textContent = '0';
        }

        // Скрываем кнопку
        this.newMessagesBtn.style.display = 'none';
        this.newMessagesBtn.classList.remove('show');

        console.log('[ChatController] New messages indicator hidden');
    }

    /**
     * Находит или создаёт кнопку новых сообщений
     * @private
     * @returns {HTMLElement|null}
     */
    _findOrCreateNewMessagesButton() {
        // Ищем существующую кнопку
        let btn = document.getElementById('new-messages-btn');
        
        if (btn) {
            return btn;
        }

        // Создаём новую кнопку
        btn = document.createElement('button');
        btn.id = 'new-messages-btn';
        btn.className = 'new-messages-indicator';
        btn.style.display = 'none';
        btn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M10 14L10 6M10 14L6 10M10 14L14 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="badge">0</span> новых сообщения
        `;

        // Добавляем обработчик клика
        btn.addEventListener('click', () => {
            this.scrollManager.scrollToBottom({ instant: false, force: true });
            this._hideNewMessagesIndicator();
        });

        // Добавляем в DOM (ищем контейнер чата или body)
        const chatContainer = this.scrollElement.parentElement || document.body;
        chatContainer.appendChild(btn);

        console.log('[ChatController] Created new messages button');
        return btn;
    }

    /**
     * Инициализирует отслеживание скролла для индикатора
     * @private
     */
    _initScrollWatcher() {
        // Слушаем скролл для автоматического скрытия индикатора
        // БЕЗ debounce - срабатывает мгновенно для тестов и UX
        const scrollHandler = () => {
            // Если пользователь прокрутил вниз вручную - скрываем индикатор
            if (this.scrollManager.isNearBottom() && this.newMessagesCount > 0) {
                this._hideNewMessagesIndicator();
            }
        };
        
        this.scrollElement.addEventListener('scroll', scrollHandler);
        
        // Сохраняем handler для cleanup
        this._scrollWatcherCleanup = () => {
            this.scrollElement.removeEventListener('scroll', scrollHandler);
        };

        console.log('[ChatController] Scroll watcher initialized');
    }

    /**
     * Получает статус чата
     * @returns {Object}
     */
    getStatus() {
        return {
            chatId: this.chatId,
            initialized: this.initialized,
            messageCount: this.store.getMessageCount(this.chatId),
            isLoading: this.loader.isLoading(this.chatId),
            hasMoreHistory: this.loader.hasMoreHistory(this.chatId),
            scroll: this.scrollManager.getStatus(),
            store: this.store.getStats(),
            renderer: this.renderer.getStats()
        };
    }

    // ==================== Утилиты ====================

    /**
     * Отправляет кастомное событие
     * @private
     */
    _dispatchEvent(eventName, detail) {
        window.dispatchEvent(new CustomEvent(eventName, { detail }));
    }
}

// Экспорт для использования в других модулях
export default ChatController;

/**
 * @fileoverview ScrollManager V2 - оптимизированное управление прокруткой
 * @module managers/scrollManagerV2
 * 
 * РЕФАКТОРИНГ:
 * - Debounce/throttle для scroll events
 * - Оптимизированный IntersectionObserver
 * - Чистый API без дублирования кода
 * - Поддержка виртуализации (будущее)
 */

import { SCROLL_CONFIG, LOADER_CONFIG } from '../config/chatConfig.js';

/**
 * Создает debounced функцию
 * @param {Function} fn - Функция для debounce
 * @param {number} delay - Задержка в мс
 * @returns {Function}
 */
function debounce(fn, delay) {
    let timeoutId = null;
    return function(...args) {
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * Создает throttled функцию
 * @param {Function} fn - Функция для throttle
 * @param {number} limit - Минимальный интервал в мс
 * @returns {Function}
 */
function throttle(fn, limit) {
    let inThrottle = false;
    return function(...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * @typedef {Object} ScrollManagerOptions
 * @property {HTMLElement} scrollElement - Контейнер для скролла
 * @property {MessageLoaderV2} loader - Загрузчик сообщений
 * @property {MessageRendererV2} renderer - Рендерер сообщений
 * @property {MessageStore} store - Store сообщений
 * @property {number} chatId - ID чата
 */

/**
 * ScrollManager V2 - управление прокруткой чата
 */
export class ScrollManagerV2 {
    /**
     * @param {ScrollManagerOptions} options
     */
    constructor(options) {
        this._validateOptions(options);

        this.scrollEl = options.scrollElement;
        this.loader = options.loader;
        this.renderer = options.renderer;
        this.store = options.store;
        this.chatId = options.chatId;

        // Конфигурация
        this.config = { ...SCROLL_CONFIG };

        // Состояние
        this._historyObserver = null;
        this._isLoadingHistory = false;
        this._destroyed = false;

        // Bound handlers для cleanup
        this._boundScrollHandler = null;
        this._boundResizeHandler = null;

        // Debounced/throttled функции
        this._debouncedLoadHistory = debounce(
            () => this._triggerLoadHistory(),
            LOADER_CONFIG.HISTORY_DEBOUNCE
        );

        console.log('[ScrollManagerV2] Created for chat:', this.chatId);
    }

    // ==================== Публичное API ====================

    /**
     * Инициализирует ScrollManager
     * @returns {Promise<void>}
     */
    async init() {
        // Ждем стабилизации DOM
        await this._waitForLayout();
        
        this._setupIntersectionObserver();
        this._setupScrollListener();
        this._setupResizeListener();
        
        console.log('[ScrollManagerV2] Initialized');
    }

    /**
     * Уничтожает ScrollManager
     */
    destroy() {
        if (this._destroyed) return;
        
        this._destroyed = true;

        // Отключаем observer
        if (this._historyObserver) {
            this._historyObserver.disconnect();
            this._historyObserver = null;
        }

        // Удаляем слушатели
        if (this._boundScrollHandler) {
            this.scrollEl.removeEventListener('scroll', this._boundScrollHandler);
        }
        if (this._boundResizeHandler) {
            window.removeEventListener('resize', this._boundResizeHandler);
        }

        console.log('[ScrollManagerV2] Destroyed');
    }

    /**
     * Загружает больше истории
     * @returns {Promise<Array>}
     */
    async loadMoreHistory() {
        console.log('[ScrollManagerV2] ======================================');
        console.log('[ScrollManagerV2] loadMoreHistory called');
        
        if (this._isLoadingHistory || this._destroyed) {
            console.log('[ScrollManagerV2] ❌ Skipped: already loading or destroyed');
            return [];
        }

        if (!this.loader.hasMoreHistory(this.chatId)) {
            console.log('[ScrollManagerV2] ❌ No more history available');
            return [];
        }

        this._isLoadingHistory = true;

        try {
            // Отключаем smooth scroll для мгновенных изменений
            const originalScrollBehavior = this.scrollEl.style.scrollBehavior;
            this.scrollEl.style.scrollBehavior = 'auto';

            // Сохраняем высоты ДО загрузки
            const oldScrollHeight = this.scrollEl.scrollHeight;
            const oldScrollTop = this.scrollEl.scrollTop;
            const messagesBefore = this.scrollEl.querySelectorAll('.msg[data-message-id]').length;

            console.log('[ScrollManagerV2] BEFORE load:', { 
                oldScrollHeight,
                oldScrollTop,
                messagesBefore
            });

            // Загружаем историю
            const messages = await this.loader.loadHistory(this.chatId);

            console.log('[ScrollManagerV2] AFTER loader.loadHistory:', {
                messagesLoaded: messages.length,
                messageIds: messages.map(m => m.id)
            });

            // Проверяем есть ли еще история ПОСЛЕ загрузки
            const stillHasMore = this.loader.hasMoreHistory(this.chatId);
            
            if (messages.length === 0 || !stillHasMore) {
                console.log('[ScrollManagerV2] ⚠️ Stopping: no messages or no more history', {
                    messagesLength: messages.length,
                    stillHasMore
                });
                this.scrollEl.style.scrollBehavior = originalScrollBehavior;
                return [];
            }

            console.log('[ScrollManagerV2] ✅ History loaded:', messages.length, 'messages');

            // КЛЮЧЕВОЙ МОМЕНТ: НЕ делаем полный render!
            // Создаем fragment с новыми сообщениями
            const fragment = this.renderer.prependMessages(messages, this.chatId);
            
            console.log('[ScrollManagerV2] Fragment created:', {
                hasChildNodes: fragment.hasChildNodes(),
                childCount: fragment.childElementCount
            });
            
            // Если fragment пустой (все сообщения уже отрендерены), выходим
            if (!fragment.hasChildNodes()) {
                console.log('[ScrollManagerV2] ⚠️ All messages already rendered');
                this.scrollEl.style.scrollBehavior = originalScrollBehavior;
                return messages;
            }

            // ВАЖНО: Проверяем и удаляем потенциальные дубликаты divider
            // ПЕРЕД prepend, чтобы избежать визуальных скачков
            const firstFragmentChild = fragment.firstElementChild;
            if (firstFragmentChild && firstFragmentChild.classList.contains('day-divider')) {
                const firstContainerChild = this.scrollEl.firstElementChild;
                if (firstContainerChild && firstContainerChild.classList.contains('day-divider')) {
                    const fragmentDividerText = firstFragmentChild.textContent.trim();
                    const containerDividerText = firstContainerChild.textContent.trim();
                    
                    // Если dividers одинаковые, удаляем из fragment
                    if (fragmentDividerText === containerDividerText) {
                        fragment.removeChild(firstFragmentChild);
                        console.log('[ScrollManagerV2] Removed duplicate divider:', fragmentDividerText);
                    }
                }
            }

            // Prepend fragment в НАЧАЛО контейнера (как в Telegram)
            this.scrollEl.prepend(fragment);

            const messagesAfterPrepend = this.scrollEl.querySelectorAll('.msg[data-message-id]').length;
            console.log('[ScrollManagerV2] AFTER prepend:', {
                messagesAfterPrepend,
                added: messagesAfterPrepend - messagesBefore
            });

            // КЛЮЧЕВОЕ ОТЛИЧИЕ Telegram: ДВОЙНОЙ RAF для стабильности!
            // Первый RAF - браузер обновляет layout
            // Второй RAF - браузер гарантированно применил все изменения
            await new Promise(resolve => {
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        // КЛЮЧЕВОЙ МОМЕНТ: вычисляем разницу в высоте
                        const newScrollHeight = this.scrollEl.scrollHeight;
                        const heightDifference = newScrollHeight - oldScrollHeight;
                        
                        // Корректируем scrollTop на разницу высоты
                        // Это сохраняет визуальную позицию пользователя ТОЧНО там же
                        // БЕЗ КАКИХ-ЛИБО ПРЫЖКОВ!
                        this.scrollEl.scrollTop = oldScrollTop + heightDifference;
                        
                        console.log('[ScrollManagerV2] Scroll restored using height difference:', {
                            oldScrollHeight,
                            newScrollHeight,
                            heightDifference,
                            oldScrollTop,
                            newScrollTop: this.scrollEl.scrollTop
                        });

                        // Обновляем observer на новое первое сообщение
                        this._updateObserverTarget();
                        
                        // Восстанавливаем scroll-behavior
                        this.scrollEl.style.scrollBehavior = originalScrollBehavior;
                        
                        const finalMessages = this.scrollEl.querySelectorAll('.msg[data-message-id]').length;
                        console.log('[ScrollManagerV2] ✅ FINAL STATE:', {
                            finalMessages,
                            totalAdded: finalMessages - messagesBefore
                        });
                        console.log('[ScrollManagerV2] ======================================');
                        
                        resolve();
                    });
                });
            });

            return messages;

        } catch (error) {
            console.error('[ScrollManagerV2] ❌ History load failed:', error);
            console.log('[ScrollManagerV2] ======================================');
            return [];
            
        } finally {
            this._isLoadingHistory = false;
        }
    }

    /**
     * Прокручивает к низу чата
     * @param {Object} [options]
     * @param {boolean} [options.instant=false] - Без анимации
     * @param {boolean} [options.force=false] - Игнорировать позицию пользователя
     */
    scrollToBottom(options = {}) {
        const { instant = false, force = false } = options;

        if (!force && !this.isNearBottom()) {
            return;
        }

        if (instant) {
            // Мгновенный скролл с visibility hiding
            this.scrollEl.style.visibility = 'hidden';
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    this.scrollEl.scrollTop = this.scrollEl.scrollHeight;
                    this.scrollEl.style.visibility = '';
                });
            });
        } else {
            // Плавный скролл
            this.scrollEl.scrollTo({
                top: this.scrollEl.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    /**
     * Прокручивает к конкретному сообщению
     * @param {number|string} messageId - ID сообщения
     * @param {Object} [options]
     * @param {string} [options.block='center'] - Позиция в viewport
     * @param {string} [options.behavior='smooth'] - Тип анимации
     */
    scrollToMessage(messageId, options = {}) {
        const messageEl = this.scrollEl.querySelector(`[data-message-id="${messageId}"]`);
        
        if (!messageEl) {
            console.warn('[ScrollManagerV2] Message not found:', messageId);
            return;
        }

        messageEl.scrollIntoView({
            block: options.block || 'center',
            behavior: options.behavior || 'smooth',
            inline: 'nearest'
        });
    }

    /**
     * Проверяет, находится ли пользователь внизу
     * @param {number} [threshold] - Порог в пикселях
     * @returns {boolean}
     */
    isNearBottom(threshold = null) {
        const th = threshold ?? this.config.BOTTOM_THRESHOLD;
        return (
            this.scrollEl.scrollTop + this.scrollEl.clientHeight >= 
            this.scrollEl.scrollHeight - th
        );
    }

    /**
     * Проверяет, находится ли пользователь вверху
     * @returns {boolean}
     */
    isAtTop() {
        return this.scrollEl.scrollTop <= 10;
    }

    /**
     * Получает текущий статус
     * @returns {Object}
     */
    getStatus() {
        return {
            isNearBottom: this.isNearBottom(),
            isAtTop: this.isAtTop(),
            isLoadingHistory: this._isLoadingHistory,
            scrollPercentage: this._getScrollPercentage(),
            firstVisibleMessageId: this._getFirstVisibleMessageId(),
            lastVisibleMessageId: this._getLastVisibleMessageId()
        };
    }

    // ==================== Приватные методы - Setup ====================

    /**
     * Настраивает IntersectionObserver для автозагрузки истории
     * @private
     */
    _setupIntersectionObserver() {
        // Находим первое сообщение
        const firstMessage = this.scrollEl.querySelector('.msg[data-message-id]');
        
        if (!firstMessage) {
            console.log('[ScrollManagerV2] No messages yet, observer not set');
            return;
        }

        // Создаем observer
        this._historyObserver = new IntersectionObserver(
            (entries) => this._handleIntersection(entries),
            {
                root: this.scrollEl,
                threshold: this.config.OBSERVER_THRESHOLD,
                rootMargin: this.config.OBSERVER_ROOT_MARGIN
            }
        );

        this._historyObserver.observe(firstMessage);
        console.log('[ScrollManagerV2] Observer attached to first message');
    }

    /**
     * Настраивает слушатель скролла
     * @private
     */
    _setupScrollListener() {
        this._boundScrollHandler = throttle((e) => {
            this._onScroll(e);
        }, 100);

        this.scrollEl.addEventListener('scroll', this._boundScrollHandler, { passive: true });
    }

    /**
     * Настраивает слушатель resize
     * @private
     */
    _setupResizeListener() {
        this._boundResizeHandler = debounce(() => {
            this._onResize();
        }, 200);

        window.addEventListener('resize', this._boundResizeHandler);
    }

    // ==================== Приватные методы - Handlers ====================

    /**
     * Обработчик IntersectionObserver
     * @private
     */
    _handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting && !this._isLoadingHistory) {
                this._debouncedLoadHistory();
            }
        });
    }

    /**
     * Обработчик скролла
     * @private
     */
    _onScroll(e) {
        // Здесь можно добавить логику:
        // - Показать/скрыть кнопку "scroll to bottom"
        // - Отслеживание видимых сообщений для mark read
        // - Отправка событий
    }

    /**
     * Обработчик resize
     * @private
     */
    _onResize() {
        // Обновляем observer если нужно
        this._updateObserverTarget();
    }

    /**
     * Триггерит загрузку истории
     * @private
     */
    async _triggerLoadHistory() {
        await this.loadMoreHistory();
    }

    // ==================== Приватные методы - Observer ====================

    /**
     * Обновляет target IntersectionObserver
     * @private
     */
    _updateObserverTarget() {
        if (!this._historyObserver) return;

        this._historyObserver.disconnect();

        const firstMessage = this.scrollEl.querySelector('.msg[data-message-id]');
        if (firstMessage) {
            this._historyObserver.observe(firstMessage);
        }
    }

    // ==================== Приватные методы - Scroll Position ====================

    /**
     * Сохраняет текущую позицию скролла
     * @private
     * @returns {Object}
     */
    _saveScrollPosition() {
        return {
            scrollTop: this.scrollEl.scrollTop,
            scrollHeight: this.scrollEl.scrollHeight,
            clientHeight: this.scrollEl.clientHeight,
            firstVisibleId: this._getFirstVisibleMessageId()
        };
    }

    /**
     * Восстанавливает позицию скролла после добавления контента
     * @private
     * @param {Object} savedPosition
     */
    _restoreScrollPosition(savedPosition) {
        if (!savedPosition) return;

        // Используем двойной RAF для гарантии после layout
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                const heightDelta = this.scrollEl.scrollHeight - savedPosition.scrollHeight;
                this.scrollEl.scrollTop = savedPosition.scrollTop + heightDelta;
            });
        });
    }

    // ==================== Приватные методы - Utilities ====================

    /**
     * Валидирует опции конструктора
     * @private
     */
    _validateOptions(options) {
        if (!options.scrollElement) {
            throw new Error('[ScrollManagerV2] scrollElement is required');
        }
        if (!options.loader) {
            throw new Error('[ScrollManagerV2] loader is required');
        }
        if (!options.renderer) {
            throw new Error('[ScrollManagerV2] renderer is required');
        }
    }

    /**
     * Ждет стабилизации layout
     * @private
     */
    _waitForLayout() {
        return new Promise(resolve => {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    resolve();
                });
            });
        });
    }

    /**
     * Получает процент прокрутки
     * @private
     */
    _getScrollPercentage() {
        const scrollable = this.scrollEl.scrollHeight - this.scrollEl.clientHeight;
        if (scrollable <= 0) return 100;
        return Math.round((this.scrollEl.scrollTop / scrollable) * 100);
    }

    /**
     * Получает ID первого видимого сообщения
     * @private
     */
    _getFirstVisibleMessageId() {
        const containerRect = this.scrollEl.getBoundingClientRect();
        const messages = this.scrollEl.querySelectorAll('.msg[data-message-id]');

        for (const msg of messages) {
            const rect = msg.getBoundingClientRect();
            if (rect.top >= containerRect.top && rect.top <= containerRect.bottom) {
                return msg.dataset.messageId;
            }
        }
        return null;
    }

    /**
     * Получает ID последнего видимого сообщения
     * @private
     */
    _getLastVisibleMessageId() {
        const containerRect = this.scrollEl.getBoundingClientRect();
        const messages = Array.from(this.scrollEl.querySelectorAll('.msg[data-message-id]'));

        for (let i = messages.length - 1; i >= 0; i--) {
            const rect = messages[i].getBoundingClientRect();
            if (rect.bottom >= containerRect.top && rect.bottom <= containerRect.bottom) {
                return messages[i].dataset.messageId;
            }
        }
        return null;
    }
}

export default ScrollManagerV2;

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
        this._newerObserver = null;  // ✅ Observer для новых сообщений (как в Telegram)
        this._isLoadingHistory = false;
        this._isLoadingNewer = false;  // ✅ Флаг загрузки новых
        this._destroyed = false;
        this._isInitializing = true; // ✅ Флаг инициализации

        // Bound handlers для cleanup
        this._boundScrollHandler = null;
        this._boundResizeHandler = null;

        // Debounced/throttled функции
        this._debouncedLoadHistory = debounce(
            () => this._triggerLoadHistory(),
            LOADER_CONFIG.HISTORY_DEBOUNCE
        );
        
        // ✅ Debounced функция для загрузки новых сообщений
        this._debouncedLoadNewer = debounce(
            () => this._triggerLoadNewer(),
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
        console.log('[ScrollManagerV2] 🔵 INIT STARTED');
        console.log('[ScrollManagerV2] Initial scroll state:', {
            scrollTop: this.scrollEl.scrollTop,
            scrollHeight: this.scrollEl.scrollHeight,
            clientHeight: this.scrollEl.clientHeight,
            isNearBottom: this.isNearBottom(),
            messagesCount: this.scrollEl.querySelectorAll('.msg').length
        });
        
        // Ждем стабилизации DOM
        await this._waitForLayout();
        
        console.log('[ScrollManagerV2] After layout wait:', {
            scrollTop: this.scrollEl.scrollTop,
            scrollHeight: this.scrollEl.scrollHeight
        });
        
        this._setupIntersectionObserver();
        this._setupScrollListener();
        this._setupResizeListener();
        
        // Снимаем флаг инициализации после небольшой задержки
        // чтобы Observer не сработал сразу
        setTimeout(() => {
            this._isInitializing = false;
            console.log('[ScrollManagerV2] ✅ Initialization flag cleared');
        }, 500);
        
        console.log('[ScrollManagerV2] 🟢 INIT COMPLETE');
    }

    /**
     * Уничтожает ScrollManager
     */
    destroy() {
        if (this._destroyed) return;
        
        this._destroyed = true;

        // Отключаем observers
        if (this._historyObserver) {
            this._historyObserver.disconnect();
            this._historyObserver = null;
        }
        
        // ✅ Отключаем observer для новых сообщений
        if (this._newerObserver) {
            this._newerObserver.disconnect();
            this._newerObserver = null;
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
                        // ✅ ФИЗИКА: НЕ АВТОСКРОЛЛ! Компенсация роста scrollHeight вверх
                        // При prepend сообщений scrollHeight растет ВВЕРХ
                        // Без коррекции: scrollTop фиксирован → визуальный ПРЫЖОК вверх
                        // С коррекцией: scrollTop += heightDiff → пользователь видит ТЕ ЖЕ сообщения
                        const newScrollHeight = this.scrollEl.scrollHeight;
                        const heightDifference = newScrollHeight - oldScrollHeight;
                        
                        // КРИТИЧНО: Без этой строки - бесконечная загрузка истории!
                        // Первое сообщение остается в viewport → observer снова его видит
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
     * Загружает более новые сообщения (при прокрутке вниз после перехода по дате)
     * Как в Telegram: при переходе к старой дате и прокрутке вниз подгружаем новые сообщения
     * @returns {Promise<Array>}
     */
    async loadMoreNewer() {
        console.log('[ScrollManagerV2] ======================================');
        console.log('[ScrollManagerV2] loadMoreNewer called');
        
        if (this._isLoadingNewer || this._destroyed) {
            console.log('[ScrollManagerV2] ❌ Skipped: already loading newer or destroyed');
            return [];
        }

        if (!this.loader.hasMoreAfter(this.chatId)) {
            console.log('[ScrollManagerV2] ❌ No more newer messages available');
            return [];
        }

        this._isLoadingNewer = true;

        try {
            const messagesBefore = this.scrollEl.querySelectorAll('.msg[data-message-id]').length;
            
            console.log('[ScrollManagerV2] BEFORE loadNewer:', { 
                messagesBefore,
                scrollTop: this.scrollEl.scrollTop,
                scrollHeight: this.scrollEl.scrollHeight
            });

            // Загружаем новые сообщения через loader
            const messages = await this.loader.loadNewer(this.chatId);

            console.log('[ScrollManagerV2] AFTER loader.loadNewer:', {
                messagesLoaded: messages.length,
                messageIds: messages.map(m => m.id)
            });

            if (messages.length === 0) {
                console.log('[ScrollManagerV2] ⚠️ No new messages loaded');
                return [];
            }

            // Проверяем какие сообщения реально новые
            const existingIds = new Set(
                Array.from(this.scrollEl.querySelectorAll('.msg[data-message-id]'))
                    .map(el => el.dataset.messageId)
            );
            const newMessages = messages.filter(m => !existingIds.has(String(m.id)));

            if (newMessages.length === 0) {
                console.log('[ScrollManagerV2] ⚠️ All messages already rendered');
                // Обновляем observer даже если сообщения уже отрендерены
                // Это важно когда loadAround загрузил меньше сообщений чем есть в чате
                this._updateNewerObserverTarget();
                return messages;
            }

            console.log('[ScrollManagerV2] ✅ Newer messages loaded:', newMessages.length);

            // Рендерим новые сообщения в КОНЕЦ контейнера
            const fragment = this.renderer.appendMessages(newMessages, this.chatId);
            
            if (fragment && fragment.hasChildNodes()) {
                this.scrollEl.appendChild(fragment);
                
                // Обновляем observer на новое последнее сообщение
                this._updateNewerObserverTarget();
                
                const messagesAfter = this.scrollEl.querySelectorAll('.msg[data-message-id]').length;
                console.log('[ScrollManagerV2] ✅ NEWER FINAL STATE:', {
                    messagesAfter,
                    totalAdded: messagesAfter - messagesBefore
                });
            } else {
                // Даже если fragment пустой, обновляем observer
                this._updateNewerObserverTarget();
            }

            console.log('[ScrollManagerV2] ======================================');
            return newMessages;

        } catch (error) {
            console.error('[ScrollManagerV2] ❌ Newer load failed:', error);
            console.log('[ScrollManagerV2] ======================================');
            return [];
            
        } finally {
            this._isLoadingNewer = false;
        }
    }

    /**
     * Прокручивает к низу чата
     * @param {Object} [options]
     * @param {boolean} [options.instant=false] - Без анимации
     * @param {boolean} [options.force=false] - Игнорировать позицию пользователя
     */
    scrollToBottom(options = {}) {
        // 🚫 REMOVED: Автоскролл не нужен!
        // IntersectionObserver + физика prepend = естественное поведение
        // Пользователь сам управляет своей позицией скролла
        console.log('[ScrollManagerV2] scrollToBottom() removed - user controls scroll');
    }

    /**
     * Прокручивает к конкретному сообщению
     * @param {number|string} messageId - ID сообщения
     * @param {Object} [options]
     * @param {string} [options.block='center'] - Позиция в viewport
     * @param {string} [options.behavior='auto'] - Тип анимации ('auto', 'smooth', 'instant')
     */
    scrollToMessage(messageId, options = {}) {
        // 🚫 REMOVED: Автоскролл к сообщению не нужен!
        // loadAround загрузит сообщения, пользователь увидит контекст
        // Принудительный скролл мешает навигации
        console.log('[ScrollManagerV2] scrollToMessage() removed - showing context only');
    }

    /**
     * Приостанавливает обработку scroll событий на указанное время
     * @param {number} duration - Длительность паузы в миллисекундах
     */
    pauseScrollEvents(duration = 1000) {
        console.log('[ScrollManagerV2] ⏸️ Pausing scroll events for', duration, 'ms');
        
        // Сохраняем оригинальный debounced handler
        const originalHandler = this._debouncedLoadHistory;
        
        // Заменяем на no-op функцию
        this._debouncedLoadHistory = () => {
            console.log('[ScrollManagerV2] 🚫 Scroll events paused, ignoring history load');
        };
        
        // Восстанавливаем оригинальный handler через указанное время
        setTimeout(() => {
            this._debouncedLoadHistory = originalHandler;
            console.log('[ScrollManagerV2] ▶️ Scroll events resumed');
        }, duration);
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
        console.log('[ScrollManagerV2] 🔍 _setupIntersectionObserver called');
        
        // Находим первое сообщение
        const firstMessage = this.scrollEl.querySelector('.msg[data-message-id]');
        
        if (!firstMessage) {
            console.log('[ScrollManagerV2] ❌ No messages yet, observer not set');
            return;
        }

        console.log('[ScrollManagerV2] First message found:', {
            messageId: firstMessage.dataset.messageId,
            offsetTop: firstMessage.offsetTop,
            scrollTop: this.scrollEl.scrollTop,
            firstMessageVisible: firstMessage.getBoundingClientRect().top < this.scrollEl.clientHeight
        });

        // Создаем observer
        this._historyObserver = new IntersectionObserver(
            (entries) => this._handleHistoryIntersection(entries),
            {
                root: this.scrollEl,
                threshold: this.config.OBSERVER_THRESHOLD,
                rootMargin: this.config.OBSERVER_ROOT_MARGIN
            }
        );

        this._historyObserver.observe(firstMessage);
        console.log('[ScrollManagerV2] ✅ Observer attached to first message');
        
        // ✅ Настраиваем observer для новых сообщений (последнее сообщение)
        this._setupNewerObserver();
    }

    /**
     * Настраивает IntersectionObserver для автозагрузки НОВЫХ сообщений
     * Как в Telegram: при прокрутке вниз после перехода по дате
     * @private
     */
    _setupNewerObserver() {
        console.log('[ScrollManagerV2] 🔍 _setupNewerObserver called');
        
        const messages = this.scrollEl.querySelectorAll('.msg[data-message-id]');
        const lastMessage = messages[messages.length - 1];
        
        if (!lastMessage) {
            console.log('[ScrollManagerV2] ❌ No last message for newer observer');
            return;
        }

        // Проверяем есть ли ещё новые сообщения для загрузки
        if (!this.loader.hasMoreAfter(this.chatId)) {
            console.log('[ScrollManagerV2] ❌ No more newer messages, skipping observer');
            return;
        }

        console.log('[ScrollManagerV2] Last message found:', {
            messageId: lastMessage.dataset.messageId
        });

        // Создаем observer для последнего сообщения
        this._newerObserver = new IntersectionObserver(
            (entries) => this._handleNewerIntersection(entries),
            {
                root: this.scrollEl,
                threshold: this.config.OBSERVER_THRESHOLD,
                rootMargin: '0px 0px 200px 0px'  // Триггер при приближении к низу
            }
        );

        this._newerObserver.observe(lastMessage);
        console.log('[ScrollManagerV2] ✅ Newer observer attached to last message');
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
     * Обработчик IntersectionObserver для ИСТОРИИ (старые сообщения)
     * @private
     */
    _handleHistoryIntersection(entries) {
        console.log('[ScrollManagerV2] 👁️ History IntersectionObserver triggered:', {
            entriesCount: entries.length,
            scrollTop: this.scrollEl.scrollTop,
            scrollHeight: this.scrollEl.scrollHeight,
            isNearBottom: this.isNearBottom(),
            isInitializing: this._isInitializing
        });
        
        entries.forEach(entry => {
            console.log('[ScrollManagerV2] History Entry:', {
                target: entry.target.dataset?.messageId,
                isIntersecting: entry.isIntersecting,
                intersectionRatio: entry.intersectionRatio,
                isLoadingHistory: this._isLoadingHistory,
                isNearBottom: this.isNearBottom(),
                isInitializing: this._isInitializing,
                willLoadHistory: entry.isIntersecting && !this._isLoadingHistory && !this.isNearBottom() && !this._isInitializing
            });
            
            // ✅ ВАЖНО: Игнорируем события во время инициализации
            if (this._isInitializing) {
                console.log('[ScrollManagerV2] 🚫 Initializing, ignoring observer event');
                return;
            }
            
            // ✅ НЕ загружаем историю если пользователь внизу
            if (entry.isIntersecting && !this._isLoadingHistory && !this.isNearBottom()) {
                console.log('[ScrollManagerV2] 🚀 Triggering debounced history load...');
                this._debouncedLoadHistory();
            } else if (entry.isIntersecting && this.isNearBottom()) {
                console.log('[ScrollManagerV2] 🚫 User at bottom, skipping history load (false positive)');
            } else if (entry.isIntersecting && this._isLoadingHistory) {
                console.log('[ScrollManagerV2] ⏸️ Already loading history, skipping');
            }
        });
    }

    /**
     * Обработчик IntersectionObserver для НОВЫХ сообщений
     * Как в Telegram: при прокрутке вниз после перехода к старой дате
     * @private
     */
    _handleNewerIntersection(entries) {
        console.log('[ScrollManagerV2] 👁️ Newer IntersectionObserver triggered:', {
            entriesCount: entries.length,
            scrollTop: this.scrollEl.scrollTop,
            isInitializing: this._isInitializing
        });
        
        entries.forEach(entry => {
            console.log('[ScrollManagerV2] Newer Entry:', {
                target: entry.target.dataset?.messageId,
                isIntersecting: entry.isIntersecting,
                isLoadingNewer: this._isLoadingNewer,
                willLoadNewer: entry.isIntersecting && !this._isLoadingNewer && !this._isInitializing
            });
            
            // Игнорируем во время инициализации
            if (this._isInitializing) {
                console.log('[ScrollManagerV2] 🚫 Initializing, ignoring newer observer event');
                return;
            }
            
            // Загружаем новые сообщения при видимости последнего
            if (entry.isIntersecting && !this._isLoadingNewer) {
                console.log('[ScrollManagerV2] 🚀 Triggering debounced newer load...');
                this._debouncedLoadNewer();
            } else if (entry.isIntersecting && this._isLoadingNewer) {
                console.log('[ScrollManagerV2] ⏸️ Already loading newer, skipping');
            }
        });
    }

    /**
     * Триггер загрузки истории
     * @private
     */
    _triggerLoadHistory() {
        console.log('[ScrollManagerV2] 🎬 _triggerLoadHistory called (from debounced)');
        this.loadMoreHistory();
    }

    /**
     * Триггер загрузки новых сообщений
     * @private
     */
    _triggerLoadNewer() {
        console.log('[ScrollManagerV2] 🎬 _triggerLoadNewer called (from debounced)');
        this.loadMoreNewer();
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
     * Обновляет target IntersectionObserver для истории
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

    /**
     * Обновляет target IntersectionObserver для новых сообщений
     * @private
     */
    _updateNewerObserverTarget() {
        // Отключаем старый observer
        if (this._newerObserver) {
            this._newerObserver.disconnect();
        }

        // Проверяем есть ли ещё новые сообщения
        if (!this.loader.hasMoreAfter(this.chatId)) {
            console.log('[ScrollManagerV2] No more newer messages, removing observer');
            this._newerObserver = null;
            return;
        }

        // Находим последнее сообщение
        const messages = this.scrollEl.querySelectorAll('.msg[data-message-id]');
        const lastMessage = messages[messages.length - 1];
        
        if (lastMessage) {
            if (!this._newerObserver) {
                // Создаем новый observer если нужно
                this._newerObserver = new IntersectionObserver(
                    (entries) => this._handleNewerIntersection(entries),
                    {
                        root: this.scrollEl,
                        threshold: this.config.OBSERVER_THRESHOLD,
                        rootMargin: '0px 0px 200px 0px'
                    }
                );
            }
            this._newerObserver.observe(lastMessage);
            console.log('[ScrollManagerV2] ✅ Newer observer updated to last message:', lastMessage.dataset.messageId);
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

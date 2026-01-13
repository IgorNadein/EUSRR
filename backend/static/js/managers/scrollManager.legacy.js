/**
 * ⚠️ DEPRECATED - LEGACY CODE ⚠️
 * Используйте scrollManagerV2.js вместо этого файла
 * Этот файл сохранен только для справки
 * 
 * @fileoverview ScrollManager - централизованное управление прокруткой
 * @module managers/scrollManager
 * 
 * Отвечает за ВСЮ логику скролла в чате:
 * - Автоматическая загрузка истории при scroll up
 * - Умный scroll to bottom без прыжков
 * - Определение "внизу ли пользователь"
 * - Сохранение позиции при загрузке истории
 */

/**
 * ScrollManager - управление прокруткой чата
 */
export class ScrollManager {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {HTMLElement} options.scrollElement - Контейнер для скролла
     * @param {MessageLoader} options.messageLoader - Загрузчик сообщений
     * @param {MessageRenderer} options.messageRenderer - Рендерер сообщений
     * @param {MessageStore} options.messageStore - Store сообщений
     * @param {number} options.chatId - ID текущего чата
     */
    constructor(options) {
        if (!options.scrollElement) {
            throw new Error('[ScrollManager] scrollElement is required');
        }
        if (!options.messageLoader) {
            throw new Error('[ScrollManager] messageLoader is required');
        }
        if (!options.messageRenderer) {
            throw new Error('[ScrollManager] messageRenderer is required');
        }

        this.scrollEl = options.scrollElement;
        this.loader = options.messageLoader;
        this.renderer = options.messageRenderer;
        this.store = options.messageStore;
        this.chatId = options.chatId;

        /** @type {IntersectionObserver|null} */
        this.historyObserver = null;

        /** @type {boolean} */
        this.isLoadingHistory = false;

        /** @type {number} Порог в пикселях для определения "внизу" */
        this.bottomThreshold = 100;

        console.log('[ScrollManager] Initialized for chat:', this.chatId);
    }

    // ==================== Инициализация ====================

    /**
     * Инициализирует ScrollManager
     */
    async init() {
        // Даём время на завершение рендера всех сообщений
        await new Promise(resolve => setTimeout(resolve, 100));
        
        this.setupIntersectionObserver();
        this.setupScrollListener();
        console.log('[ScrollManager] Initialized');
    }

    /**
     * Останавливает ScrollManager и очищает ресурсы
     */
    destroy() {
        if (this.historyObserver) {
            this.historyObserver.disconnect();
            this.historyObserver = null;
        }
        console.log('[ScrollManager] Destroyed');
    }

    // ==================== IntersectionObserver для автозагрузки ====================

    /**
     * Настраивает IntersectionObserver для автоматической загрузки истории
     */
    setupIntersectionObserver() {
        console.log('[ScrollManager] ========================================');
        console.log('[ScrollManager] setupIntersectionObserver called');
        
        // Отключаем старый observer если есть
        if (this.historyObserver) {
            console.log('[ScrollManager] Disconnecting old observer');
            this.historyObserver.disconnect();
            this.historyObserver = null;
        }

        // Находим первое сообщение (просто .msg - найдет первый с этим классом)
        const firstMessage = this.scrollEl.querySelector('.msg');
        
        console.log('[ScrollManager] First message element:', !!firstMessage);
        console.log('[ScrollManager] Total messages in DOM:', this.scrollEl.querySelectorAll('.msg').length);
        
        // Логируем реальные классы первых 3 элементов в контейнере
        const allChildren = this.scrollEl.children;
        console.log('[ScrollManager] First 3 elements in container:');
        for (let i = 0; i < Math.min(3, allChildren.length); i++) {
            const el = allChildren[i];
            console.log(`  [${i}]:`, {
                tag: el.tagName,
                classes: el.className,
                messageId: el.dataset?.messageId
            });
        }
        
        if (!firstMessage) {
            console.warn('[ScrollManager] ❌ No messages yet, observer NOT set');
            console.log('[ScrollManager] ========================================');
            return;
        }

        console.log('[ScrollManager] First message ID:', firstMessage.dataset?.messageId);

        // Создаем observer
        this.historyObserver = new IntersectionObserver(
            entries => {
                entries.forEach(entry => {
                    console.log('[ScrollManager] IntersectionObserver triggered:', {
                        isIntersecting: entry.isIntersecting,
                        isLoadingHistory: this.isLoadingHistory,
                        target: entry.target.dataset?.messageId
                    });
                    
                    if (entry.isIntersecting && !this.isLoadingHistory) {
                        console.log('[ScrollManager] ✅ First message visible, loading history...');
                        this.loadMoreHistory();
                    }
                });
            },
            {
                root: this.scrollEl,
                threshold: 0.1,
                rootMargin: '300px 0px 0px 0px' // Telegram-стиль: загружаем намного раньше
            }
        );

        this.historyObserver.observe(firstMessage);
        console.log('[ScrollManager] ✅ IntersectionObserver attached to first message');
        console.log('[ScrollManager] ========================================');
    }

    /**
     * Обновляет observer на новое первое сообщение
     */
    updateObserverTarget() {
        console.log('[ScrollManager] ========================================');
        console.log('[ScrollManager] updateObserverTarget called');
        
        if (!this.historyObserver) {
            console.warn('[ScrollManager] No observer exists');
            console.log('[ScrollManager] ========================================');
            return;
        }

        // Отключаем от всех
        this.historyObserver.disconnect();

        // Находим РЕАЛЬНОЕ первое сообщение с data-message-id
        // Важно: после добавления истории в начало, ПЕРВОЕ сообщение в DOM - это самое старое
        const firstMessage = this.scrollEl.querySelector('.msg[data-message-id]');
        
        console.log('[ScrollManager] Found first message:', !!firstMessage);
        if (firstMessage) {
            console.log('[ScrollManager] First message ID:', firstMessage.dataset.messageId);
            this.historyObserver.observe(firstMessage);
            console.log('[ScrollManager] ✅ Observer updated to new first message');
        } else {
            console.warn('[ScrollManager] ❌ No first message found in DOM');
        }
        console.log('[ScrollManager] ========================================');
    }

    // ==================== Загрузка истории ====================

    /**
     * Загружает больше истории при scroll up
     */
    async loadMoreHistory() {
        console.log('[ScrollManager] ========================================');
        console.log('[ScrollManager] loadMoreHistory called');
        console.log('[ScrollManager] isLoadingHistory:', this.isLoadingHistory);
        
        if (this.isLoadingHistory) {
            console.log('[ScrollManager] ❌ Already loading history');
            console.log('[ScrollManager] ========================================');
            return;
        }

        const hasMore = this.loader.hasMoreHistory(this.chatId);
        console.log('[ScrollManager] hasMoreHistory:', hasMore);
        
        if (!hasMore) {
            console.log('[ScrollManager] ❌ No more history available');
            console.log('[ScrollManager] ========================================');
            return;
        }

        try {
            this.isLoadingHistory = true;

            // ============================================
            // ПРАВИЛЬНЫЙ подход из Telegram Web:
            // 1. Сохраняем scrollHeight и scrollTop ДО добавления элементов
            // 2. Prepend элементы в начало (НЕ полный re-render!)
            // 3. Вычисляем разницу scrollHeight
            // 4. Корректируем scrollTop на эту разницу
            // ============================================

            // Отключаем smooth scroll чтобы изменения были мгновенными
            const originalScrollBehavior = this.scrollEl.style.scrollBehavior;
            this.scrollEl.style.scrollBehavior = 'auto';

            const oldScrollHeight = this.scrollEl.scrollHeight;
            const oldScrollTop = this.scrollEl.scrollTop;

            console.log('[ScrollManager] ✅ Loading history...', { 
                oldScrollHeight,
                oldScrollTop
            });

            // Загружаем историю через Loader (возвращает уже загруженные сообщения)
            const messages = await this.loader.loadHistoryBefore(this.chatId);

            // Проверяем есть ли еще история ПОСЛЕ загрузки
            const stillHasMore = this.loader.hasMoreHistory(this.chatId);
            
            if (messages.length === 0 || !stillHasMore) {
                console.log('[ScrollManager] ⚠️ No more unique history to load');
                console.log('[ScrollManager] ========================================');
                this.isLoadingHistory = false;
                return;
            }

            console.log('[ScrollManager] ✅ History loaded:', messages.length, 'messages');

            // КЛЮЧЕВОЙ МОМЕНТ: НЕ делаем полный render!
            // Создаем fragment с новыми сообщениями
            const fragment = this.renderer.prependMessages(messages, this.chatId);
            
            // Если fragment пустой (все сообщения уже отрендерены), выходим
            if (!fragment.hasChildNodes()) {
                console.log('[ScrollManager] ⚠️ All messages already rendered');
                this.scrollEl.style.scrollBehavior = originalScrollBehavior;
                this.isLoadingHistory = false;
                return;
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
                        console.log('[ScrollManager] Removed duplicate divider before prepend:', fragmentDividerText);
                    }
                }
            }

            // Prepend fragment в НАЧАЛО контейнера (как в Telegram)
            this.scrollEl.prepend(fragment);

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
                        
                        console.log('[ScrollManager] Scroll restored using height difference:', {
                            oldScrollHeight,
                            newScrollHeight,
                            heightDifference,
                            oldScrollTop,
                            newScrollTop: this.scrollEl.scrollTop
                        });

                        // Обновляем observer на новое первое сообщение
                        this.updateObserverTarget();
                        
                        // Восстанавливаем scroll-behavior
                        this.scrollEl.style.scrollBehavior = originalScrollBehavior;
                        
                        resolve();
                    });
                });
            });

        } catch (error) {
            console.error('[ScrollManager] Failed to load history:', error);
        } finally {
            this.isLoadingHistory = false;
        }
    }

    // ==================== Scroll управление ====================

    /**
     * Настраивает слушатель скролла (для будущих фич)
     */
    setupScrollListener() {
        this.scrollEl.addEventListener('scroll', () => {
            // Здесь можно добавить логику, например:
            // - Показать/скрыть кнопку "scroll to bottom"
            // - Отметка сообщений как прочитанных
            // - etc.
        }, { passive: true });
    }

    /**
     * Прокручивает чат в самый низ
     * @param {Object} options - Опции
     * @param {boolean} [options.instant=false] - Мгновенная прокрутка без анимации
     * @param {boolean} [options.force=false] - Прокрутить даже если пользователь не внизу
     */
    scrollToBottom(options = {}) {
        const { instant = false, force = false } = options;

        // Не скроллим если загружается история (кроме force)
        if (!force && this.isLoadingHistory) {
            console.log('[ScrollManager] History is loading, not scrolling to bottom');
            return;
        }

        // Не скроллим если пользователь читает историю (кроме force)
        if (!force && !this.isNearBottom()) {
            console.log('[ScrollManager] User is reading history, not scrolling');
            return;
        }

        console.log('[ScrollManager] Scrolling to bottom:', { instant, force });

        if (instant) {
            // Мгновенная прокрутка - используем visibility hiding
            this.scrollEl.style.visibility = 'hidden';
            
            // Двойной RAF для гарантии после layout
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    this.scrollEl.scrollTop = this.scrollEl.scrollHeight;
                    this.scrollEl.style.visibility = '';
                    console.log('[ScrollManager] Instant scroll complete');
                });
            });
        } else {
            // Плавная прокрутка
            requestAnimationFrame(() => {
                this.scrollEl.scrollTop = this.scrollEl.scrollHeight;
                console.log('[ScrollManager] Smooth scroll complete');
            });
        }
    }

    /**
     * Прокручивает к конкретному сообщению
     * @param {number|string} messageId - ID сообщения
     * @param {Object} options - Опции
     * @param {string} [options.block='center'] - Положение ('start', 'center', 'end', 'nearest')
     * @param {string} [options.behavior='smooth'] - Поведение ('auto', 'smooth')
     */
    scrollToMessage(messageId, options = {}) {
        const messageEl = this.scrollEl.querySelector(`[data-message-id="${messageId}"]`);
        
        if (!messageEl) {
            console.warn('[ScrollManager] Message not found:', messageId);
            return;
        }

        messageEl.scrollIntoView({
            block: options.block || 'center',
            behavior: options.behavior || 'smooth'
        });

        console.log('[ScrollManager] Scrolled to message:', messageId);
    }

    // ==================== Утилиты ====================

    /**
     * Проверяет находится ли пользователь близко к низу
     * @param {number} [threshold] - Порог в пикселях (по умолчанию this.bottomThreshold)
     * @returns {boolean}
     */
    isNearBottom(threshold = null) {
        const th = threshold !== null ? threshold : this.bottomThreshold;
        const isNear = (
            this.scrollEl.scrollTop + this.scrollEl.clientHeight >=
            this.scrollEl.scrollHeight - th
        );
        return isNear;
    }

    /**
     * Проверяет находится ли пользователь в самом верху
     * @returns {boolean}
     */
    isAtTop() {
        return this.scrollEl.scrollTop <= 10;
    }

    /**
     * Получает текущую позицию скролла в процентах
     * @returns {number} От 0 до 100
     */
    getScrollPercentage() {
        const scrollable = this.scrollEl.scrollHeight - this.scrollEl.clientHeight;
        if (scrollable <= 0) return 100;
        
        return (this.scrollEl.scrollTop / scrollable) * 100;
    }

    /**
     * Сохраняет текущую позицию скролла
     * @returns {Object} Сохраненное состояние
     */
    saveScrollPosition() {
        return {
            scrollTop: this.scrollEl.scrollTop,
            scrollHeight: this.scrollEl.scrollHeight,
            clientHeight: this.scrollEl.clientHeight
        };
    }

    /**
     * Восстанавливает позицию скролла
     * @param {Object} savedPosition - Сохраненное состояние
     */
    restoreScrollPosition(savedPosition) {
        if (!savedPosition) return;

        const delta = this.scrollEl.scrollHeight - savedPosition.scrollHeight;
        this.scrollEl.scrollTop = savedPosition.scrollTop + delta;

        console.log('[ScrollManager] Position restored:', {
            delta,
            newScrollTop: this.scrollEl.scrollTop
        });
    }

    /**
     * Получает первое видимое сообщение (элемент DOM)
     * @private
     * @returns {HTMLElement|null}
     */
    _getFirstVisibleMessage() {
        const messages = this.scrollEl.querySelectorAll('.msg[data-message-id]');
        const containerRect = this.scrollEl.getBoundingClientRect();
        
        for (const msg of messages) {
            const rect = msg.getBoundingClientRect();
            if (rect.top >= containerRect.top && rect.top <= containerRect.bottom) {
                return msg;
            }
        }
        
        return messages[0] || null; // Если не нашли видимое, берем первое
    }

    /**
     * Получает ID первого видимого сообщения
     * @returns {number|string|null}
     */
    getFirstVisibleMessageId() {
        const msg = this._getFirstVisibleMessage();
        return msg ? msg.dataset.messageId : null;
    }

    /**
     * Получает ID последнего видимого сообщения
     * @returns {number|string|null}
     */
    getLastVisibleMessageId() {
        const messages = Array.from(this.scrollEl.querySelectorAll('.msg[data-message-id]'));
        
        for (let i = messages.length - 1; i >= 0; i--) {
            const msg = messages[i];
            const rect = msg.getBoundingClientRect();
            const containerRect = this.scrollEl.getBoundingClientRect();
            
            if (rect.bottom >= containerRect.top && rect.bottom <= containerRect.bottom) {
                return msg.dataset.messageId;
            }
        }
        
        return null;
    }

    /**
     * Получает статус ScrollManager
     * @returns {Object}
     */
    getStatus() {
        return {
            isNearBottom: this.isNearBottom(),
            isAtTop: this.isAtTop(),
            scrollPercentage: this.getScrollPercentage(),
            isLoadingHistory: this.isLoadingHistory,
            firstVisibleMessage: this.getFirstVisibleMessageId(),
            lastVisibleMessage: this.getLastVisibleMessageId()
        };
    }
}

export default ScrollManager;

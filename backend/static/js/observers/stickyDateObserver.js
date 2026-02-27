/**
 * StickyDateObserver - IntersectionObserver для отслеживания sticky состояния дат
 * 
 * Основано на Telegram Web (StickyIntersector):
 * - Отслеживает когда date header "прилипает" к верху
 * - Добавляет/удаляет класс .is-sticky
 * - Управляет видимостью оригинальной даты
 * 
 * @module observers/stickyDateObserver
 */

/**
 * Observer для отслеживания sticky состояния date headers
 */
export class StickyDateObserver {
    /**
     * @param {Object} options - Опции конфигурации
     * @param {HTMLElement} options.container - Scroll контейнер для наблюдения
     * @param {Function} [options.onSticky] - Callback при изменении sticky состояния
     */
    constructor(options = {}) {
        this.container = options.container;
        this.onSticky = options.onSticky || null;
        
        // IntersectionObserver для отслеживания
        this.observer = null;
        
        // Set наблюдаемых элементов
        this.observedDates = new Set();
        
        console.log('[StickyDateObserver] Initialized');
    }

    /**
     * Инициализирует IntersectionObserver
     * 
     * @example
     * observer.init();
     */
    init() {
        if (this.observer) {
            console.warn('[StickyDateObserver] Already initialized');
            return;
        }

        // Создаем observer с нужными настройками
        this.observer = new IntersectionObserver(
            (entries) => this._handleIntersection(entries),
            {
                root: this.container,
                threshold: [0, 1], // Отслеживаем полное и частичное пересечение
                rootMargin: '-56px 0px 0px 0px' // Offset на высоту header
            }
        );

        console.log('[StickyDateObserver] IntersectionObserver created');

        // Наблюдаем за всеми существующими date headers
        this.observeAll();
    }

    /**
     * Обработчик IntersectionObserver
     * @private
     */
    _handleIntersection(entries) {
        for (const entry of entries) {
            const stickyDate = entry.target.parentElement;
            
            if (!stickyDate || !stickyDate.classList.contains('sticky-date')) {
                continue;
            }

            const targetInfo = entry.boundingClientRect;
            const rootBoundsInfo = entry.rootBounds;

            if (!rootBoundsInfo) continue;

            // Определяем sticky состояние
            // Элемент "прилип" если его верх выше root bounds top
            const isSticky = targetInfo.bottom < rootBoundsInfo.top;
            
            // Обновляем класс
            if (isSticky) {
                if (!stickyDate.classList.contains('is-sticky')) {
                    stickyDate.classList.add('is-sticky');
                    this._notifySticky(stickyDate, true);
                }
            } else {
                if (stickyDate.classList.contains('is-sticky')) {
                    stickyDate.classList.remove('is-sticky');
                    this._notifySticky(stickyDate, false);
                }
            }
        }
    }

    /**
     * Уведомляет о изменении sticky состояния
     * @private
     */
    _notifySticky(stickyDate, isSticky) {
        const dateText = stickyDate.getAttribute('data-date-text') || 
                        stickyDate.querySelector('span')?.textContent;

        console.log('[StickyDateObserver] Sticky state changed:', {
            date: dateText,
            isSticky
        });

        if (this.onSticky) {
            this.onSticky(isSticky, stickyDate, dateText);
        }
    }

    /**
     * Начинает наблюдение за всеми date headers в контейнере
     * 
     * @example
     * observer.observeAll();
     */
    observeAll() {
        if (!this.observer) {
            console.warn('[StickyDateObserver] Observer not initialized');
            return;
        }

        const stickyDates = this.container.querySelectorAll('.sticky-date');
        
        for (const stickyDate of stickyDates) {
            // Для IntersectionObserver нам нужен элемент-"сентинель"
            // Telegram Web использует вложенный div, мы будем наблюдать за span
            const sentinel = stickyDate.querySelector('span');
            
            if (sentinel && !this.observedDates.has(sentinel)) {
                this.observer.observe(sentinel);
                this.observedDates.add(sentinel);
            }
        }

        console.log('[StickyDateObserver] Observing dates:', this.observedDates.size);
    }

    /**
     * Начинает наблюдение за конкретным date header
     * 
     * @param {HTMLElement} stickyDateEl - Элемент .sticky-date
     * 
     * @example
     * const dateGroup = document.querySelector('.message-date-group');
     * const stickyDate = dateGroup.querySelector('.sticky-date');
     * observer.observe(stickyDate);
     */
    observe(stickyDateEl) {
        if (!this.observer) {
            console.warn('[StickyDateObserver] Observer not initialized');
            return;
        }

        const sentinel = stickyDateEl.querySelector('span');
        
        if (sentinel && !this.observedDates.has(sentinel)) {
            this.observer.observe(sentinel);
            this.observedDates.add(sentinel);
            console.log('[StickyDateObserver] Started observing date');
        }
    }

    /**
     * Прекращает наблюдение за конкретным date header
     * 
     * @param {HTMLElement} stickyDateEl - Элемент .sticky-date
     * 
     * @example
     * observer.unobserve(stickyDate);
     */
    unobserve(stickyDateEl) {
        if (!this.observer) return;

        const sentinel = stickyDateEl.querySelector('span');
        
        if (sentinel && this.observedDates.has(sentinel)) {
            this.observer.unobserve(sentinel);
            this.observedDates.delete(sentinel);
            
            // Удаляем sticky класс
            stickyDateEl.classList.remove('is-sticky');
            
            console.log('[StickyDateObserver] Stopped observing date');
        }
    }

    /**
     * Обновляет список наблюдаемых элементов
     * Полезно после добавления/удаления date groups
     * 
     * @example
     * // После загрузки новых сообщений
     * observer.refresh();
     */
    refresh() {
        if (!this.observer) return;

        // Прекращаем наблюдение за всеми
        for (const sentinel of this.observedDates) {
            this.observer.unobserve(sentinel);
        }
        
        this.observedDates.clear();

        // Начинаем заново
        this.observeAll();
        
        console.log('[StickyDateObserver] Refreshed');
    }

    /**
     * Уничтожает observer и очищает ресурсы
     * 
     * @example
     * // При unmount компонента
     * observer.destroy();
     */
    destroy() {
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
        
        this.observedDates.clear();
        
        console.log('[StickyDateObserver] Destroyed');
    }

    /**
     * Проверяет, инициализирован ли observer
     * 
     * @returns {boolean}
     */
    isInitialized() {
        return this.observer !== null;
    }

    /**
     * Получает количество наблюдаемых элементов
     * 
     * @returns {number}
     */
    getObservedCount() {
        return this.observedDates.size;
    }
}

export default StickyDateObserver;

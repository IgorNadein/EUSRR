/**
 * @fileoverview UnreadBadgeManager - управление badge непрочитанных на scrollBtn
 * @module managers/unreadBadgeManager
 * 
 * ОТВЕТСТВЕННОСТЬ:
 * - Создание и управление badge элементом
 * - Увеличение/сброс счетчика
 * - Визуальные эффекты (анимации, классы)
 * - НЕТ бизнес-логики (когда показывать/скрывать)
 */

/**
 * Управляет badge непрочитанных сообщений на кнопке скролла
 */
export class UnreadBadgeManager {
    /**
     * @param {string} buttonId - ID кнопки скролла
     */
    constructor(buttonId) {
        this.buttonId = buttonId;
        this.button = null;
        this.badge = null;
        this.count = 0;
        
        this._init();
    }

    /**
     * Инициализирует badge
     * @private
     */
    _init() {
        this.button = document.getElementById(this.buttonId);
        
        if (!this.button) {
            console.warn(`[UnreadBadgeManager] Button #${this.buttonId} not found`);
            return;
        }

        // Ищем существующий badge или создаем новый
        this.badge = this.button.querySelector('.unread-badge');
        
        if (!this.badge) {
            this.badge = this._createBadge();
            this.button.appendChild(this.badge);
        }

        console.log('[UnreadBadgeManager] Initialized');
    }

    /**
     * Создает badge элемент
     * @private
     * @returns {HTMLElement}
     */
    _createBadge() {
        const badge = document.createElement('span');
        badge.className = 'unread-badge';
        badge.style.display = 'none';
        badge.textContent = '0';
        return badge;
    }

    /**
     * Увеличивает счетчик непрочитанных
     * @returns {number} Новое значение счетчика
     */
    increment() {
        if (!this.badge || !this.button) {
            console.warn('[UnreadBadgeManager] Cannot increment: not initialized');
            return this.count;
        }

        this.count++;
        this.badge.textContent = this.count;
        this.badge.style.display = 'flex';
        this.button.classList.add('has-unread');

        console.log('[UnreadBadgeManager] Incremented:', this.count);
        return this.count;
    }

    /**
     * Сбрасывает счетчик непрочитанных
     */
    reset() {
        if (!this.badge || !this.button) {
            console.warn('[UnreadBadgeManager] Cannot reset: not initialized');
            return;
        }

        this.count = 0;
        this.badge.textContent = '0';
        this.badge.style.display = 'none';
        this.button.classList.remove('has-unread');

        console.log('[UnreadBadgeManager] Reset');
    }

    /**
     * Устанавливает конкретное значение счетчика
     * @param {number} value - Новое значение
     */
    setCount(value) {
        if (!this.badge || !this.button) {
            console.warn('[UnreadBadgeManager] Cannot set count: not initialized');
            return;
        }

        this.count = Math.max(0, value);
        this.badge.textContent = this.count;

        if (this.count > 0) {
            this.badge.style.display = 'flex';
            this.button.classList.add('has-unread');
        } else {
            this.badge.style.display = 'none';
            this.button.classList.remove('has-unread');
        }
    }

    /**
     * Получает текущий счетчик
     * @returns {number}
     */
    getCount() {
        return this.count;
    }

    /**
     * Проверяет есть ли непрочитанные
     * @returns {boolean}
     */
    hasUnread() {
        return this.count > 0;
    }

    /**
     * Уничтожает badge manager
     */
    destroy() {
        if (this.badge && this.badge.parentNode) {
            this.badge.remove();
        }
        this.button = null;
        this.badge = null;
        this.count = 0;
    }
}

/**
 * DateDividerManager - Централизованная утилита для управления date dividers в чате
 * 
 * Основано на архитектуре Telegram Web:
 * - Единый источник логики для дат
 * - Поддержка группировки сообщений
 * - Sticky positioning
 * 
 * @module dateDividers
 */

import { formatDay } from './chatUtils.js';
import { escapeHtml } from './chatUtils.js';

/**
 * Менеджер для создания и управления date dividers
 */
export class DateDividerManager {
    /**
     * Форматирует дату для отображения (re-export из chatUtils)
     * 
     * @param {Date|string|number} date - Дата для форматирования
     * @returns {string} Отформатированная дата ("Сегодня", "Вчера", "5 января 2026")
     * 
     * @example
     * DateDividerManager.formatDay(new Date()) // "Сегодня"
     * DateDividerManager.formatDay('2026-01-05') // "5 января 2026"
     */
    static formatDay(date) {
        return formatDay(date);
    }

    /**
     * Создает DOM элемент date divider (простой вариант)
     * Используется для обратной совместимости с текущей версией
     * 
     * @param {string} text - Текст даты для отображения
     * @returns {HTMLDivElement} DOM элемент divider
     * 
     * @example
     * const divider = DateDividerManager.createDivider('Сегодня');
     * container.appendChild(divider);
     */
    static createDivider(text) {
        const dividerEl = document.createElement('div');
        dividerEl.className = 'day-divider text-center small text-muted my-3';
        dividerEl.setAttribute('data-date-divider', text);
        
        const bubble = document.createElement('span');
        bubble.className = 'px-3 py-1 rounded-pill bg-light';
        bubble.textContent = escapeHtml(text);
        
        dividerEl.appendChild(bubble);
        return dividerEl;
    }

    /**
     * Создает sticky date header (как в Telegram Web)
     * Используется для группировки сообщений по датам
     * 
     * @param {string} text - Текст даты для отображения
     * @param {boolean} interactive - Добавить ли класс interactive для кликабельности
     * @returns {HTMLDivElement} DOM элемент sticky date
     * 
     * @example
     * const stickyDate = DateDividerManager.createStickyDate('Сегодня', true);
     * dateGroup.appendChild(stickyDate);
     */
    static createStickyDate(text, interactive = false) {
        const stickyEl = document.createElement('div');
        const classes = ['sticky-date'];
        if (interactive) {
            classes.push('interactive');
        }
        stickyEl.className = classes.join(' ');
        stickyEl.setAttribute('data-date-text', text);
        
        const span = document.createElement('span');
        span.setAttribute('dir', 'auto');
        span.textContent = escapeHtml(text);
        
        stickyEl.appendChild(span);
        return stickyEl;
    }

    /**
     * Проверяет, нужно ли добавлять date divider между сообщениями
     * 
     * @param {string} currentDay - Дата текущего сообщения (отформатированная)
     * @param {string} previousDay - Дата предыдущего сообщения (отформатированная)
     * @returns {boolean} true если нужно добавить divider
     * 
     * @example
     * const needsDivider = DateDividerManager.shouldAddDivider('Сегодня', 'Вчера');
     * if (needsDivider) {
     *     container.appendChild(DateDividerManager.createDivider('Сегодня'));
     * }
     */
    static shouldAddDivider(currentDay, previousDay) {
        // Если это первое сообщение или даты разные - добавляем divider
        return !previousDay || currentDay !== previousDay;
    }

    /**
     * Извлекает дату из сообщения (универсальный метод)
     * 
     * @param {Object} message - Объект сообщения
     * @returns {Date} Дата сообщения
     * 
     * @example
     * const date = DateDividerManager.getMessageDate(message);
     * const formatted = DateDividerManager.formatDay(date);
     */
    static getMessageDate(message) {
        // Поддержка разных форматов timestamp
        const timestamp = message.created_ts || message.timestamp || message.created_at;
        
        if (!timestamp) {
            console.warn('[DateDividerManager] Message without timestamp:', message);
            return new Date();
        }

        // Если timestamp в секундах (10 цифр), конвертируем в миллисекунды
        const ts = timestamp.toString().length === 10 ? timestamp * 1000 : timestamp;
        
        return new Date(ts);
    }

    /**
     * Группирует массив сообщений по датам
     * Возвращает структуру для рендеринга с dividers
     * 
     * @param {Array} messages - Массив сообщений
     * @returns {Array} Массив объектов { type: 'divider'|'message', data: ... }
     * 
     * @example
     * const grouped = DateDividerManager.groupMessages(messages);
     * grouped.forEach(item => {
     *     if (item.type === 'divider') {
     *         container.appendChild(DateDividerManager.createDivider(item.text));
     *     } else {
     *         renderMessage(item.message);
     *     }
     * });
     */
    static groupMessages(messages) {
        const result = [];
        let lastDay = null;

        for (const message of messages) {
            const date = this.getMessageDate(message);
            const day = this.formatDay(date);

            if (this.shouldAddDivider(day, lastDay)) {
                result.push({
                    type: 'divider',
                    text: day,
                    timestamp: date.getTime()
                });
                lastDay = day;
            }

            result.push({
                type: 'message',
                message: message,
                day: day
            });
        }

        return result;
    }

    /**
     * Находит date divider по тексту даты в контейнере
     * 
     * @param {HTMLElement} container - Контейнер для поиска
     * @param {string} dateText - Текст даты
     * @returns {HTMLElement|null} Найденный divider или null
     * 
     * @example
     * const divider = DateDividerManager.findDivider(chatScroll, 'Сегодня');
     * if (divider) {
     *     divider.scrollIntoView();
     * }
     */
    static findDivider(container, dateText) {
        return container.querySelector(`[data-date-divider="${dateText}"], [data-date-text="${dateText}"]`);
    }

    /**
     * Обновляет текст существующего divider (для live update)
     * Например, когда "Сегодня" становится "Вчера" после полуночи
     * 
     * @param {HTMLElement} divider - DOM элемент divider
     * @param {string} newText - Новый текст
     * 
     * @example
     * // После полуночи обновляем даты
     * const dividers = document.querySelectorAll('[data-date-divider]');
     * dividers.forEach(div => {
     *     const date = new Date(div.dataset.timestamp);
     *     const newText = DateDividerManager.formatDay(date);
     *     DateDividerManager.updateDivider(div, newText);
     * });
     */
    static updateDivider(divider, newText) {
        const bubble = divider.querySelector('span');
        if (bubble) {
            bubble.textContent = escapeHtml(newText);
            divider.setAttribute('data-date-divider', newText);
        }
    }

    /**
     * Удаляет все date dividers из контейнера
     * Полезно для полной перерисовки
     * 
     * @param {HTMLElement} container - Контейнер
     * 
     * @example
     * DateDividerManager.clearDividers(chatScroll);
     * // Теперь можно заново отрендерить сообщения с dividers
     */
    static clearDividers(container) {
        const dividers = container.querySelectorAll('[data-date-divider], .sticky-date');
        dividers.forEach(div => div.remove());
    }
}

/**
 * Экспортируем отдельные функции для удобства
 */
export const {
    formatDay: formatDayExport,
    createDivider,
    createStickyDate,
    shouldAddDivider,
    getMessageDate,
    groupMessages,
    findDivider,
    updateDivider,
    clearDividers
} = DateDividerManager;

export default DateDividerManager;

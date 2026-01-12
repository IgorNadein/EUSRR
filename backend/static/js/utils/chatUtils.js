/**
 * @fileoverview Chat Utilities - вспомогательные функции для чата
 * @module utils/chatUtils
 */

/**
 * Создает debounced функцию
 * @param {Function} fn - Функция для debounce
 * @param {number} delay - Задержка в мс
 * @returns {Function}
 */
export function debounce(fn, delay) {
    let timeoutId = null;
    
    function debounced(...args) {
        if (timeoutId) {
            clearTimeout(timeoutId);
        }
        timeoutId = setTimeout(() => {
            fn.apply(this, args);
            timeoutId = null;
        }, delay);
    }
    
    debounced.cancel = () => {
        if (timeoutId) {
            clearTimeout(timeoutId);
            timeoutId = null;
        }
    };
    
    return debounced;
}

/**
 * Создает throttled функцию
 * @param {Function} fn - Функция для throttle
 * @param {number} limit - Минимальный интервал в мс
 * @returns {Function}
 */
export function throttle(fn, limit) {
    let inThrottle = false;
    let lastArgs = null;
    
    return function(...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => {
                inThrottle = false;
                if (lastArgs) {
                    fn.apply(this, lastArgs);
                    lastArgs = null;
                }
            }, limit);
        } else {
            lastArgs = args;
        }
    };
}

/**
 * Экранирует HTML для безопасного вывода
 * @param {string} text - Текст для экранирования
 * @returns {string}
 */
export function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

/**
 * Форматирует дату в текст дня
 * @param {Date|number} date - Дата или timestamp
 * @returns {string}
 */
export function formatDay(date) {
    const d = date instanceof Date ? date : new Date(date);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (d.toDateString() === today.toDateString()) return 'Сегодня';
    if (d.toDateString() === yesterday.toDateString()) return 'Вчера';

    return d.toLocaleDateString('ru-RU', { 
        day: 'numeric', 
        month: 'long', 
        year: 'numeric' 
    });
}

/**
 * Форматирует время
 * @param {Date|number} date - Дата или timestamp
 * @returns {string}
 */
export function formatTime(date) {
    const d = date instanceof Date ? date : new Date(date);
    return d.toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

/**
 * Форматирует дату и время
 * @param {Date|number} date - Дата или timestamp
 * @returns {string}
 */
export function formatDateTime(date) {
    return `${formatDay(date)}, ${formatTime(date)}`;
}

/**
 * Форматирует размер файла
 * @param {number} bytes - Размер в байтах
 * @returns {string}
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB'];
    const k = 1024;
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${units[i]}`;
}

/**
 * Генерирует уникальный ID
 * @param {string} [prefix=''] - Префикс
 * @returns {string}
 */
export function generateId(prefix = '') {
    const random = Math.random().toString(36).substr(2, 9);
    return prefix ? `${prefix}_${Date.now()}_${random}` : `${Date.now()}_${random}`;
}

/**
 * Ждет указанное время
 * @param {number} ms - Миллисекунды
 * @returns {Promise<void>}
 */
export function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Ждет следующего кадра анимации
 * @returns {Promise<void>}
 */
export function nextFrame() {
    return new Promise(resolve => requestAnimationFrame(resolve));
}

/**
 * Ждет двойного кадра (гарантия после layout)
 * @returns {Promise<void>}
 */
export function afterLayout() {
    return new Promise(resolve => {
        requestAnimationFrame(() => {
            requestAnimationFrame(resolve);
        });
    });
}

/**
 * Проверяет, виден ли элемент в контейнере
 * @param {HTMLElement} element - Элемент
 * @param {HTMLElement} container - Контейнер
 * @returns {boolean}
 */
export function isElementVisible(element, container) {
    const elRect = element.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    
    return (
        elRect.top >= containerRect.top &&
        elRect.bottom <= containerRect.bottom
    );
}

/**
 * Проверяет, частично виден ли элемент в контейнере
 * @param {HTMLElement} element - Элемент
 * @param {HTMLElement} container - Контейнер
 * @returns {boolean}
 */
export function isElementPartiallyVisible(element, container) {
    const elRect = element.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    
    return (
        elRect.bottom >= containerRect.top &&
        elRect.top <= containerRect.bottom
    );
}

/**
 * Копирует текст в буфер обмена
 * @param {string} text - Текст для копирования
 * @returns {Promise<boolean>}
 */
export async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        // Fallback для старых браузеров
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        
        try {
            document.execCommand('copy');
            return true;
        } catch {
            return false;
        } finally {
            document.body.removeChild(textarea);
        }
    }
}

/**
 * Парсит булево значение из строки
 * @param {any} value - Значение
 * @returns {boolean}
 */
export function parseBool(value) {
    if (typeof value === 'boolean') return value;
    if (value === '1' || value === 'true') return true;
    return false;
}

/**
 * Глубокое клонирование объекта
 * @param {Object} obj - Объект для клонирования
 * @returns {Object}
 */
export function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (Array.isArray(obj)) return obj.map(deepClone);
    
    const clone = {};
    for (const key in obj) {
        if (Object.prototype.hasOwnProperty.call(obj, key)) {
            clone[key] = deepClone(obj[key]);
        }
    }
    return clone;
}

/**
 * Сравнивает два объекта на равенство
 * @param {any} a - Первый объект
 * @param {any} b - Второй объект
 * @returns {boolean}
 */
export function isEqual(a, b) {
    if (a === b) return true;
    if (a == null || b == null) return false;
    if (typeof a !== typeof b) return false;
    
    if (typeof a === 'object') {
        const keysA = Object.keys(a);
        const keysB = Object.keys(b);
        
        if (keysA.length !== keysB.length) return false;
        
        return keysA.every(key => isEqual(a[key], b[key]));
    }
    
    return false;
}

export default {
    debounce,
    throttle,
    escapeHtml,
    formatDay,
    formatTime,
    formatDateTime,
    formatFileSize,
    generateId,
    delay,
    nextFrame,
    afterLayout,
    isElementVisible,
    isElementPartiallyVisible,
    copyToClipboard,
    parseBool,
    deepClone,
    isEqual
};

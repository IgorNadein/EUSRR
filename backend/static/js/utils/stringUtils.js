/**
 * String Utilities
 * 
 * Утилиты для работы со строками: экранирование, нормализация, работа с cookies и т.д.
 * 
 * Использование:
 * import { esc, norm, getCookie } from '{% static "js/utils/stringUtils.js" %}';
 */

/**
 * Получение значения cookie по имени
 * 
 * @param {string} name - имя cookie
 * @returns {string} - значение cookie или пустая строка
 * 
 * @example
 * getCookie('csrftoken')
 * // => 'abc123xyz...'
 * 
 * getCookie('nonexistent')
 * // => ''
 */
export function getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

/**
 * Экранирование HTML символов для безопасного отображения
 * Защищает от XSS атак при выводе пользовательского контента
 * 
 * @param {string|number|null|undefined} s - строка для экранирования
 * @returns {string} - экранированная строка
 * 
 * @example
 * esc('<script>alert("XSS")</script>')
 * // => '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'
 * 
 * esc("O'Reilly & Sons")
 * // => 'O&#39;Reilly &amp; Sons'
 */
export function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Нормализация строки для поиска и сравнения
 * Приводит к lowercase, заменяет множественные пробелы на один, убирает пробелы с краёв
 * 
 * @param {string|null|undefined} s - строка для нормализации
 * @returns {string} - нормализованная строка
 * 
 * @example
 * norm('  Иван   Петров  ')
 * // => 'иван петров'
 * 
 * norm('МОСКВА')
 * // => 'москва'
 */
export function norm(s) {
  return (s || '').toString().toLowerCase().replace(/\s+/g, ' ').trim();
}

/**
 * Экранирование для использования в атрибутах HTML
 * Более строгое, чем esc() - заменяет больше символов
 * 
 * @param {string|null|undefined} s - строка для экранирования
 * @returns {string} - экранированная строка для атрибута
 * 
 * @example
 * escAttr('value="test"')
 * // => 'value=&quot;test&quot;'
 */
export function escAttr(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Усечение строки до указанной длины с добавлением многоточия
 * 
 * @param {string} s - строка для усечения
 * @param {number} maxLen - максимальная длина (включая многоточие)
 * @returns {string} - усечённая строка
 * 
 * @example
 * truncate('Очень длинная строка текста', 15)
 * // => 'Очень длинн...'
 */
export function truncate(s, maxLen) {
  const str = String(s || '');
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}

/**
 * Извлечение инициалов из ФИО
 * 
 * @param {string} fullName - полное имя
 * @returns {string} - инициалы
 * 
 * @example
 * getInitials('Иванов Иван Петрович')
 * // => 'ИИ'
 * 
 * getInitials('John Doe')
 * // => 'JD'
 */
export function getInitials(fullName) {
  const parts = String(fullName || '').trim().split(/\s+/);
  if (parts.length === 0) return '';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase();
}

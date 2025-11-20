/**
 * @module chatBadgeHandler
 * @description Обработчик бейджа непрочитанных чатов в боковой панели.
 * Автоматически обновляет счётчик непрочитанных сообщений, поддерживает real-time обновления.
 * 
 * Пример HTML:
 * <span id="sidebarChatBadge" data-count="0" class="badge d-none">0</span>
 * 
 * Использование:
 * import { initChatBadge } from './chatBadgeHandler.js';
 * initChatBadge({ badgeId: 'sidebarChatBadge' });
 * 
 * Real-time обновление:
 * window.dispatchEvent(new CustomEvent('chats:unread-total', { detail: { total: 5 } }));
 */

/**
 * Форматирует число для отображения в бейдже (99+).
 * @param {number} count - Количество непрочитанных сообщений
 * @returns {string} Отформатированная строка
 */
function formatCount(count) {
  const value = Number(count) || 0;
  return value > 99 ? '99+' : String(value);
}

/**
 * Инициализирует обработчик бейджа непрочитанных чатов.
 * @param {Object} options - Опции инициализации
 * @param {string} [options.badgeId='sidebarChatBadge'] - ID элемента бейджа
 * @param {string} [options.hiddenClass='d-none'] - Класс для скрытия бейджа
 * @param {string} [options.eventName='chats:unread-total'] - Имя события для real-time обновлений
 * @returns {Object} API с методами update, destroy
 */
export function initChatBadge(options = {}) {
  const {
    badgeId = 'sidebarChatBadge',
    hiddenClass = 'd-none',
    eventName = 'chats:unread-total'
  } = options;

  const badge = document.getElementById(badgeId);

  if (!badge) {
    console.warn('initChatBadge: элемент бейджа не найден');
    return { update: () => {}, destroy: () => {} };
  }

  /**
   * Обновляет отображение бейджа.
   * @param {number} count - Новое количество непрочитанных сообщений
   */
  function updateBadge(count) {
    const value = Number(count) || 0;
    
    badge.dataset.count = String(value);
    badge.textContent = formatCount(value);
    badge.classList.toggle(hiddenClass, value <= 0);
  }

  /**
   * Обработчик real-time события обновления счётчика.
   * @param {CustomEvent} event - Событие с данными { detail: { total: number } }
   */
  function handleRealtimeUpdate(event) {
    const total = event?.detail?.total;
    if (typeof total !== 'undefined') {
      updateBadge(total);
    }
  }

  /**
   * Fallback: подсчитывает общее количество непрочитанных из элементов на странице.
   * Используется на страницах списка чатов, где каждый чат имеет [data-unread-count].
   */
  function calculateTotalFromPage() {
    const rows = document.querySelectorAll('[data-unread-count]');
    if (!rows.length) return;

    const total = Array.from(rows).reduce((sum, element) => {
      return sum + (Number(element.textContent) || 0);
    }, 0);

    updateBadge(total);
  }

  // Начальная установка значения из data-count
  updateBadge(badge.dataset.count);

  // Подписка на real-time обновления
  window.addEventListener(eventName, handleRealtimeUpdate);

  // Fallback подсчёт при загрузке страницы
  document.addEventListener('DOMContentLoaded', calculateTotalFromPage);

  /**
   * Функция для удаления обработчиков.
   */
  function destroy() {
    window.removeEventListener(eventName, handleRealtimeUpdate);
    document.removeEventListener('DOMContentLoaded', calculateTotalFromPage);
  }

  return {
    /**
     * Публичный метод для обновления счётчика.
     * @param {number} count - Новое значение
     */
    update: updateBadge,
    destroy
  };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initChatBadge = initChatBadge;
}

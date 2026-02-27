/**
 * @fileoverview Chat Badge Manager - управление счётчиками непрочитанных сообщений
 * Слушает события `chat:read` и обновляет бейджи для чатов
 * @module components/chatBadgeManager
 */

/**
 * Инициализирует менеджер бейджей непрочитанных сообщений
 * @param {Object} options - Опции инициализации
 * @param {string} [options.chatRowSelector='.chat-row'] - Селектор элементов чата
 * @param {string} [options.badgeSelector='[data-unread]'] - Селектор бейджа
 * @param {string} [options.countSelector='[data-unread-count]'] - Селектор счётчика
 * @returns {Object|null} API менеджера или null
 */
export function initChatBadgeManager(options = {}) {
  const {
    chatRowSelector = '.chat-row',
    badgeSelector = '[data-unread]',
    countSelector = '[data-unread-count]'
  } = options;

  /**
   * Обновляет бейдж для конкретного чата
   * @param {string} chatId - ID чата
   * @param {number} count - Количество непрочитанных (0 = скрыть бейдж)
   */
  function updateBadge(chatId, count = 0) {
    const row = document.querySelector(`${chatRowSelector}[data-chat-id="${chatId}"]`);
    if (!row) return;

    const badge = row.querySelector(badgeSelector);
    const cntEl = row.querySelector(countSelector);

    if (cntEl) {
      cntEl.textContent = String(count);
    }

    if (badge) {
      // Telegram-стиль: используем style.display и анимацию
      const oldCount = parseInt(cntEl?.textContent || '0', 10);
      if (count > 0) {
        badge.style.display = '';
        // Анимация при увеличении
        if (count > oldCount) {
          badge.classList.add('pulse');
          setTimeout(() => badge.classList.remove('pulse'), 600);
        }
      } else {
        badge.style.display = 'none';
        badge.classList.remove('pulse');
      }
    }
  }

  /**
   * Получает текущее количество непрочитанных для чата
   * @param {string} chatId - ID чата
   * @returns {number} Количество непрочитанных
   */
  function getBadgeCount(chatId) {
    const row = document.querySelector(`${chatRowSelector}[data-chat-id="${chatId}"]`);
    if (!row) return 0;

    const cntEl = row.querySelector(countSelector);
    if (!cntEl) return 0;

    return Number(cntEl.textContent) || 0;
  }

  /**
   * Увеличивает счётчик непрочитанных для чата
   * @param {string} chatId - ID чата
   * @param {number} delta - На сколько увеличить (по умолчанию 1)
   */
  function incrementBadge(chatId, delta = 1) {
    const current = getBadgeCount(chatId);
    updateBadge(chatId, current + delta);
  }

  /**
   * Сбрасывает бейдж (устанавливает 0)
   * @param {string} chatId - ID чата
   */
  function resetBadge(chatId) {
    updateBadge(chatId, 0);
  }

  /**
   * Обработчик события chat:read
   * @param {CustomEvent} e - Событие с detail.chatId
   */
  function handleChatRead(e) {
    const chatId = e.detail?.chatId;
    if (chatId) {
      resetBadge(chatId);
    }
  }

  // Подключаем обработчик события
  window.addEventListener('chat:read', handleChatRead);

  // API
  return {
    /**
     * Программное обновление бейджа
     * @param {string} chatId - ID чата
     * @param {number} count - Количество непрочитанных
     */
    updateBadge,

    /**
     * Получить количество непрочитанных
     * @param {string} chatId - ID чата
     * @returns {number}
     */
    getBadgeCount,

    /**
     * Увеличить счётчик
     * @param {string} chatId - ID чата
     * @param {number} delta - На сколько увеличить
     */
    incrementBadge,

    /**
     * Сбросить счётчик в 0
     * @param {string} chatId - ID чата
     */
    resetBadge,

    /**
     * Уничтожение обработчиков
     */
    destroy: () => {
      window.removeEventListener('chat:read', handleChatRead);
    }
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initChatBadgeManager = initChatBadgeManager;
}

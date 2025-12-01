/**
 * @fileoverview Chat List Realtime - обновление списка чатов в реальном времени
 * ВНИМАНИЕ: Больше НЕ создаёт собственное WebSocket соединение!
 * Использует универсальное userWebSocket из base.html через callback onListUpdate
 * @module components/chatListRealtime
 */

/**
 * Инициализирует обработчик realtime-обновлений списка чатов
 * @param {Object} options - Опции инициализации
 * @param {number} options.meId - ID текущего пользователя
 * @param {string} [options.chatRowSelector='.chat-row'] - Селектор элементов чата
 * @param {Object} [options.badgeManager] - API chatBadgeManager для обновления бейджей
 * @returns {Object|null} API обработчика или null если список чатов не найден
 */
export function initChatListRealtime(options = {}) {
  const {
    meId,
    chatRowSelector = '.chat-row',
    badgeManager
  } = options;

  // Проверяем наличие списка чатов
  const listAny = document.querySelector(chatRowSelector);
  if (!listAny) {
    // Тихо выходим если не на странице чатов
    return null;
  }

  if (!meId) {
    console.warn('[ChatListRealtime] meId is required');
    return null;
  }

  console.log('[ChatListRealtime] Initialized (using shared userWebSocket)');

  /**
   * Пересортирует элементы секции по timestamp
   * @param {HTMLElement} sectionListEl - Контейнер списка чатов
   */
  function resortSection(sectionListEl) {
    if (!sectionListEl) return;

    const rows = Array.from(sectionListEl.querySelectorAll(chatRowSelector));
    rows.sort((a, b) => {
      const ta = Number(a.getAttribute('data-last-ts') || 0);
      const tb = Number(b.getAttribute('data-last-ts') || 0);
      return tb - ta; // Сортировка по убыванию (новые сверху)
    });
    rows.forEach(r => sectionListEl.appendChild(r));
  }

  /**
   * Получает контейнер для типа чата
   * @param {string} type - Тип чата (global, department, private, group, channel, announcement)
   * @returns {HTMLElement|null}
   */
  function containerForType(type) {
    if (type === 'global') return document.getElementById('sec-global');
    if (type === 'department') return document.getElementById('sec-department');
    if (type === 'private') return document.getElementById('sec-private');
    if (type === 'group') return document.getElementById('sec-group');
    if (type === 'channel') return document.getElementById('sec-channel');
    if (type === 'announcement') return document.getElementById('sec-announcement');
    return null;
  }

  /**
   * Обновляет карточку чата в списке (вызывается из userWebSocket через onListUpdate)
   * @param {string|number} chatId - ID чата
   * @param {Object} msg - Объект сообщения с полями created, author_name, preview и т.д.
   */
  function updateChatCard(chatId, msg = {}) {
    try {
      chatId = String(chatId);
      
      // Находим строку чата
      const row = document.querySelector(`${chatRowSelector}[data-chat-id="${chatId}"]`);
      if (!row) return;

      // Обновляем timestamp
      const ts = Number(msg.created_ts || Date.now());
      row.setAttribute('data-last-ts', String(ts));

      // Обновляем время, автора и превью
      const timeEl = row.querySelector('[data-last-time]');
      const authEl = row.querySelector('[data-last-author]');
      const prevEl = row.querySelector('[data-last-preview]');

      if (timeEl) timeEl.textContent = msg.created || '';
      if (authEl) authEl.textContent = msg.author_name || 'Сотрудник';
      if (prevEl) prevEl.textContent = (msg.content || '').slice(0, 120);

      // Обновляем бейдж
      const isMyMessage = Number(msg.author_id) === Number(meId);
      
      if (isMyMessage) {
        // Моё сообщение - сбрасываем счётчик
        if (badgeManager) {
          badgeManager.resetBadge(chatId);
        } else {
          // Fallback если нет badgeManager
          const badge = row.querySelector('[data-unread]');
          const cntEl = row.querySelector('[data-unread-count]');
          if (cntEl) cntEl.textContent = '0';
          if (badge) badge.classList.add('d-none');
        }
      } else {
        // Чужое сообщение - увеличиваем счётчик
        if (badgeManager) {
          badgeManager.incrementBadge(chatId, 1);
        } else {
          // Fallback если нет badgeManager
          const badge = row.querySelector('[data-unread]');
          const cntEl = row.querySelector('[data-unread-count]');
          const cur = Number((cntEl && cntEl.textContent) || 0) + 1;
          if (cntEl) cntEl.textContent = String(cur);
          if (badge && cur > 0) badge.classList.remove('d-none');
        }
      }

      // Пересортировываем список
      const type = row.getAttribute('data-type');
      const list = containerForType(type);
      if (list) {
        resortSection(list);
      }

      // Обновить глобальный бейдж если есть
      if (badgeManager) {
        badgeManager.refresh();
      }

      // Анимация обновления
      row.classList.add('updated');
      setTimeout(() => row.classList.remove('updated'), 300);

    } catch (err) {
      console.error('[ChatListRealtime] updateChatCard error:', err);
    }
  }

  // API
  return {
    updateChatCard,  // Главная функция - вызывается из userWebSocket
    resortSection,
    containerForType
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initChatListRealtime = initChatListRealtime;
}

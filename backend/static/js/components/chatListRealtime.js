/**
 * @fileoverview Chat List Realtime - WebSocket для обновления списка чатов в реальном времени
 * Обновляет последние сообщения, время, счётчики, пересортирует список по timestamp
 * @module components/chatListRealtime
 */

/**
 * Инициализирует WebSocket для realtime-обновлений списка чатов
 * @param {Object} options - Опции инициализации
 * @param {number} options.meId - ID текущего пользователя
 * @param {string} [options.chatRowSelector='.chat-row'] - Селектор элементов чата
 * @param {string} [options.wsUrl] - URL WebSocket (по умолчанию /ws/chats/)
 * @param {Object} [options.badgeManager] - API chatBadgeManager для обновления бейджей
 * @returns {Object|null} API WebSocket или null если список чатов не найден
 */
export function initChatListRealtime(options = {}) {
  const {
    meId,
    chatRowSelector = '.chat-row',
    wsUrl,
    badgeManager
  } = options;

  // Проверяем наличие списка чатов
  const listAny = document.querySelector(chatRowSelector);
  if (!listAny) {
    console.warn('ChatListRealtime: no chat rows found, skipping');
    return null;
  }

  if (!meId) {
    console.warn('ChatListRealtime: meId is required');
    return null;
  }

  // Создаём WebSocket соединение
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = wsUrl || `/ws/chats/`;
  const ws = new WebSocket(`${proto}://${location.host}${url}`);

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
   * @param {string} type - Тип чата (global, department, private)
   * @returns {HTMLElement|null}
   */
  function containerForType(type) {
    if (type === 'global') return document.getElementById('sec-global');
    if (type === 'department') return document.getElementById('sec-department');
    return document.getElementById('sec-private');
  }

  /**
   * Обрабатывает входящие сообщения WebSocket
   */
  ws.addEventListener('message', (e) => {
    try {
      const data = JSON.parse(e.data);
      
      // Обрабатываем только list_update события
      if (data.type !== 'list_update') return;

      const chatId = String(data.chat_id);
      const msg = data.message || {};
      
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
    } catch (err) {
      console.warn('ChatListRealtime: failed to parse message', err);
    }
  });

  /**
   * Обрабатывает закрытие соединения
   */
  ws.addEventListener('close', () => {
    console.log('ChatListRealtime: connection closed');
  });

  /**
   * Обрабатывает ошибки WebSocket
   */
  ws.addEventListener('error', (err) => {
    console.error('ChatListRealtime: connection error', err);
  });

  // API
  return {
    /**
     * Закрывает WebSocket соединение
     */
    close: () => {
      ws.close();
    },

    /**
     * Программная пересортировка секции
     * @param {string} type - Тип секции (global, department, private)
     */
    resortSection: (type) => {
      const container = containerForType(type);
      if (container) {
        resortSection(container);
      }
    },

    /**
     * Получает состояние соединения
     * @returns {number} WebSocket.readyState
     */
    getReadyState: () => ws.readyState,

    /**
     * Прямой доступ к WebSocket (для отладки)
     */
    ws
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initChatListRealtime = initChatListRealtime;
}

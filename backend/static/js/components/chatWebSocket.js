/**
 * @fileoverview Chat WebSocket - WebSocket соединение для чата в реальном времени
 * Отправка/получение сообщений, индикация "печатает...", рендеринг в DOM
 * @module components/chatWebSocket
 */

import { getChatAvatar } from './chatAvatarMap.js';
import {
  createMessageElement,
  createDayDivider,
  formatDay,
  toTimestamp
} from './chatMessageTemplates.js';

/**
 * Инициализирует WebSocket соединение для чата
 * @param {Object} options - Опции инициализации
 * @param {number} options.chatId - ID чата
 * @param {number} options.meId - ID текущего пользователя
 * @param {string} [options.scrollContainerId='chatScroll'] - ID контейнера скролла
 * @param {string} [options.formId='chatForm'] - ID формы отправки
 * @param {string} [options.textareaId='id_content'] - ID textarea
 * @param {string} [options.typingIndicatorId='typing'] - ID индикатора "печатает..."
 * @param {string} [options.profileUrl] - URL профиля текущего пользователя
 * @param {string} [options.detailUrlTemplate] - Шаблон URL деталей сотрудника
 * @param {Object} [options.avatarMap] - Карта аватаров пользователей
 * @param {Object} [options.markReadApi] - API из chatMarkRead для интеграции
 * @returns {Object|null} API WebSocket или null если параметры невалидны
 */
export function initChatWebSocket(options = {}) {
  const {
    chatId,
    meId,
    scrollContainerId = 'chatScroll',
    formId = 'chatForm',
    textareaId = 'id_content',
    typingIndicatorId = 'typing',
    profileUrl = '/employees/profile/',
    detailUrlTemplate = '/employees/0/',
    avatarMap = {},
    markReadApi
  } = options;

  // Проверка обязательных параметров
  if (!chatId || !meId) {
    console.warn('ChatWebSocket: chatId and meId are required');
    return null;
  }

  // Получение элементов
  const scrollEl = document.getElementById(scrollContainerId);
  if (!scrollEl) {
    console.warn(`ChatWebSocket: element #${scrollContainerId} not found`);
    return null;
  }

  const form = document.getElementById(formId);
  const ta = document.getElementById(textareaId);
  const typingEl = document.getElementById(typingIndicatorId);

  // Извлекаем методы из chatMarkRead API
  const { markRead, observeLastForeign, autoscroll, atBottom } = markReadApi || {};

  // Создание WebSocket соединения
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${location.host}/ws/chat/${chatId}/`;
  const ws = new WebSocket(wsUrl);

  /**
   * Инициализирует последний день из DOM
   */
  function ensureLastDayFromDom() {
    const dl = scrollEl.querySelector('.day-divider:last-of-type span');
    if (dl) {
      scrollEl.dataset.lastDay = dl.textContent.trim();
    } else {
      const lastMsg = scrollEl.querySelector('.msg:last-of-type');
      if (lastMsg) {
        const ts = Number(lastMsg.dataset.ts || Date.now());
        scrollEl.dataset.lastDay = formatDay(ts);
      }
    }
  }
  ensureLastDayFromDom();

  /**
   * Рендерит разделитель дня
   * @param {string} dateStr - Дата в текстовом формате
   */
  function renderDayDivider(dateStr) {
    const div = createDayDivider(dateStr);
    scrollEl.appendChild(div);
  }

  /**
   * Рендерит сообщение в DOM
   * @param {Object} msg - Объект сообщения
   */
  function renderMessage(msg) {
    const mine = Number(msg.author_id) === Number(meId);

    // Обновляем карту аватаров
    if (msg.author_id && msg.avatar && !avatarMap[msg.author_id]) {
      avatarMap[msg.author_id] = msg.avatar;
    }

    // Проверяем день
    const ts = toTimestamp(msg);
    const dayStr = msg.day || formatDay(ts);
    
    if (dayStr && scrollEl.dataset.lastDay !== dayStr) {
      renderDayDivider(dayStr);
      scrollEl.dataset.lastDay = dayStr;
    }

    // Создаём элемент сообщения
    const msgElement = createMessageElement(msg, {
      meId,
      profileUrl,
      detailUrlTemplate,
      avatarMap
    });

    // Проверяем, нужен ли автоскролл
    const keep = atBottom ? atBottom() : false;

    // Добавляем в DOM
    scrollEl.appendChild(msgElement);

    // Автоскролл если был внизу
    if (keep && autoscroll) {
      autoscroll();
    }

    // Обновляем observer для последнего чужого сообщения
    if (observeLastForeign) {
      observeLastForeign();
    }

    // Отмечаем как прочитанное если был внизу
    if (keep && markRead) {
      markRead(ts);
    }
  }

  /**
   * Показывает индикатор "печатает..."
   */
  let typingTimer = null;
  function showTyping() {
    if (!typingEl) return;
    
    typingEl.classList.remove('d-none');
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => {
      typingEl.classList.add('d-none');
    }, 2000);
  }

  /**
   * Обрабатывает входящие сообщения WebSocket
   */
  ws.addEventListener('message', (e) => {
    try {
      const data = JSON.parse(e.data);

      // Обработка события "печатает..."
      if (data.type === 'typing' && Number(data.user_id) !== Number(meId)) {
        showTyping();
        return;
      }

      // Обработка обычного сообщения
      const msg = data.payload || data.message || data;
      renderMessage(msg);
    } catch (err) {
      console.warn('ChatWebSocket: failed to parse message', err);
    }
  });

  /**
   * Обрабатывает закрытие соединения
   */
  ws.addEventListener('close', () => {
    console.log('ChatWebSocket: connection closed, reloading in 2s...');
    setTimeout(() => location.reload(), 2000);
  });

  /**
   * Обрабатывает ошибки WebSocket
   */
  ws.addEventListener('error', (err) => {
    console.error('ChatWebSocket: connection error', err);
  });

  /**
   * Обрабатывает отправку формы
   */
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    
    const text = (ta?.value || '').trim();
    if (!text || ws.readyState !== WebSocket.OPEN) return;

    // Отправка сообщения
    ws.send(JSON.stringify({ content: text }));

    // Очистка textarea
    ta.value = '';
    ta.dispatchEvent(new Event('input'));
  });

  /**
   * Обрабатывает ввод в textarea (индикация "печатает...")
   */
  let lastTyping = 0;
  ta?.addEventListener('input', () => {
    const now = Date.now();
    
    // Отправляем событие "печатает..." не чаще раз в 1.5 секунды
    if (ws.readyState === WebSocket.OPEN && now - lastTyping > 1500) {
      ws.send(JSON.stringify({ type: 'typing' }));
      lastTyping = now;
    }
  });

  /**
   * Начальный скролл при загрузке страницы
   */
  if (!window.__SCROLLED_ON_INIT__ && autoscroll) {
    autoscroll();
  }

  // API
  return {
    /**
     * Отправляет сообщение
     * @param {string} content - Текст сообщения
     */
    send: (content) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ content }));
      } else {
        console.warn('ChatWebSocket: connection not open');
      }
    },

    /**
     * Отправляет индикацию "печатает..."
     */
    sendTyping: () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'typing' }));
      }
    },

    /**
     * Закрывает WebSocket соединение
     */
    close: () => {
      ws.close();
    },

    /**
     * Рендерит сообщение (для внешнего использования)
     */
    renderMessage,

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
  window.initChatWebSocket = initChatWebSocket;
}

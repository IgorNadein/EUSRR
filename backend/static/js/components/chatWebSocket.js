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

// Храним активное соединение для предотвращения дубликатов
let activeWebSocket = null;
let lastOptions = null;

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
    markReadApi,
    bindFormSubmit = true
  } = options;

  // Проверка обязательных параметров
  if (!chatId || !meId) {
    console.warn('ChatWebSocket: chatId and meId are required');
    return null;
  }
  
  // Закрываем существующее соединение перед созданием нового
  if (activeWebSocket && activeWebSocket.readyState !== WebSocket.CLOSED) {
    console.log('ChatWebSocket: closing existing connection');
    activeWebSocket.close(1000, 'Reconnecting');
  }
  
  // Сохраняем опции для переподключения
  lastOptions = options;

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
  
  // Сохраняем активное соединение
  activeWebSocket = ws;
  
  // Настройки переподключения
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;

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

    // Сообщаем другим модулям о новом сообщении
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('chat:message-received', { detail: msg })
      );
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
   * Обрабатывает успешное подключение
   */
  ws.addEventListener('open', () => {
    console.log('ChatWebSocket: connection established');
    reconnectAttempts = 0; // Сбрасываем счетчик при успешном подключении
  });

  /**
   * Обрабатывает входящие сообщения WebSocket
   */
  ws.addEventListener('message', (e) => {
    try {
      const data = JSON.parse(e.data);

      // Обработка ping для keepalive (игнорируем)
      if (data.type === 'ping') {
        return;
      }

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
  ws.addEventListener('close', (event) => {
    console.log('ChatWebSocket: connection closed', event.code, event.reason);
    
    // Не переподключаемся если закрытие было нормальным (код 1000)
    if (event.code === 1000) {
      console.log('ChatWebSocket: normal closure, not reconnecting');
      return;
    }
    
    // Пробуем переподключиться
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++;
      console.log(`ChatWebSocket: reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
      
      setTimeout(() => {
        if (document.querySelector('[data-chat-ws]')) {
          console.log('ChatWebSocket: attempting to reconnect...');
          // Переинициализируем WebSocket с сохраненными опциями
          initChatWebSocket(lastOptions);
        }
      }, reconnectDelay);
    } else {
      console.warn('ChatWebSocket: max reconnect attempts reached');
      // Показываем уведомление пользователю вместо перезагрузки
      const notification = document.createElement('div');
      notification.className = 'alert alert-warning position-fixed bottom-0 start-50 translate-middle-x mb-3';
      notification.style.zIndex = '9999';
      notification.innerHTML = `
        <i class="bi-exclamation-triangle me-2"></i>
        Соединение с сервером потеряно. 
        <button class="btn btn-sm btn-link" onclick="location.reload()">Обновить страницу</button>
      `;
      document.body.appendChild(notification);
    }
  });

  /**
   * Обрабатывает ошибки WebSocket
   */
  ws.addEventListener('error', (err) => {
    console.error('ChatWebSocket: connection error', err);
    // Не перезагружаем страницу при ошибке - дожидаемся события 'close'
  });

  /**
   * Обрабатывает отправку формы
   */
  const handleFormSubmit = (e) => {
    e.preventDefault();
    
    const text = (ta?.value || '').trim();
    if (!text || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({ content: text }));
    ta.value = '';
    ta.dispatchEvent(new Event('input'));
  };

  if (bindFormSubmit && form) {
    form.addEventListener('submit', handleFormSubmit);
  }

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

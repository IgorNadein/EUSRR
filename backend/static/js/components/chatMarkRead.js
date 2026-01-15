/**
 * @fileoverview Chat Mark Read - Отметка прочитанных сообщений в чате
 * Включает автоскролл, разделитель "Новые сообщения", IntersectionObserver,
 * синхронизацию с localStorage и API
 * @module components/chatMarkRead
 */

import { getCookie } from '../utils/stringUtils.js';

/**
 * Инициализирует обработчик отметки прочитанных сообщений
 * @param {Object} options - Опции инициализации
 * @param {string} [options.scrollContainerId='chatScroll'] - ID контейнера скролла
 * @param {string} [options.textareaId='id_content'] - ID textarea для сообщений
 * @param {string} [options.formId='chatForm'] - ID формы отправки
 * @param {string} [options.scrollBtnId='scrollBtn'] - ID кнопки "вниз"
 * @param {number} options.chatId - ID чата
 * @param {number} options.meId - ID текущего пользователя
 * @param {string} [options.markReadUrl] - URL для отметки прочитанных (опционально)
 * @param {number} [options.initialLastReadTs] - Начальный timestamp последнего прочитанного
 * @returns {Object|null} API обработчика или null если элементы не найдены
 */
export function initChatMarkRead(options = {}) {
  console.log('[ChatMarkRead] Initializing with options:', options);
  
  const {
    scrollContainerId = 'chatScroll',
    textareaId = 'id_content',
    formId = 'chatForm',
    scrollBtnId = 'scrollBtn',
    chatId,
    meId,
    markReadUrl,
    initialLastReadTs
  } = options;

  // Проверка обязательных параметров
  if (!chatId || !meId) {
    console.warn('[ChatMarkRead] chatId and meId are required', { chatId, meId });
    return null;
  }

  // Получение элементов
  const box = document.getElementById(scrollContainerId);
  if (!box) {
    console.warn(`[ChatMarkRead] element #${scrollContainerId} not found`);
    return null;
  }
  
  // Установка data-me-id для markVisibleMessagesAsRead
  box.dataset.meId = String(meId);
  console.log('[ChatMarkRead] Set data-me-id on chatScroll:', box.dataset.meId);

  const ta = document.getElementById(textareaId);
  const form = document.getElementById(formId);
  const btn = document.getElementById(scrollBtnId);

  const csrf = getCookie('csrftoken');
  const LS_KEY = `chat:lastRead:${chatId}`;

  /**
   * Получает timestamp последнего прочитанного из localStorage
   */
  function getLocalLastReadTs() {
    const v = localStorage.getItem(LS_KEY);
    return v ? Number(v) : NaN;
  }

  /**
   * Сохраняет timestamp последнего прочитанного в localStorage
   */
  function setLocalLastReadTs(ts) {
    localStorage.setItem(LS_KEY, String(ts));
  }

  /**
   * Инициализирует последний прочитанный timestamp
   */
  function initLastRead() {
    let lastRead = initialLastReadTs || Number(box.dataset.lastReadTs || NaN);
    if (!Number.isFinite(lastRead)) {
      const ls = getLocalLastReadTs();
      if (Number.isFinite(ls)) lastRead = ls;
    }
    if (Number.isFinite(lastRead)) {
      box.dataset.lastReadTs = String(lastRead);
    }
  }
  initLastRead();

  let lastMarkedTs = Number(box.dataset.lastReadTs || 0);

  /**
   * Проверяет, находится ли скролл внизу
   */
  function atBottom() {
    return (box.scrollHeight - box.scrollTop - box.clientHeight) < 60;
  }

  /**
   * Скроллит вниз без анимации
   * ВНИМАНИЕ: Используется только для кнопки "вниз" и при вводе текста
   * НЕ используется при инициализации!
   */
  function autoscroll() {
    const prev = box.style.scrollBehavior;
    box.style.scrollBehavior = 'auto';
    box.scrollTop = box.scrollHeight;
    if (prev) {
      box.style.scrollBehavior = prev;
    } else {
      box.style.removeProperty('scroll-behavior');
    }
  }

  /**
   * Переключает видимость кнопки "вниз"
   */
  function toggleBtn() {
    btn?.classList.toggle('show', !atBottom());
  }

  /**
   * Создаёт разделитель (divider)
   */
  function makeDivider(cls, text) {
    const div = document.createElement('div');
    div.className = cls;
    div.setAttribute('role', 'separator');
    div.setAttribute('aria-label', text);
    div.innerHTML = `<span>${text}</span>`;
    return div;
  }

  /**
   * Находит первое непрочитанное сообщение
   */
  function findUnreadTarget() {
    const id = window.__FIRST_UNREAD_ID__;
    const ts = window.__UNREAD_FROM_TS__;
    const lastReadTs = Number(box.dataset.lastReadTs || NaN);

    // 1. Поиск по ID
    if (id != null) {
      const el = box.querySelector(`.msg[data-id="${id}"]`);
      if (el) return el;
    }

    // 2. Поиск по timestamp из window
    if (Number.isFinite(ts)) {
      const items = Array.from(box.querySelectorAll('.msg[data-ts]'));
      const el = items.find(e => Number(e.dataset.ts) >= Number(ts));
      if (el) return el;
    }

    // 3. Поиск по lastReadTs из dataset
    if (Number.isFinite(lastReadTs)) {
      const items = Array.from(box.querySelectorAll('.msg[data-ts][data-author-id]'));
      return items.find(e => 
        Number(e.dataset.ts) > lastReadTs && 
        Number(e.dataset.authorId) !== meId
      ) || null;
    }

    return null;
  }

  /**
   * Вставляет разделитель "Новые сообщения"
   */
  function insertUnreadDivider() {
    if (!box || box.querySelector('.unread-divider')) return null;
    
    const target = findUnreadTarget();
    if (target) {
      const div = makeDivider('unread-divider', 'Новые сообщения');
      target.parentNode.insertBefore(div, target);
      return div;
    }
    return null;
  }

  /**
   * Удаляет разделитель "Новые сообщения"
   */
  function removeUnreadDivider() {
    const d = box.querySelector('.unread-divider');
    if (d) d.remove();
  }

  /**
   * Отмечает сообщения как прочитанные до указанного timestamp
   * @param {number} ts - Timestamp последнего прочитанного сообщения
   */
  async function markRead(ts) {
    ts = Number(ts);
    console.log('[ChatMarkRead] markRead called:', { ts, lastMarkedTs, isFinite: Number.isFinite(ts), willSkip: !Number.isFinite(ts) || ts <= lastMarkedTs });
    
    if (!Number.isFinite(ts) || ts <= lastMarkedTs) {
      console.log('[ChatMarkRead] Skipping markRead - invalid or already marked');
      return;
    }

    lastMarkedTs = ts;
    setLocalLastReadTs(ts);
    box.dataset.lastReadTs = String(ts);
    removeUnreadDivider();
    
    console.log('[ChatMarkRead] Updated local state:', { lastMarkedTs, localStorage: getLocalLastReadTs(), dataset: box.dataset.lastReadTs });

    // Определение URL для отметки
    let url = markReadUrl;
    if (!url) {
      const base = location.pathname.endsWith("/") 
        ? location.pathname 
        : (location.pathname + "/");
      url = base + "mark-read/";
    }
    
    console.log('[ChatMarkRead] Sending mark-read request:', { url, chatId, upto_ts: ts });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json'
        },
        body: new URLSearchParams({ upto_ts: String(ts) }),
        credentials: 'same-origin'
      });
      
      const data = await response.json();
      console.log('[ChatMarkRead] mark-read response:', { status: response.status, data });

      // Отправляем событие для обновления глобального бейджа
      window.dispatchEvent(new CustomEvent('chat:read', {
        detail: { chatId: String(chatId) }
      }));
    } catch (err) {
      console.error('[ChatMarkRead] Failed to mark as read:', err);
    }
  }

  /**
   * Автоматически изменяет высоту textarea
   * DEPRECATED: теперь используется универсальный модуль textareaAutoExpand.js
   * Оставлено для совместимости с autoscroll
   */
  function autosize() {
    if (!ta) return;
    // Авторасширение теперь обрабатывается textareaAutoExpand.js
    // Оставляем только autoscroll логику
    if (atBottom()) autoscroll();
  }

  /**
   * Настраивает IntersectionObserver для автоматической отметки
   */
  const io = new IntersectionObserver((entries) => {
    entries.forEach(en => {
      if (en.isIntersecting) {
        const el = en.target.closest('.msg');
        if (!el) return;
        const ts = Number(el.dataset.ts || 0);
        markRead(ts);
      }
    });
  }, { root: box, threshold: 1.0 });

  /**
   * Наблюдает за последним чужим сообщением
   */
  function observeLastForeign() {
    io.disconnect();
    const msgs = Array.from(box.querySelectorAll('.msg[data-ts][data-author-id]'));
    const lastForeign = [...msgs].reverse().find(e => 
      Number(e.dataset.authorId) !== meId
    );
    
    if (lastForeign) {
      const bubble = lastForeign.querySelector('.bubble') || lastForeign;
      io.observe(bubble);
    }
  }

  // Инициализация
  const mark = insertUnreadDivider();
  
  // ВАЖНО: НЕ скроллим при инициализации!
  // Прокрутка управляется из handleInitialMessages в userWebSocket.js
  // Здесь только инициализируем UI состояние
  requestAnimationFrame(() => {
    autosize();
    toggleBtn();
    window.__SCROLLED_ON_INIT__ = true;
  });

  // События textarea
  ta?.addEventListener('input', autosize);
  ta?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      // Enter без Shift - отправка сообщения
      e.preventDefault();
      form?.requestSubmit();
    }
    // Shift+Enter - перенос строки (стандартное поведение)
  });

  // События скролла
  box.addEventListener('scroll', toggleBtn);
  btn?.addEventListener('click', autoscroll);

  // Наблюдение за последним чужим сообщением
  observeLastForeign();

  // Отметка при достижении низа
  let bottomTimer = null;
  box.addEventListener('scroll', () => {
    clearTimeout(bottomTimer);
    if (atBottom()) {
      bottomTimer = setTimeout(() => {
        const lastMsg = box.querySelector('.msg:last-of-type');
        const ts = lastMsg ? Number(lastMsg.dataset.ts || 0) : 0;
        markRead(ts);
      }, 300);
    }
  });

  // API
  const api = {
    markRead,
    observeLastForeign,
    autoscroll,
    atBottom,
    destroy: () => {
      io.disconnect();
      clearTimeout(bottomTimer);
      ta?.removeEventListener('input', autosize);
      box.removeEventListener('scroll', toggleBtn);
      btn?.removeEventListener('click', autoscroll);
    }
  };

  // Переподключение observer при добавлении новых сообщений
  window.addEventListener('ws:new-message', () => {
    observeLastForeign();
  });
  
  // Синхронизация lastMarkedTs через WebSocket (между вкладками)
  window.addEventListener('ws:marked-read', (e) => {
    const { chat_id, last_read_at, last_read_message_id } = e.detail;
    
    if (chat_id !== chatId) return;
    
    console.log('[ChatMarkRead] Received marked_read event:', { chat_id, last_read_at, last_read_message_id });
    
    // Парсим timestamp из ISO строки
    const newTimestamp = last_read_at ? new Date(last_read_at).getTime() : 0;
    
    // Обновляем локальное состояние только если новее
    if (newTimestamp > lastMarkedTs) {
      lastMarkedTs = newTimestamp;
      localStorage.setItem(lsKey, String(lastMarkedTs));
      console.log('[ChatMarkRead] Updated lastMarkedTs from WebSocket:', lastMarkedTs);
    }
  });

  // Экспорт в window для совместимости
  window.__CHAT_MARK_READ__ = api;

  return api;
}

// Публикуем в window
if (typeof window !== 'undefined') {
  window.initChatMarkRead = initChatMarkRead;
}

/**
 * Функция инициализации отметки для видимых сообщений
 * Вызывается после загрузки и рендеринга начальных сообщений
 */
export function markVisibleMessagesAsRead() {
  console.log('[ChatMarkRead] markVisibleMessagesAsRead called');
  
  const api = window.__CHAT_MARK_READ__;
  if (!api) {
    console.warn('[ChatMarkRead] API not initialized, cannot mark visible');
    return;
  }

  const box = document.getElementById('chatScroll');
  const meId = Number(box?.dataset.meId || 0);
  
  console.log('[ChatMarkRead] markVisible: checking elements', { box: !!box, meId });
  
  if (!box || !meId) {
    console.warn('[ChatMarkRead] Missing chatScroll or meId');
    return;
  }

  const msgs = Array.from(box.querySelectorAll('.msg[data-ts][data-author-id]'));
  console.log('[ChatMarkRead] markVisible: found messages', msgs.length);
  
  const boxRect = box.getBoundingClientRect();
  console.log('[ChatMarkRead] markVisible: viewport', { top: boxRect.top, bottom: boxRect.bottom, height: boxRect.height });
  
  let foreignCount = 0;
  const visibleForeignMsgs = msgs.filter(msg => {
    const authorId = Number(msg.dataset.authorId);
    if (authorId === meId) return false; // Пропускаем свои сообщения
    
    foreignCount++;
    const rect = msg.getBoundingClientRect();
    // Проверяем пересечение: сообщение видимо, если хотя бы частично во viewport
    const isVisible = rect.bottom > boxRect.top && rect.top < boxRect.bottom;
    
    console.log('[ChatMarkRead] markVisible: checking message', {
      messageId: msg.dataset.messageId || msg.dataset.id,
      authorId,
      rect: { top: Math.round(rect.top), bottom: Math.round(rect.bottom) },
      viewport: { top: Math.round(boxRect.top), bottom: Math.round(boxRect.bottom) },
      isVisible
    });
    
    return isVisible;
  });
  
  console.log('[ChatMarkRead] markVisible: foreign/visible', { foreignCount, visibleCount: visibleForeignMsgs.length });
  
  if (visibleForeignMsgs.length > 0) {
    // Используем ТЕКУЩЕЕ время, а не timestamp сообщения
    // (timestamp сообщения может быть из прошлого)
    const ts = Date.now();
    const newestVisible = visibleForeignMsgs[visibleForeignMsgs.length - 1];
    console.log('[ChatMarkRead] Initial mark-read for visible messages:', { 
      messageId: newestVisible.dataset.id, 
      messageCreatedAt: newestVisible.dataset.ts,
      usingCurrentTime: ts 
    });
    api.markRead(ts);
  } else {
    console.log('[ChatMarkRead] markVisible: no visible foreign messages to mark');
  }
}

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
  
  // In-memory кэш (как в Telegram Web)
  // Быстрая синхронная проверка перед отправкой HTTP
  window._chatLastRead = window._chatLastRead || {};
  
  // Debounce для markRead
  let markReadTimer = null;
  let pendingMarkTs = 0;
  
  // Флаг активного запроса (дедупликация)
  let readPromise = null;
  
  // Отслеживание текущего наблюдаемого элемента
  let currentObservedBubble = null;

  /**
   * Получает timestamp последнего прочитанного из кэша/localStorage
   * Как в Telegram Web: сначала проверяем память, потом localStorage
   */
  function getLocalLastReadTs() {
    // 1. Проверяем in-memory кэш (синхронно, быстро)
    const cached = window._chatLastRead[chatId];
    if (cached && Number.isFinite(cached)) return cached;
    
    // 2. Fallback: localStorage
    const v = localStorage.getItem(LS_KEY);
    return v ? Number(v) : NaN;
  }

  /**
   * Сохраняет timestamp последнего прочитанного в кэш + localStorage
   * Как в Telegram Web: двухуровневое хранение
   */
  function setLocalLastReadTs(ts) {
    // 1. Сохраняем в memory (синхронно, мгновенно)
    window._chatLastRead[chatId] = ts;
    
    // 2. Сохраняем в localStorage (персистентно)
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
   * Находит первое непрочитанное ЧУЖОЕ сообщение для divider
   * (свои сообщения отмечаются, но не показывают divider)
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
   * Отмечает сообщения как прочитанные до указанного timestamp (с debounce)
   * @param {number} ts - Timestamp последнего прочитанного сообщения
   */
  function markReadDebounced(ts) {
    ts = Number(ts);
    if (!Number.isFinite(ts)) {
      console.log('[ChatMarkRead] markReadDebounced: invalid ts', ts);
      return;
    }
    
    // Сохраняем максимальный timestamp
    pendingMarkTs = Math.max(pendingMarkTs, ts);
    
    clearTimeout(markReadTimer);
    markReadTimer = setTimeout(() => {
      if (pendingMarkTs > lastMarkedTs) {
        markRead(pendingMarkTs);
        pendingMarkTs = 0;
      }
    }, 500);
  }
  
  /**
   * Отмечает сообщения как прочитанные до указанного timestamp
   * Как в Telegram Web: проверяем кэш перед отправкой HTTP
   * @param {number} ts - Timestamp последнего прочитанного сообщения
   */
  async function markRead(ts) {
    ts = Number(ts);
    const cachedTs = getLocalLastReadTs();
    
    console.log('[ChatMarkRead] markRead called:', { 
      ts, 
      lastMarkedTs, 
      cachedTs,
      isFinite: Number.isFinite(ts), 
      willSkip: !Number.isFinite(ts) || ts <= lastMarkedTs || ts <= cachedTs
    });
    
    // ПРОВЕРКА 1: Валидность
    if (!Number.isFinite(ts)) {
      console.log('[ChatMarkRead] Skipping - invalid timestamp');
      return;
    }
    
    // ПРОВЕРКА 2: Уже отметили локально?
    if (ts <= lastMarkedTs) {
      console.log('[ChatMarkRead] Skipping - already marked locally');
      return;
    }
    
    // ПРОВЕРКА 3: Кэш показывает что уже прочитано? (как в Telegram Web)
    if (Number.isFinite(cachedTs) && ts <= cachedTs) {
      console.log('[ChatMarkRead] Skipping - already marked in cache:', cachedTs);
      return;
    }
    
    // ПРОВЕРКА 4: Уже идёт запрос? (дедупликация)
    if (readPromise) {
      console.log('[ChatMarkRead] Skipping - request already in progress');
      return readPromise;
    }

    // Оптимистичное обновление (как в Telegram Web)
    // Обновляем UI сразу, до ответа от сервера
    lastMarkedTs = ts;
    setLocalLastReadTs(ts); // → window._chatLastRead + localStorage
    box.dataset.lastReadTs = String(ts);
    removeUnreadDivider();
    
    console.log('[ChatMarkRead] Optimistic update:', { 
      lastMarkedTs, 
      memoryCache: window._chatLastRead[chatId],
      localStorage: localStorage.getItem(LS_KEY),
      dataset: box.dataset.lastReadTs 
    });

    // Определение URL для отметки
    let url = markReadUrl;
    if (!url) {
      const base = location.pathname.endsWith("/") 
        ? location.pathname 
        : (location.pathname + "/");
      url = base + "mark-read/";
    }
    
    console.log('[ChatMarkRead] Sending HTTP mark-read:', { url, chatId, upto_ts: ts });

    // HTTP запрос для гарантированной доставки (как в Telegram Web)
    // WebSocket только для получения уведомлений, не для отправки
    try {
      // Сохраняем Promise для дедупликации
      readPromise = fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json'
        },
        body: new URLSearchParams({ upto_ts: String(ts) }),
        credentials: 'same-origin'
      });
      
      const response = await readPromise;
      
      const data = await response.json();
      console.log('[ChatMarkRead] HTTP mark-read response:', { status: response.status, data });

      // Отправляем событие для обновления глобального бейджа
      window.dispatchEvent(new CustomEvent('chat:read', {
        detail: { chatId: String(chatId) }
      }));
    } catch (err) {
      console.error('[ChatMarkRead] HTTP mark-read failed:', err);
    } finally {
      // Освобождаем флаг для новых запросов
      readPromise = null;
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
        markReadDebounced(ts);
      }
    });
  }, { root: box, threshold: 1.0 });

  /**
   * Наблюдает за последним сообщением (любым - своим или чужим)
   * Как в Telegram Web: отмечаем все видимые сообщения, включая собственные
   */
  function observeLastMessage() {
    const msgs = Array.from(box.querySelectorAll('.msg[data-ts][data-author-id]'));
    
    // Берем последнее ЛЮБОЕ сообщение (не только чужое)
    const lastMsg = msgs.length > 0 ? msgs[msgs.length - 1] : null;
    
    if (!lastMsg) return;
    
    const bubble = lastMsg.querySelector('.bubble') || lastMsg;
    
    // Проверяем, нужно ли обновлять observer
    if (currentObservedBubble === bubble) {
      return; // Уже наблюдаем за этим элементом
    }
    
    // Отключаем только предыдущий элемент
    if (currentObservedBubble) {
      io.unobserve(currentObservedBubble);
    }
    
    io.observe(bubble);
    currentObservedBubble = bubble;
    console.log('[ChatMarkRead] Observer updated to last message:', lastMsg.dataset.id);
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

  // Наблюдение за последним сообщением (любым - своим или чужим)
  observeLastMessage();

  // API
  const api = {
    markRead,
    markReadDebounced,
    observeLastMessage,
    autoscroll,
    atBottom,
    destroy: () => {
      io.disconnect();
      clearTimeout(markReadTimer);
      ta?.removeEventListener('input', autosize);
      box.removeEventListener('scroll', toggleBtn);
      btn?.removeEventListener('click', autoscroll);
    }
  };

  // Переподключение observer при добавлении новых сообщений
  window.addEventListener('ws:new-message', () => {
    observeLastMessage();
  });
  
  // Синхронизация через WebSocket (как в Telegram Web)
  // WebSocket получает уведомления от других устройств/вкладок
  window.addEventListener('ws:marked-read', (e) => {
    const { chat_id, last_read_at, last_read_message_id } = e.detail;
    
    if (chat_id !== chatId) return;
    
    console.log('[ChatMarkRead] Received WS marked_read:', { chat_id, last_read_at, last_read_message_id });
    
    // Парсим timestamp из ISO строки
    const remoteTs = last_read_at ? new Date(last_read_at).getTime() : 0;
    const localTs = getLocalLastReadTs();
    
    console.log('[ChatMarkRead] WS sync check:', { remoteTs, localTs, willSync: remoteTs > localTs });
    
    // Комбинированный подход (как в Telegram Web):
    // Если удалённый timestamp НОВЕЕ локального → отправляем HTTP для гарантии
    if (Number.isFinite(remoteTs) && remoteTs > localTs) {
      console.log('[ChatMarkRead] WS sync: remote is newer, syncing...');
      
      // Обновляем локальный кэш оптимистично
      lastMarkedTs = remoteTs;
      setLocalLastReadTs(remoteTs);
      box.dataset.lastReadTs = String(remoteTs);
      removeUnreadDivider();
      
      // Отправляем HTTP запрос для гарантии синхронизации с сервером
      // (на случай если другая вкладка не успела отправить или был disconnect)
      markRead(remoteTs);
    } else {
      console.log('[ChatMarkRead] WS sync: local is up-to-date, skipping');
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
  
  // Находим ВСЕ видимые сообщения (включая свои)
  const visibleMsgs = msgs.filter(msg => {
    const rect = msg.getBoundingClientRect();
    const isVisible = rect.bottom > boxRect.top && rect.top < boxRect.bottom;
    
    console.log('[ChatMarkRead] markVisible: checking message', {
      messageId: msg.dataset.id,
      authorId: msg.dataset.authorId,
      rect: { top: Math.round(rect.top), bottom: Math.round(rect.bottom) },
      viewport: { top: Math.round(boxRect.top), bottom: Math.round(boxRect.bottom) },
      isVisible
    });
    
    return isVisible;
  });
  
  console.log('[ChatMarkRead] markVisible: visible messages', visibleMsgs.length);
  
  if (visibleMsgs.length > 0) {
    // Отмечаем последнее видимое сообщение (даже если оно свое)
    const newestVisible = visibleMsgs[visibleMsgs.length - 1];
    const ts = Number(newestVisible.dataset.ts);
    console.log('[ChatMarkRead] Initial mark-read for visible messages:', { 
      messageId: newestVisible.dataset.id,
      authorId: newestVisible.dataset.authorId,
      isOwn: Number(newestVisible.dataset.authorId) === meId,
      messageTimestamp: ts
    });
    api.markRead(ts);
  } else {
    console.log('[ChatMarkRead] markVisible: no visible messages to mark');
  }
}

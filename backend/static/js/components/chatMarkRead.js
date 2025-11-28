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
    console.warn('ChatMarkRead: chatId and meId are required');
    return null;
  }

  // Получение элементов
  const box = document.getElementById(scrollContainerId);
  if (!box) {
    console.warn(`ChatMarkRead: element #${scrollContainerId} not found`);
    return null;
  }

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
    if (!Number.isFinite(ts) || ts <= lastMarkedTs) return;

    lastMarkedTs = ts;
    setLocalLastReadTs(ts);
    box.dataset.lastReadTs = String(ts);
    removeUnreadDivider();

    // Определение URL для отметки
    let url = markReadUrl;
    if (!url) {
      const base = location.pathname.endsWith("/") 
        ? location.pathname 
        : (location.pathname + "/");
      url = base + "mark-read/";
    }

    try {
      await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json'
        },
        body: new URLSearchParams({ upto_ts: String(ts) }),
        credentials: 'same-origin'
      });

      // Отправляем событие для обновления глобального бейджа
      window.dispatchEvent(new CustomEvent('chat:read', {
        detail: { chatId: String(chatId) }
      }));
    } catch (err) {
      console.warn('ChatMarkRead: failed to mark as read', err);
    }
  }

  /**
   * Автоматически изменяет высоту textarea
   */
  function autosize() {
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 6 * 24) + 'px';
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
  requestAnimationFrame(() => {
    if (mark) {
      mark.scrollIntoView({ block: 'center' });
    } else {
      autoscroll();
    }
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

  // Экспорт в window для совместимости
  window.__CHAT_MARK_READ__ = api;

  return api;
}

// Публикуем в window
if (typeof window !== 'undefined') {
  window.initChatMarkRead = initChatMarkRead;
}

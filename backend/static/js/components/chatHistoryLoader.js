import {
  createMessageElement,
  createDayDivider,
  formatDay,
  toTimestamp
} from './chatMessageTemplates.js';

const DEFAULT_CONFIG = {
  scrollSelector: '#chatScroll',
  loaderSelector: '[data-history-loader]',
  triggerThreshold: 140,
  pageSize: 30
};

function parseBool(value) {
  if (typeof value === 'boolean') return value;
  return value === '1' || value === 'true';
}

function getAvatarMapSnapshot() {
  if (window?.chatAvatarMap?.getAll) {
    return window.chatAvatarMap.getAll();
  }
  if (window?.__CHAT_AVATARS__) {
    return { ...window.__CHAT_AVATARS__ };
  }
  return {};
}

function updateOldestDataset(scrollEl) {
  const firstMsg = scrollEl.querySelector('.msg[data-id]');
  if (!firstMsg) {
    scrollEl.dataset.oldestId = '';
    scrollEl.dataset.oldestTs = '';
    return null;
  }
  scrollEl.dataset.oldestId = String(firstMsg.dataset.id || '');
  scrollEl.dataset.oldestTs = String(firstMsg.dataset.ts || '');
  return firstMsg;
}

function ensureLoader(scrollEl, selector) {
  let loader = scrollEl.querySelector(selector);
  if (!loader) {
    loader = document.createElement('div');
    loader.className = 'history-loader d-none';
    loader.setAttribute('data-history-loader', '1');
    loader.innerHTML = `
      <div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div>
      <span class="small">Загружаем ранние сообщения…</span>
    `;
    scrollEl.prepend(loader);
  }
  return loader;
}

export function initChatHistoryLoader(options = {}) {
  const config = { ...DEFAULT_CONFIG, ...options };
  const scrollEl = document.querySelector(config.scrollSelector);
  if (!scrollEl) return null;

  const fetchUrl = scrollEl.dataset.fetchUrl;
  if (!fetchUrl) return null;

  const loaderEl = ensureLoader(scrollEl, config.loaderSelector);
  const meId = Number(scrollEl.dataset.meId || 0);
  const profileUrl = scrollEl.dataset.profileUrl || '/employees/profile/';
  const detailUrlTemplate = scrollEl.dataset.detailUrlTemplate || '/employees/0/';
  const avatarMap = getAvatarMapSnapshot();

  const state = {
    loading: false,
    hasMore: parseBool(scrollEl.dataset.hasMore || false),
    oldestId: (() => {
      const raw = scrollEl.dataset.oldestId;
      if (!raw || raw === 'None') return null;
      return raw;
    })(),
    fetchUrl,
    limit: Number(scrollEl.dataset.pageSize || config.pageSize) || config.pageSize
  };

  function showLoader() {
    loaderEl.classList.remove('d-none');
  }

  function hideLoader() {
    loaderEl.classList.add('d-none');
  }

  function dedupeDayDividers(scrollEl) {
    const dividerEls = scrollEl.querySelectorAll('.day-divider');
    let lastLabel = null;
    dividerEls.forEach((divider) => {
      const label = divider.textContent.trim();
      if (label === lastLabel) {
        divider.remove();
      } else {
        lastLabel = label;
      }
    });
  }

  function prependMessages(messages = [], ctx) {
    if (!messages.length) {
      return;
    }

    const {
      scrollEl,
      loaderEl,
      meId,
      profileUrl,
      detailUrlTemplate,
      avatarMap,
      state
    } = ctx;

    const prevHeight = scrollEl.scrollHeight;
    const fragment = document.createDocumentFragment();
    let prevDay = null;

    messages.forEach((msg) => {
      const ts = toTimestamp(msg);
      const day = msg.day || formatDay(ts);

      if (day !== prevDay) {
        fragment.appendChild(createDayDivider(day));
      }
      prevDay = day;

      const element = createMessageElement(msg, {
        meId,
        profileUrl,
        detailUrlTemplate,
        avatarMap
      });
      element.classList.remove('message-pending', 'message-pending--resolved');
      fragment.appendChild(element);
    });

    const anchor = loaderEl.nextSibling || scrollEl.firstChild;
    scrollEl.insertBefore(fragment, anchor);

    const delta = scrollEl.scrollHeight - prevHeight;
    scrollEl.scrollTop += delta;

    dedupeDayDividers(scrollEl);

    const firstMsg = updateOldestDataset(scrollEl);
    if (firstMsg) {
      state.oldestId = firstMsg.dataset.id;
    }
  }

  async function loadMore() {
    if (state.loading || !state.hasMore || !state.oldestId) {
      return;
    }

    state.loading = true;
    showLoader();

    try {
      const url = new URL(state.fetchUrl, window.location.origin);
      url.searchParams.set('limit', String(state.limit));
      url.searchParams.set('before_id', state.oldestId);

      const response = await fetch(url.toString(), {
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin'
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || 'Не удалось загрузить сообщения');
      }

      if (Array.isArray(payload.messages) && payload.messages.length) {
        prependMessages(payload.messages, {
          scrollEl,
          loaderEl,
          meId,
          profileUrl,
          detailUrlTemplate,
          avatarMap,
          state
        });
        state.oldestId = String(payload.messages[0].id);
      } else if (payload.next_before_id) {
        state.oldestId = String(payload.next_before_id);
      } else {
        state.oldestId = null;
      }

      state.hasMore = Boolean(payload.has_more);
      scrollEl.dataset.hasMore = state.hasMore ? '1' : '0';

    } catch (error) {
      console.error('ChatHistoryLoader: history request failed', error);
    } finally {
      state.loading = false;
      hideLoader();
    }
  }

  function handleScroll() {
    if (!state.hasMore || state.loading) {
      return;
    }
    if (scrollEl.scrollTop <= config.triggerThreshold) {
      loadMore();
    }
  }

  scrollEl.addEventListener('scroll', handleScroll, { passive: true });

  if (!state.hasMore) {
    hideLoader();
  } else if (scrollEl.scrollHeight <= scrollEl.clientHeight + config.triggerThreshold) {
    // Если сообщений мало и страница «короткая», сразу догружаем ещё
    loadMore();
  }

  return {
    loadMore,
    hasMore: () => state.hasMore
  };
}

// УДАЛЕНО: Авто-инициализация теперь происходит через chat_detail_scripts.html
// if (document.readyState === 'loading') {
//   document.addEventListener('DOMContentLoaded', () => initChatHistoryLoader());
// } else {
//   initChatHistoryLoader();
// }

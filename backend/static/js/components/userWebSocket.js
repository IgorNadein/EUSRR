/**
 * @fileoverview User WebSocket - единое WebSocket соединение для пользователя
 * Обрабатывает все real-time обновления:
 * - Чаты и сообщения
 * - Уведомления
 * - Бейджи в sidebar
 * - Онлайн-статус
 * - Календарь и другие события
 * @module components/userWebSocket
 */

import { getChatAvatar } from './chatAvatarMap.js';

/**
 * Инициализирует WebSocket соединение для пользователя
 * @param {Object} options - Опции инициализации
 * @param {number} options.userId - ID текущего пользователя
 * @param {string} [options.scrollContainerId='chatScroll'] - ID контейнера скролла (если открыт чат)
 * @param {string} [options.formId='chatForm'] - ID формы отправки (если открыт чат)
 * @param {string} [options.textareaId='id_content'] - ID textarea (если открыт чат)
 * @param {string} [options.typingIndicatorId='typing'] - ID индикатора "печатает..." (если открыт чат)
 * @param {Object} [options.avatarMap] - Карта аватаров пользователей
 * @param {Object} [options.markReadApi] - API из chatMarkRead для интеграции
 * @param {Object} [options.badgeManager] - Менеджер бейджей для обновления счетчиков
 * @param {Function} [options.onListUpdate] - Callback для обновления списка чатов
 * @param {Function} [options.onNotification] - Callback для уведомлений (будущее)
 * @returns {Object} API WebSocket
 */

let activeConnection = null;

export function initUserWebSocket(options = {}) {
  const {
    userId,
    scrollContainerId = 'chatScroll',
    formId = 'chatForm',
    textareaId = 'id_content',
    typingIndicatorId = 'typing',
    avatarMap = {},
    markReadApi,
    badgeManager,
    onListUpdate
  } = options;

  if (!userId) {
    console.warn('[UserWS] userId is required');
    return null;
  }

  // Закрываем существующее соединение
  if (activeConnection) {
    console.log('[UserWS] Closing existing connection');
    activeConnection.close(1000, 'Reconnecting');
  }

  // Состояние
  const state = {
    activeChatId: null,
    scrollEl: null,
    form: null,
    textarea: null,
    typingEl: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 3000,
    typingTimeout: null,
    lastTypingSent: 0,
    typingThrottle: 3000
  };

  // Создание WebSocket соединения
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${location.host}/ws/`;
  const ws = new WebSocket(wsUrl);

  activeConnection = ws;

  console.log('[UserWS] Connecting to', wsUrl);

  // ==================== WebSocket события ====================

  ws.onopen = () => {
    console.log('[UserWS] Connected');
    state.reconnectAttempts = 0;

    // Если есть активный чат на странице, открываем его
    const currentChatId = detectCurrentChatId();
    if (currentChatId) {
      openChat(currentChatId, true);
    }
  };

  ws.onclose = (event) => {
    console.log('[UserWS] Disconnected', event.code, event.reason);
    
    if (event.code !== 1000 && state.reconnectAttempts < state.maxReconnectAttempts) {
      state.reconnectAttempts++;
      console.log(`[UserWS] Reconnecting attempt ${state.reconnectAttempts}...`);
      setTimeout(() => {
        initUserWebSocket(options);
      }, state.reconnectDelay);
    }
  };

  ws.onerror = (error) => {
    console.error('[UserWS] Error:', error);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleMessage(data);
    } catch (err) {
      console.error('[UserWS] Failed to parse message:', err);
    }
  };

  // ==================== Обработка входящих сообщений ====================

  function handleMessage(data) {
    const { type } = data;
    
    console.log('[UserWebSocket] Received message:', type, data);

    switch (type) {
      case 'ping':
        // Keepalive - просто логируем
        break;

      case 'chat_opened':
        console.log('[UserWS] Chat opened:', data.chat_id);
        break;

      case 'chat_closed':
        console.log('[UserWS] Chat closed:', data.chat_id);
        break;

      case 'initial_messages':
        handleInitialMessages(data);
        break;

      case 'new_message':
        handleNewMessage(data);
        break;

      case 'message_updated':
        handleMessageUpdated(data);
        break;

      case 'message_deleted':
        console.log('[UserWebSocket] Handling message_deleted event');
        handleMessageDeleted(data);
        break;

      case 'list_update':
        handleListUpdate(data);
        break;

      case 'message_edited':
        handleMessageEditedInList(data);
        break;

      case 'reaction_added':
        handleReactionAdded(data);
        break;

      case 'reaction_removed':
        handleReactionRemoved(data);
        break;

      case 'typing_start':
        handleTypingStart(data);
        break;

      case 'typing_stop':
        handleTypingStop(data);
        break;

      case 'poll_vote':
      case 'poll_update':
        handlePollUpdate(data);
        break;

      case 'error':
        console.error('[UserWS] Server error:', data.error);
        break;

      default:
        console.warn('[UserWS] Unknown message type:', type);
    }
  }

  // ==================== Управление активным чатом ====================

  function detectCurrentChatId() {
    // Определяем ID чата из DOM (если мы на странице чата)
    const scrollEl = document.getElementById(scrollContainerId);
    if (scrollEl) {
      const chatId = scrollEl.dataset.chatId;
      if (chatId) {
        return parseInt(chatId);
      }
    }
    return null;
  }

  function openChat(chatId, loadHistory = false) {
    console.log('[UserWS] Opening chat:', chatId);
    
    state.activeChatId = chatId;
    
    // Получаем элементы
    state.scrollEl = document.getElementById(scrollContainerId);
    state.form = document.getElementById(formId);
    state.textarea = document.getElementById(textareaId);
    state.typingEl = document.getElementById(typingIndicatorId);

    // Отправляем на сервер
    send({
      action: 'open_chat',
      chat_id: chatId,
      load_history: loadHistory
    });

    // ОТКЛЮЧЕНО: Форма теперь обрабатывается chatComposer.js
    // initChatFormHandlers() больше не используется
  }

  function closeChat(chatId) {
    console.log('[UserWS] Closing chat:', chatId);
    
    send({
      action: 'close_chat',
      chat_id: chatId
    });

    state.activeChatId = null;
    state.scrollEl = null;
    state.form = null;
    state.textarea = null;
    state.typingEl = null;
  }

  // ==================== Обработчики событий чата ====================

  function handleInitialMessages(data) {
    if (!state.scrollEl) return;

    const { messages } = data;
    
    // Убираем индикатор загрузки независимо от наличия сообщений
    const loader = document.getElementById('initialLoader');
    if (loader) {
      loader.remove();
    }
    
    console.log('[UserWS] Dispatching ws:initial-messages with %d messages', messages?.length || 0);
    
    // НОВАЯ АРХИТЕКТУРА: Dispatch события вместо прямого вызова renderer
    // ChatController подпишется на это событие и обработает через MessageLoader
    window.dispatchEvent(new CustomEvent('ws:initial-messages', {
      detail: {
        messages: messages || [],
        chatId: state.activeChatId
      }
    }));
    
    // УСТАРЕВШЕЕ: Старая логика с messageRenderer остается для backward compatibility
    // Удалится после полной миграции на ChatController
    if (options.messageRenderer && messages?.length) {
      console.log('[UserWS] [DEPRECATED] Using old messageRenderer for backward compatibility');
      options.messageRenderer.renderMessages(messages);
      
      // Автоскролл только для старой архитектуры (НЕ V2)
      // V2 управляет скроллом через ChatControllerV2
      if (!window.chatControllerV2) {
        requestAnimationFrame(() => {
          state.scrollEl.scrollTop = state.scrollEl.scrollHeight;
        });
      }
    }
    
    // Инициализируем голосования после загрузки сообщений
    if (window.chatPoll && messages?.length) {
      console.log('[UserWS] Initializing polls after initial messages load');
      setTimeout(() => window.chatPoll.initializeExistingPolls(), 100);
    }
  }

  function handleNewMessage(data) {
    if (!state.scrollEl) return;

    const { message } = data;
    if (!message) return;

    console.log('[UserWS] Dispatching ws:new-message for message id=%s', message.id);
    
    // НОВАЯ АРХИТЕКТУРА: Dispatch события для ChatController
    window.dispatchEvent(new CustomEvent('ws:new-message', {
      detail: {
        message,
        chatId: state.activeChatId,
        isOwnMessage: message.author_id === userId
      }
    }));
    
    // УСТАРЕВШЕЕ: Старая логика остается для backward compatibility
    if (options.messageRenderer) {
      console.log('[UserWS] [DEPRECATED] Using old messageRenderer for backward compatibility');
      options.messageRenderer.renderMessage(message);
      
      const isAtBottom = markReadApi?.atBottom?.() ?? false;
      const isOwnMessage = message.author_id === userId;
      
      // КРИТИЧНО: Не скроллим если работает ChatControllerV2
      // V2 сам управляет автоскроллом через свою логику (isNearBottom, индикатор новых сообщений)
      if (!window.chatControllerV2 && (isOwnMessage || isAtBottom)) {
        requestAnimationFrame(() => scrollToBottom());
      }
      
      const msgEl = state.scrollEl.querySelector(`[data-message-id="${message.id}"]`);
      if (msgEl && markReadApi?.observeLastForeign) {
        markReadApi.observeLastForeign(msgEl);
      }
    }
    
    // Если в сообщении есть голосование, инициализируем его
    if (message.poll && window.chatPoll) {
      console.log('[UserWS] New message with poll detected, poll_id=%s', message.poll.id);
      setTimeout(() => window.chatPoll.refreshPoll(message.poll.id), 100);
    }
  }

  function handleMessageUpdated(data) {
    const { message } = data;
    if (!message) return;

    console.log('[UserWS] Dispatching ws:message-edited for message id=%s', message.id);
    
    // НОВАЯ АРХИТЕКТУРА: ChatController обработает через MessageLoader
    window.dispatchEvent(new CustomEvent('ws:message-edited', {
      detail: {
        message,
        chatId: data.chat_id || state.activeChatId
      }
    }));
    
    // Backward compatibility: старое событие
    window.dispatchEvent(new CustomEvent('chat:message-edited', {
      detail: {
        payload: message,
        chat_id: data.chat_id
      }
    }));
  }

  function handleMessageDeleted(data) {
    console.log('[UserWS] handleMessageDeleted called:', data);
    
    const { message_id } = data;
    if (!message_id) {
      console.warn('[UserWS] No message_id in delete event');
      return;
    }

    console.log('[UserWS] Dispatching ws:message-removed for message id=%s', message_id);
    
    // НОВАЯ АРХИТЕКТУРА: ChatController обработает через MessageLoader
    window.dispatchEvent(new CustomEvent('ws:message-removed', {
      detail: {
        messageId: message_id,
        chatId: data.chat_id || state.activeChatId
      }
    }));
    
    // УСТАРЕВШЕЕ: Старая логика для backward compatibility
    const msgEl = state.scrollEl?.querySelector(`[data-message-id="${message_id}"]`);
    if (msgEl) {
      console.log('[UserWS] [DEPRECATED] Using old direct DOM removal');
      msgEl.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
      msgEl.style.opacity = '0';
      msgEl.style.transform = 'scale(0.8)';
      setTimeout(() => msgEl.remove(), 300);
    }
  }

  function handleListUpdate(data) {
    const { chat_id, message } = data;
    if (!chat_id || !message) return;

    // Обновляем бейдж (если сообщение не от нас)
    if (badgeManager && message.author_id !== userId) {
      badgeManager.incrementChat(chat_id);
    }

    // Обновляем карточку чата в списке
    if (onListUpdate) {
      onListUpdate(chat_id, message);
    }

    // Диспатчим событие для других модулей
    window.dispatchEvent(new CustomEvent('chat:list-update', {
      detail: { chatId: chat_id, message }
    }));
  }

  function handleMessageEditedInList(data) {
    // Обновление последнего сообщения в списке чатов
    if (onListUpdate) {
      onListUpdate(data.chat_id, data.message);
    }
    
    // Диспатчим событие для обновления сообщения в открытом чате
    window.dispatchEvent(new CustomEvent('chat:message-edited', {
      detail: {
        payload: data.message,  // Данные сообщения
        chat_id: data.chat_id
      }
    }));
  }

  function handleReactionAdded(data) {
    const { message_id, emoji, user_id, user_name, reactions_summary } = data;
    
    console.log('[UserWS] Dispatching ws:reaction-added for message id=%s', message_id);
    
    // НОВАЯ АРХИТЕКТУРА: Событие для ChatController
    window.dispatchEvent(new CustomEvent('ws:reaction-added', {
      detail: {
        messageId: message_id,
        emoji,
        userId: user_id,
        userName: user_name,
        reactionsSummary: reactions_summary,
        chatId: state.activeChatId
      }
    }));
    
    // Backward compatibility: старое событие
    window.dispatchEvent(new CustomEvent('chat:reaction-added', {
      detail: { 
        messageId: message_id, 
        emoji, 
        userId: user_id, 
        userName: user_name,
        reactions_summary: reactions_summary
      }
    }));
  }

  function handleReactionRemoved(data) {
    const { message_id, emoji, user_id, reactions_summary } = data;
    
    console.log('[UserWS] Dispatching ws:reaction-removed for message id=%s', message_id);
    
    // НОВАЯ АРХИТЕКТУРА: Событие для ChatController
    window.dispatchEvent(new CustomEvent('ws:reaction-removed', {
      detail: {
        messageId: message_id,
        emoji,
        userId: user_id,
        reactionsSummary: reactions_summary,
        chatId: state.activeChatId
      }
    }));
    
    // Backward compatibility: старое событие
    window.dispatchEvent(new CustomEvent('chat:reaction-removed', {
      detail: { 
        messageId: message_id, 
        emoji, 
        userId: user_id,
        reactions_summary: reactions_summary
      }
    }));
  }

  function handleTypingStart(data) {
    const { user_name } = data;
    if (state.typingEl) {
      state.typingEl.textContent = `${user_name} печатает...`;
      state.typingEl.classList.remove('d-none');
    }
  }

  function handleTypingStop(data) {
    if (state.typingEl) {
      state.typingEl.classList.add('d-none');
    }
  }

  function handlePollUpdate(data) {
    console.log('[UserWebSocket] Poll update received:', data);
    window.dispatchEvent(new CustomEvent('chat:poll-update', {
      detail: {
        poll_id: data.poll_id,
        message_id: data.message_id,
        results: data.results
      }
    }));
  }

  // ==================== Отправка сообщений ====================
  
  // УДАЛЕНО: initChatFormHandlers() больше не используется
  // Форма теперь обрабатывается chatComposer.js через стандартный HTML submit
  // Отправка сообщений идёт через HTTP POST, а не через WebSocket

  function sendMessage(content) {
    send({
      action: 'send_message',
      content: content
    });
  }

  function sendTyping() {
    send({
      action: 'typing'
    });
  }

  function sendStopTyping() {
    send({
      action: 'stop_typing'
    });
  }

  // ==================== Вспомогательные методы ====================

  function send(data) {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    } else {
      console.warn('[UserWS] Cannot send, connection not open');
    }
  }

  function scrollToBottom(instant = false) {
    if (!state.scrollEl) return;
    
    // Прямая установка scrollTop для предсказуемости
    // Избегаем вызова markReadApi.autoscroll чтобы не было конфликтов
    if (instant) {
      const prev = state.scrollEl.style.scrollBehavior;
      state.scrollEl.style.scrollBehavior = 'auto';
      state.scrollEl.scrollTop = state.scrollEl.scrollHeight;
      if (prev) {
        state.scrollEl.style.scrollBehavior = prev;
      } else {
        state.scrollEl.style.removeProperty('scroll-behavior');
      }
    } else {
      state.scrollEl.scrollTop = state.scrollEl.scrollHeight;
    }
  }

  // ==================== Public API ====================

  const api = {
    ws,
    
    /**
     * Динамическая конфигурация WebSocket
     * Позволяет расширять функциональность после инициализации
     * @param {Object} newOptions - Дополнительные опции
     */
    configure: (newOptions = {}) => {
      console.log('[UserWS] Configuring with:', Object.keys(newOptions));
      
      // Обновляем DOM элементы
      if (newOptions.scrollContainerId) {
        state.scrollEl = document.getElementById(newOptions.scrollContainerId);
      }
      if (newOptions.formId) {
        state.form = document.getElementById(newOptions.formId);
      }
      if (newOptions.textareaId) {
        state.textarea = document.getElementById(newOptions.textareaId);
      }
      if (newOptions.typingIndicatorId) {
        state.typingEl = document.getElementById(newOptions.typingIndicatorId);
      }
      
      // Обновляем avatarMap
      if (newOptions.avatarMap) {
        Object.assign(avatarMap, newOptions.avatarMap);
      }
      
      // Обновляем markReadApi
      if (newOptions.markReadApi) {
        options.markReadApi = newOptions.markReadApi;
      }
      
      // Обновляем messageRenderer
      if (newOptions.messageRenderer) {
        options.messageRenderer = newOptions.messageRenderer;
      }
      
      // Обновляем callbacks
      if (newOptions.onListUpdate) {
        options.onListUpdate = newOptions.onListUpdate;
      }
      
      console.log('[UserWS] Configuration updated');
    },
    
    // Управление чатом
    openChat,
    closeChat,
    
    // Отправка сообщений
    sendMessage,
    
    // Реакции
    addReaction: (messageId, emoji) => {
      send({
        action: 'add_reaction',
        message_id: messageId,
        emoji: emoji
      });
    },
    
    removeReaction: (messageId, emoji) => {
      send({
        action: 'remove_reaction',
        message_id: messageId,
        emoji: emoji
      });
    },
    
    // Редактирование
    editMessage: (messageId, content) => {
      send({
        action: 'edit_message',
        message_id: messageId,
        content: content
      });
    },
    
    // Удаление
    deleteMessage: (messageId) => {
      send({
        action: 'delete_message',
        message_id: messageId
      });
    },
    
    // Отметка прочитанного
    markRead: (chatId) => {
      send({
        action: 'mark_read',
        chat_id: chatId
      });
    },
    
    // Голосование
    votePoll: (pollId, optionIds) => {
      send({
        action: 'vote_poll',
        poll_id: pollId,
        option_ids: optionIds
      });
    },
    
    // Состояние
    getActiveChatId: () => state.activeChatId,
    isConnected: () => ws.readyState === WebSocket.OPEN
  };

  // Сохраняем глобально для backward compatibility
  window.userWebSocket = api;

  return api;
}

// Экспортируем также прямой API для использования в модулях
export const getUserWebSocket = () => window.userWebSocket;

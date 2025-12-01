/**
 * Chat Form Manager
 * Управляет состоянием формы отправки сообщений
 * - Обычная отправка
 * - Редактирование сообщения
 * - Ответ на сообщение
 */

export function initChatFormManager(options = {}) {
  const {
    formId = 'chatForm',
    textareaId = 'id_content',
    chatId,
    uploadUrl = '/api/v1/communications/upload-message/',
    editUrlTemplate = '/api/v1/communications/messages/{id}/edit/',
  } = options;

  const form = document.getElementById(formId);
  const textarea = document.getElementById(textareaId);

  if (!form || !textarea) {
    console.warn('[ChatFormManager] Form or textarea not found');
    return null;
  }

  // Состояние формы
  const state = {
    mode: 'send', // 'send' | 'edit' | 'reply'
    editMessageId: null,
    replyToMessageId: null,
    originalAction: form.action,
    originalMethod: form.method,
  };

  // ==================== API ====================

  /**
   * Переключить форму в режим обычной отправки
   */
  function setModeToSend() {
    state.mode = 'send';
    state.editMessageId = null;
    state.replyToMessageId = null;

    // Восстанавливаем action
    form.action = uploadUrl;
    form.method = 'POST';

    // Удаляем hidden поля
    removeHiddenInput('message_id');
    removeHiddenInput('reply_to');

    // Удаляем индикаторы
    removeEditIndicator();
    removeReplyIndicator();

    // Очищаем текст
    textarea.value = '';
    textarea.placeholder = 'Напишите сообщение…';
    textarea.focus();

    console.log('[ChatFormManager] Mode: SEND');
  }

  /**
   * Переключить форму в режим редактирования
   */
  function setModeToEdit(messageId, currentContent) {
    if (!messageId) {
      console.error('[ChatFormManager] messageId required for edit mode');
      return;
    }

    state.mode = 'edit';
    state.editMessageId = messageId;
    state.replyToMessageId = null;

    // Меняем action на API редактирования
    const editUrl = editUrlTemplate.replace('{id}', messageId);
    form.action = editUrl;
    form.method = 'POST';

    // Добавляем hidden input для message_id (на всякий случай)
    addHiddenInput('message_id', messageId);

    // Удаляем reply_to если был
    removeHiddenInput('reply_to');

    // Удаляем индикатор ответа
    removeReplyIndicator();

    // Показываем индикатор редактирования
    showEditIndicator(messageId, currentContent);

    // Заполняем textarea текущим содержимым
    textarea.value = currentContent || '';
    textarea.placeholder = 'Редактирование сообщения…';
    textarea.focus();

    // Курсор в конец
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    console.log('[ChatFormManager] Mode: EDIT', messageId);
  }

  /**
   * Переключить форму в режим ответа
   */
  function setModeToReply(messageId, authorName, messagePreview) {
    if (!messageId) {
      console.error('[ChatFormManager] messageId required for reply mode');
      return;
    }

    // Если было редактирование - сбрасываем
    if (state.mode === 'edit') {
      form.action = uploadUrl;
      form.method = 'POST';
      removeHiddenInput('message_id');
      removeEditIndicator();
    }

    state.mode = 'reply';
    state.editMessageId = null;
    state.replyToMessageId = messageId;

    // Action остаётся обычным (upload-message)
    form.action = uploadUrl;
    form.method = 'POST';

    // Добавляем hidden input reply_to
    addHiddenInput('reply_to', messageId);

    // Показываем индикатор ответа
    showReplyIndicator(messageId, authorName, messagePreview);

    // Фокус на textarea
    textarea.placeholder = `Ответ на сообщение от ${authorName}…`;
    textarea.focus();

    console.log('[ChatFormManager] Mode: REPLY', messageId);
  }

  /**
   * Отменить текущее действие (вернуться к обычной отправке)
   */
  function cancel() {
    setModeToSend();
  }

  /**
   * Получить текущий режим
   */
  function getMode() {
    return state.mode;
  }

  /**
   * Получить данные для отправки
   */
  function getFormData() {
    return {
      mode: state.mode,
      editMessageId: state.editMessageId,
      replyToMessageId: state.replyToMessageId,
      content: textarea.value.trim(),
    };
  }

  // ==================== HELPER FUNCTIONS ====================

  function addHiddenInput(name, value) {
    // Удаляем если уже есть
    removeHiddenInput(name);

    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    input.dataset.chatFormManager = '1';
    form.appendChild(input);
  }

  function removeHiddenInput(name) {
    const existing = form.querySelector(`input[name="${name}"][data-chat-form-manager="1"]`);
    if (existing) {
      existing.remove();
    }
  }

  function showEditIndicator(messageId, content) {
    removeEditIndicator();

    const preview = content.length > 50 ? content.substring(0, 50) + '…' : content;

    const indicator = document.createElement('div');
    indicator.className = 'edit-indicator alert alert-warning d-flex align-items-center justify-content-between py-2 px-3 mb-2';
    indicator.dataset.editIndicator = '1';
    indicator.innerHTML = `
      <div class="d-flex align-items-center gap-2">
        <i class="bi-pencil-square"></i>
        <div>
          <strong>Редактирование сообщения</strong>
          <div class="small text-muted">${escapeHtml(preview)}</div>
        </div>
      </div>
      <button type="button" class="btn-close" data-cancel-edit></button>
    `;

    // Вставляем перед полем ввода
    form.insertBefore(indicator, form.firstChild);

    // Обработчик кнопки отмены
    indicator.querySelector('[data-cancel-edit]').addEventListener('click', () => {
      cancel();
    });
  }

  function removeEditIndicator() {
    const indicator = form.querySelector('[data-edit-indicator]');
    if (indicator) {
      indicator.remove();
    }
  }

  function showReplyIndicator(messageId, authorName, messagePreview) {
    removeReplyIndicator();

    const preview = messagePreview && messagePreview.length > 50 
      ? messagePreview.substring(0, 50) + '…' 
      : messagePreview || 'Сообщение';

    const indicator = document.createElement('div');
    indicator.className = 'reply-indicator alert alert-info d-flex align-items-center justify-content-between py-2 px-3 mb-2';
    indicator.dataset.replyIndicator = '1';
    indicator.innerHTML = `
      <div class="d-flex align-items-center gap-2">
        <i class="bi-reply-fill"></i>
        <div>
          <strong>Ответ на сообщение от ${escapeHtml(authorName)}</strong>
          <div class="small text-muted">${escapeHtml(preview)}</div>
        </div>
      </div>
      <button type="button" class="btn-close" data-cancel-reply></button>
    `;

    // Вставляем перед полем ввода
    form.insertBefore(indicator, form.firstChild);

    // Обработчик кнопки отмены
    indicator.querySelector('[data-cancel-reply]').addEventListener('click', () => {
      cancel();
    });
  }

  function removeReplyIndicator() {
    const indicator = form.querySelector('[data-reply-indicator]');
    if (indicator) {
      indicator.remove();
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ==================== KEYBOARD SHORTCUTS ====================

  // ESC - отменить редактирование/ответ
  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && (state.mode === 'edit' || state.mode === 'reply')) {
      e.preventDefault();
      cancel();
    }
  });

  // ==================== INITIALIZATION ====================

  // Начальное состояние - обычная отправка
  setModeToSend();

  // Экспортируем API
  const api = {
    setModeToSend,
    setModeToEdit,
    setModeToReply,
    cancel,
    getMode,
    getFormData,
    
    // Геттеры для удобного доступа
    get mode() {
      return state.mode;
    },
    get currentMessageId() {
      return state.editMessageId;
    },
    get replyToMessageId() {
      return state.replyToMessageId;
    },
    
    state, // Для отладки
  };

  // Делаем доступным глобально
  window.chatFormManager = api;

  return api;
}

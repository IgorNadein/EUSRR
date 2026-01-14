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
    uploadUrl = '/api/v1/communications/messages/upload/',
    editUrlTemplate = '/api/v1/communications/messages/{id}/',
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
    existingAttachments: [], // Вложения при редактировании
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
   * @param {number|string} messageId - ID сообщения
   * @param {string} currentContent - Текущий текст сообщения
   * @param {Array} existingAttachments - Существующие вложения [{id, file_url, filename, ...}]
   */
  function setModeToEdit(messageId, currentContent = '', existingAttachments = []) {    console.log('[ChatFormManager] setModeToEdit called with:', {
      messageId,
      contentLength: currentContent?.length || 0,
      attachmentsCount: existingAttachments?.length || 0,
      attachments: existingAttachments
    });
        if (!messageId) {
      console.error('[ChatFormManager] messageId required for edit mode');
      return;
    }

    state.mode = 'edit';
    state.editMessageId = messageId;
    state.replyToMessageId = null;
    state.existingAttachments = existingAttachments; // Сохраняем существующие файлы

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
    
    // ВАЖНО: Очищаем новые загруженные файлы (input type="file")
    clearFileInputs();

    // Показываем индикатор редактирования
    showEditIndicator(messageId, currentContent);
    
    // Добавляем существующие вложения в chatComposer
    if (existingAttachments && existingAttachments.length > 0 && window.chatComposer) {
      console.log('[ChatFormManager] Adding existing attachments to chatComposer:', existingAttachments);
      
      // Сохраняем оригинальный метод removeFile
      if (!window.chatComposer._originalRemoveFile) {
        window.chatComposer._originalRemoveFile = window.chatComposer.removeFile.bind(window.chatComposer);
      }
      
      // Переопределяем removeFile чтобы учитывать существующие файлы
      window.chatComposer.removeFile = function(entryId) {
        console.log('[ChatComposer] removeFile called:', entryId);
        
        // Если это существующий файл - удаляем через chatFormManager
        if (entryId.startsWith('existing-')) {
          const attachmentId = entryId.replace('existing-', '');
          const manager = window.chatFormManager;
          if (manager && manager.state) {
            manager.state.existingAttachments = manager.state.existingAttachments.filter(
              att => att.id != attachmentId
            );
            console.log('[ChatComposer] Removed existing attachment:', attachmentId);
          }
        }
        
        // Вызываем оригинальный метод
        this._originalRemoveFile(entryId);
      };
      
      existingAttachments.forEach(att => {
        // Создаем фейковый File объект для существующих вложений
        // chatComposer будет отображать их как обычные файлы
        const mockFile = createMockFileFromAttachment(att);
        if (mockFile) {
          const fileId = `existing-${att.id}`;
          window.chatComposer.selectedFiles.push({ id: fileId, file: mockFile, existingId: att.id });
        }
      });
      window.chatComposer.renderPreview();
    }

    // Заполняем textarea текущим содержимым
    textarea.value = currentContent || '';
    textarea.placeholder = 'Редактирование сообщения…';
    textarea.focus();

    // Курсор в конец
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    console.log('[ChatFormManager] Mode: EDIT', {
      messageId,
      contentLength: currentContent?.length || 0,
      attachmentsCount: existingAttachments?.length || 0
    });
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

  /**
   * Создает mock File объект из данных существующего вложения
   */
  function createMockFileFromAttachment(att) {
    const fileName = att.filename || att.file_name || 'Файл';
    const fileUrl = att.file_url || att.url || '';
    
    if (!fileUrl) return null;
    
    // Определяем MIME type из URL
    let mimeType = 'application/octet-stream';
    if (fileUrl.match(/\.(jpg|jpeg)$/i)) mimeType = 'image/jpeg';
    else if (fileUrl.match(/\.png$/i)) mimeType = 'image/png';
    else if (fileUrl.match(/\.gif$/i)) mimeType = 'image/gif';
    else if (fileUrl.match(/\.webp$/i)) mimeType = 'image/webp';
    else if (fileUrl.match(/\.mp4$/i)) mimeType = 'video/mp4';
    else if (fileUrl.match(/\.pdf$/i)) mimeType = 'application/pdf';
    
    // Создаем mock File объект с расширенными свойствами
    const mockFile = {
      name: fileName,
      type: mimeType,
      size: 0, // Размер неизвестен для существующих файлов
      lastModified: Date.now(),
      // Дополнительные свойства для идентификации
      _isExisting: true,
      _existingId: att.id,
      _existingUrl: fileUrl,
      _sizeStr: att.size_str || ''
    };
    
    return mockFile;
  }

  function showEditIndicator(messageId, content) {
    console.log('[ChatFormManager] showEditIndicator called:', { messageId, contentLength: content?.length || 0 });
    
    removeEditIndicator();

    const preview = content.length > 50 ? content.substring(0, 50) + '…' : content;

    const indicator = document.createElement('div');
    indicator.className = 'edit-indicator alert alert-info d-flex align-items-center justify-content-between py-2 px-3 mb-2';
    indicator.dataset.editIndicator = '1';
    indicator.innerHTML = `
      <div class="d-flex align-items-center gap-2">
        <i class="bi bi-pencil-square fs-5"></i>
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

  /**
   * Очистить все input type="file" и их превью
   */
  function clearFileInputs() {
    console.log('[ChatFormManager] Clearing file inputs...');
    
    // Очищаем все file inputs в форме
    const fileInputs = form.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
      input.value = '';
    });
    
    // Очищаем превью файлов (если есть ChatComposer)
    const attachmentPreview = document.getElementById('attachmentPreview');
    if (attachmentPreview) {
      attachmentPreview.classList.add('d-none');
      attachmentPreview.innerHTML = '';
    }
    
    // Если есть глобальный chatComposer - вызываем его метод очистки
    if (window.chatComposer && typeof window.chatComposer.selectedFiles !== 'undefined') {
      window.chatComposer.selectedFiles = [];
      if (typeof window.chatComposer.renderPreview === 'function') {
        window.chatComposer.renderPreview();
      }
      console.log('[ChatFormManager] ✓ Cleared chatComposer files');
    }
    
    console.log('[ChatFormManager] ✓ File inputs cleared');
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
    get existingAttachments() {
      return state.existingAttachments || [];
    },
    get existingAttachments() {
      return state.existingAttachments || [];
    },
    
    state, // Для отладки
  };

  // Делаем доступным глобально
  window.chatFormManager = api;

  return api;
}

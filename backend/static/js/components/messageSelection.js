/**
 * @fileoverview Message Selection - выделение и пересылка сообщений
 * @module components/messageSelection
 */

/**
 * Класс для управления выделением и пересылкой сообщений
 */
export class MessageSelection {
  /**
   * @param {Object} options - Опции конфигурации
   * @param {string} options.chatId - ID текущего чата
   * @param {string} options.scrollContainerId - ID контейнера сообщений
   * @param {string} options.currentUserId - ID текущего пользователя
   * @param {Function} options.onForward - Callback при успешной пересылке
   */
  constructor(options) {
    console.log('[MessageSelection] Constructor called with options:', options);
    this.chatId = options.chatId;
    this.scrollContainer = document.getElementById(options.scrollContainerId);
    this.currentUserId = options.currentUserId;
    this.onForward = options.onForward || (() => {});
    
    this.selectedMessages = new Set();
    this.selectionMode = false;
    
    console.log('[MessageSelection] scrollContainer found:', !!this.scrollContainer);
    
    this.init();
  }

  /**
   * Инициализация
   */
  init() {
    console.log('[MessageSelection] Initializing...');
    this.createActionBar();
    this.attachEventListeners();
    
    // Слушаем события контекстного меню
    window.addEventListener('message-context-menu', (e) => {
      console.log('[MessageSelection] message-context-menu event received:', e.detail);
      const action = e.detail?.action;
      const messageElement = e.detail?.messageElement;
      
      if (action === 'select' && messageElement) {
        console.log('[MessageSelection] Entering selection mode for message:', messageElement.dataset.messageId);
        this.enterSelectionMode(messageElement);
      }
    });
    
    // Слушаем события пересылки одного сообщения
    window.addEventListener('message-forward-single', (e) => {
      console.log('[MessageSelection] message-forward-single event received:', e.detail);
      const messageId = e.detail?.messageId;
      if (messageId) {
        console.log('[MessageSelection] Forwarding single message:', messageId);
        this.forwardSingleMessage(messageId);
      }
    });
    
    console.log('[MessageSelection] Initialized successfully');
  }

  /**
   * Создает панель действий внизу экрана
   */
  createActionBar() {
    const bar = document.createElement('div');
    bar.className = 'selection-actions-bar';
    bar.id = 'selectionActionsBar';
    bar.innerHTML = `
      <div class="selection-count">
        <span id="selectionCount">0</span> выбрано
      </div>
      <div class="selection-actions">
        <button type="button" class="btn btn-outline-secondary" id="btnCancelSelection">
          <i class="bi-x-lg"></i> Отмена
        </button>
        <button type="button" class="btn btn-outline-danger" id="btnDeleteSelected" style="display: none;">
          <i class="bi-trash"></i> Удалить
        </button>
        <button type="button" class="btn btn-primary" id="btnForwardSelected">
          <i class="bi-arrow-right"></i> Переслать
        </button>
      </div>
    `;
    document.body.appendChild(bar);
    
    this.actionBar = bar;
    this.countElement = bar.querySelector('#selectionCount');
    
    // Обработчики кнопок
    bar.querySelector('#btnCancelSelection').addEventListener('click', () => {
      this.exitSelectionMode();
    });
    
    bar.querySelector('#btnForwardSelected').addEventListener('click', () => {
      this.showForwardDialog();
    });
    
    bar.querySelector('#btnDeleteSelected').addEventListener('click', () => {
      this.deleteSelected();
    });
  }

  /**
   * Подключает обработчики событий
   */
  attachEventListeners() {
    // Делегирование событий для чекбоксов и сообщений
    this.scrollContainer.addEventListener('click', (e) => {
      if (!this.selectionMode) return;
      
      const checkbox = e.target.closest('.msg-select-checkbox');
      if (checkbox) {
        const messageElement = checkbox.closest('.msg');
        this.toggleMessageSelection(messageElement);
        return;
      }
      
      const messageElement = e.target.closest('.msg');
      if (messageElement) {
        this.toggleMessageSelection(messageElement);
      }
    });

    // Долгое нажатие отключено - режим выбора активируется только через кнопку "Выбрать" в меню
    // let longPressTimer = null;
    // 
    // this.scrollContainer.addEventListener('touchstart', (e) => {
    //   const messageElement = e.target.closest('.msg');
    //   if (!messageElement || this.selectionMode) return;
    //   
    //   longPressTimer = setTimeout(() => {
    //     this.enterSelectionMode(messageElement);
    //     navigator.vibrate?.(50); // Вибрация на мобильных
    //   }, 500);
    // });
    // 
    // this.scrollContainer.addEventListener('touchend', () => {
    //   clearTimeout(longPressTimer);
    // });
    // 
    // this.scrollContainer.addEventListener('touchmove', () => {
    //   clearTimeout(longPressTimer);
    // });

    // ESC для выхода из режима
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.selectionMode) {
        this.exitSelectionMode();
      }
    });
  }

  /**
   * Входит в режим выделения
   * @param {HTMLElement} firstMessage - Первое выделенное сообщение
   */
  enterSelectionMode(firstMessage) {
    this.selectionMode = true;
    this.scrollContainer.classList.add('selection-mode');
    this.actionBar.classList.add('active');
    
    // Добавляем чекбоксы ко всем сообщениям
    const messages = this.scrollContainer.querySelectorAll('.msg');
    messages.forEach(msg => {
      if (!msg.querySelector('.msg-select-checkbox')) {
        const checkbox = document.createElement('div');
        checkbox.className = 'msg-select-checkbox';
        msg.style.position = 'relative';
        msg.appendChild(checkbox);
      }
    });
    
    // Выделяем первое сообщение
    if (firstMessage) {
      this.toggleMessageSelection(firstMessage);
    }
  }

  /**
   * Выходит из режима выделения
   */
  exitSelectionMode() {
    this.selectionMode = false;
    this.selectedMessages.clear();
    this.scrollContainer.classList.remove('selection-mode');
    this.actionBar.classList.remove('active');
    
    // Убираем чекбоксы и выделение
    const messages = this.scrollContainer.querySelectorAll('.msg');
    messages.forEach(msg => {
      msg.classList.remove('selected');
      const checkbox = msg.querySelector('.msg-select-checkbox');
      if (checkbox) {
        checkbox.remove();
      }
    });
    
    this.updateCount();
  }

  /**
   * Переключает выделение сообщения
   * @param {HTMLElement} messageElement - Элемент сообщения
   */
  toggleMessageSelection(messageElement) {
    if (!messageElement) return;
    
    const messageId = messageElement.dataset.id;
    if (!messageId) return;
    
    const checkbox = messageElement.querySelector('.msg-select-checkbox');
    
    if (this.selectedMessages.has(messageId)) {
      this.selectedMessages.delete(messageId);
      messageElement.classList.remove('selected');
      checkbox?.classList.remove('selected');
    } else {
      this.selectedMessages.add(messageId);
      messageElement.classList.add('selected');
      checkbox?.classList.add('selected');
    }
    
    this.updateCount();
    
    // Автовыход если ничего не выбрано
    if (this.selectedMessages.size === 0) {
      this.exitSelectionMode();
    }
  }

  /**
   * Обновляет счетчик выделенных сообщений
   */
  updateCount() {
    const count = this.selectedMessages.size;
    this.countElement.textContent = count;
    
    // Показываем кнопку удаления только для своих сообщений
    const deleteBtn = this.actionBar.querySelector('#btnDeleteSelected');
    const canDelete = this.canDeleteSelected();
    deleteBtn.style.display = canDelete ? 'block' : 'none';
  }

  /**
   * Проверяет, можно ли удалить выделенные сообщения
   * @returns {boolean}
   */
  canDeleteSelected() {
    for (const messageId of this.selectedMessages) {
      const messageElement = this.scrollContainer.querySelector(`[data-id="${messageId}"]`);
      const authorId = messageElement?.dataset.authorId;
      if (authorId !== this.currentUserId) {
        return false;
      }
    }
    return true;
  }

  /**
   * Пересылает одно сообщение (без входа в режим выбора)
   * @param {string|number} messageId - ID сообщения для пересылки
   */
  async forwardSingleMessage(messageId) {
    console.log('forwardSingleMessage called with:', messageId);
    
    // Временно добавляем сообщение в selectedMessages
    const wasInSelectionMode = this.selectionMode;
    const originalSelection = new Set(this.selectedMessages);
    
    this.selectedMessages.clear();
    this.selectedMessages.add(String(messageId));
    
    console.log('selectedMessages after add:', this.selectedMessages);
    
    // Создаем модальное окно
    const modal = this.createForwardModal();
    document.body.appendChild(modal);
    
    // Загружаем список чатов
    await this.loadChats(modal);
    
    // Показываем модальное окно
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Восстанавливаем состояние после закрытия модала
    modal.addEventListener('hidden.bs.modal', () => {
      modal.remove();
      if (!wasInSelectionMode) {
        this.selectedMessages = originalSelection;
      }
    });
  }

  /**
   * Показывает диалог выбора чата для пересылки
   */
  async showForwardDialog() {
    if (this.selectedMessages.size === 0) return;
    
    // Создаем модальное окно
    const modal = this.createForwardModal();
    document.body.appendChild(modal);
    
    // Загружаем список чатов
    await this.loadChats(modal);
    
    // Показываем модальное окно
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Удаляем после закрытия
    modal.addEventListener('hidden.bs.modal', () => {
      modal.remove();
    });
  }

  /**
   * Создает модальное окно для пересылки
   * @returns {HTMLElement}
   */
  createForwardModal() {
    const modal = document.createElement('div');
    modal.className = 'modal fade chat-forward-modal';
    modal.id = 'forwardModal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi-arrow-right-circle me-2"></i>
              Переслать ${this.selectedMessages.size} ${this.getMessageWord(this.selectedMessages.size)}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="chat-forward-search">
            <input type="text" placeholder="Поиск чата..." id="chatSearchInput">
          </div>
          <div class="modal-body p-0" id="chatListContainer">
            <div class="chat-list-loading">
              <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Загрузка...</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Поиск
    const searchInput = modal.querySelector('#chatSearchInput');
    searchInput.addEventListener('input', (e) => {
      this.filterChats(modal, e.target.value);
    });
    
    return modal;
  }

  /**
   * Загружает список чатов
   * @param {HTMLElement} modal - Модальное окно
   */
  async loadChats(modal) {
    const container = modal.querySelector('#chatListContainer');
    
    try {
      const response = await fetch('/api/v1/communications/chats/', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Server error:', response.status, errorText);
        throw new Error(`Failed to load chats: ${response.status}`);
      }
      
      const data = await response.json();
      const chats = data.results || data;
      
      if (!Array.isArray(chats)) {
        console.error('Invalid response format:', data);
        throw new Error('Invalid response format');
      }
      
      // Исключаем текущий чат
      const filteredChats = chats.filter(chat => String(chat.id) !== String(this.chatId));
      
      if (filteredChats.length === 0) {
        container.innerHTML = `
          <div class="chat-list-empty">
            <i class="bi-chat-dots fs-1 mb-3 d-block"></i>
            <p>Нет доступных чатов</p>
          </div>
        `;
        return;
      }
      
      container.innerHTML = filteredChats.map(chat => this.renderChatItem(chat)).join('');
      
      // Обработчики клика
      container.querySelectorAll('.chat-list-item').forEach(item => {
        item.addEventListener('click', () => {
          const targetChatId = item.dataset.chatId;
          this.forwardToChat(targetChatId, modal);
        });
      });
      
    } catch (error) {
      console.error('Failed to load chats:', error);
      container.innerHTML = `
        <div class="chat-list-empty">
          <i class="bi-exclamation-triangle text-danger fs-1 mb-3 d-block"></i>
          <p>Ошибка загрузки чатов</p>
          <button class="btn btn-sm btn-primary mt-2" onclick="location.reload()">
            Обновить страницу
          </button>
        </div>
      `;
    }
  }

  /**
   * Рендерит элемент чата
   * @param {Object} chat - Данные чата
   * @returns {string}
   */
  renderChatItem(chat) {
    const avatar = chat.avatar || '';
    const name = chat.name || 'Без названия';
    const subtitle = chat.last_message?.content || 'Нет сообщений';
    const type = chat.type || 'private';
    
    // Иконки для типов чатов
    const typeIcons = {
      'private': 'bi-person-fill',
      'group': 'bi-people-fill',
      'channel': 'bi-broadcast',
      'department': 'bi-diagram-3',
      'announcement': 'bi-megaphone',
      'global': 'bi-globe'
    };
    const icon = typeIcons[type] || 'bi-chat-dots';
    
    return `
      <div class="chat-list-item" data-chat-id="${chat.id}">
        <div class="chat-list-avatar">
          ${avatar ? `<img src="${avatar}" alt="${this.escapeHtml(name)}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">` : ''}
          <i class="bi ${icon}" style="${avatar ? 'display:none' : ''}"></i>
        </div>
        <div class="chat-list-info">
          <div class="chat-list-name">${this.escapeHtml(name)}</div>
          <div class="chat-list-subtitle">${this.escapeHtml(subtitle)}</div>
        </div>
      </div>
    `;
  }

  /**
   * Фильтрует чаты по поисковому запросу
   * @param {HTMLElement} modal - Модальное окно
   * @param {string} query - Поисковый запрос
   */
  filterChats(modal, query) {
    const container = modal.querySelector('#chatListContainer');
    const items = container.querySelectorAll('.chat-list-item');
    const lowerQuery = query.toLowerCase();
    
    items.forEach(item => {
      const name = item.querySelector('.chat-list-name').textContent.toLowerCase();
      item.style.display = name.includes(lowerQuery) ? 'flex' : 'none';
    });
  }

  /**
   * Пересылает сообщения в выбранный чат
   * @param {string} targetChatId - ID целевого чата
   * @param {HTMLElement} modal - Модальное окно
   */
  async forwardToChat(targetChatId, modal) {
    const messageIds = Array.from(this.selectedMessages);
    
    console.log('forwardToChat:', {
      selectedMessages: this.selectedMessages,
      messageIds: messageIds,
      targetChatId: targetChatId
    });
    
    try {
      const response = await fetch('/api/v1/communications/messages/forward/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCsrfToken()
        },
        body: JSON.stringify({
          message_ids: messageIds,
          target_chat_id: targetChatId
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to forward messages');
      }
      
      // Закрываем модальное окно
      const bsModal = bootstrap.Modal.getInstance(modal);
      bsModal.hide();
      
      // Выходим из режима выделения
      this.exitSelectionMode();
      
      // Показываем уведомление
      this.showToast('success', `${messageIds.length} ${this.getMessageWord(messageIds.length)} переслано`);
      
      // Callback
      this.onForward(messageIds, targetChatId);
      
    } catch (error) {
      console.error('Failed to forward messages:', error);
      this.showToast('danger', 'Ошибка при пересылке сообщений');
    }
  }

  /**
   * Удаляет выделенные сообщения
   */
  async deleteSelected() {
    if (!this.canDeleteSelected()) return;
    
    const messageIds = Array.from(this.selectedMessages);
    
    if (!confirm(`Удалить ${messageIds.length} ${this.getMessageWord(messageIds.length)}?`)) {
      return;
    }
    
    try {
      const response = await fetch('/api/v1/communications/messages/bulk-delete/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCsrfToken()
        },
        body: JSON.stringify({
          message_ids: messageIds
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete messages');
      }
      
      // Удаляем из DOM
      messageIds.forEach(id => {
        const element = this.scrollContainer.querySelector(`[data-id="${id}"]`);
        element?.remove();
      });
      
      // Выходим из режима выделения
      this.exitSelectionMode();
      
      this.showToast('success', 'Сообщения удалены');
      
    } catch (error) {
      console.error('Failed to delete messages:', error);
      this.showToast('danger', 'Ошибка при удалении сообщений');
    }
  }

  /**
   * Получает CSRF токен
   * @returns {string}
   */
  getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  }

  /**
   * Показывает toast уведомление
   * @param {string} type - Тип (success, danger, warning, info)
   * @param {string} message - Текст сообщения
   */
  showToast(type, message) {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed bottom-0 end-0 m-3`;
    toast.style.zIndex = '9999';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.remove();
    }, 3000);
  }

  /**
   * Возвращает правильную форму слова "сообщение"
   * @param {number} count - Количество
   * @returns {string}
   */
  getMessageWord(count) {
    const lastDigit = count % 10;
    const lastTwoDigits = count % 100;
    
    if (lastTwoDigits >= 11 && lastTwoDigits <= 19) {
      return 'сообщений';
    }
    if (lastDigit === 1) {
      return 'сообщение';
    }
    if (lastDigit >= 2 && lastDigit <= 4) {
      return 'сообщения';
    }
    return 'сообщений';
  }

  /**
   * Экранирует HTML
   * @param {string} text - Текст
   * @returns {string}
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Export для использования в других модулях
export default MessageSelection;

/**
 * Module: Request Detail Modal
 * 
 * Отвечает за открытие и управление модальным окном с деталями заявления.
 * Используется для открытия заявления из списка или прямой ссылки.
 */

export class RequestDetailModal {
  constructor(modalId = 'requestDetailModal', containerId = 'requestDetailContent') {
    this.modalId = modalId;
    this.containerId = containerId;
    this.modal = null;
    this.container = null;
    this.currentRequestId = null;
    this.init();
  }

  /**
   * Инициализация модального окна
   */
  init() {
    const modalElement = document.getElementById(this.modalId);
    if (!modalElement) {
      console.warn(`Modal element with id "${this.modalId}" not found`);
      return;
    }

    this.container = document.getElementById(this.containerId);
    this.modal = new bootstrap.Modal(modalElement);

    // Обработчики событий модали
    modalElement.addEventListener('hidden.bs.modal', () => {
      this.currentRequestId = null;
    });
  }

  /**
   * Открыть модальное окно с заявлением
   * @param {number} requestId - ID заявления
   */
  async open(requestId) {
    this.currentRequestId = requestId;
    
    // Показать loading
    if (this.container) {
      this.container.innerHTML = '<div class="d-flex justify-content-center p-4"><div class="spinner-border" role="status"><span class="visually-hidden">Загрузка...</span></div></div>';
    }

    // Загрузить данные
    await this.loadData(requestId);
    
    // Показать модаль
    if (this.modal) {
      this.modal.show();
    }
  }

  /**
   * Загрузить данные заявления через AJAX
   * @param {number} requestId - ID заявления
   */
  async loadData(requestId) {
    try {
      const response = await fetch(`/requests/${requestId}/`, {
        method: 'GET',
        headers: {
          'Accept': 'text/html',
        },
        credentials: 'same-origin'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const html = await response.text();
      
      // Извлечь содержимое из полной страницы (ищем .card элемент)
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const content = doc.querySelector('.container > .row > .col-12');

      if (content && this.container) {
        this.container.innerHTML = content.innerHTML;
        this.attachEventListeners();
      }
    } catch (error) {
      console.error('Error loading request details:', error);
      if (this.container) {
        this.container.innerHTML = `
          <div class="alert alert-danger mb-0">
            <strong>Ошибка при загрузке:</strong> ${error.message}
          </div>
        `;
      }
    }
  }

  /**
   * Присоединить обработчики событий к элементам в модали
   */
  attachEventListeners() {
    // Обработчик для формы добавления комментария
    const commentForm = this.container?.querySelector('.request-comment-form');
    if (commentForm) {
      commentForm.addEventListener('submit', (e) => this.handleCommentSubmit(e));
    }

    // Обработчик для кнопки отозвать
    const cancelBtn = this.container?.querySelector('[href*="request_cancel"]');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', (e) => this.handleCancel(e));
    }

    // Обработчик для кнопок удаления комментариев
    const deleteCommentForms = this.container?.querySelectorAll('[action*="request_comment_delete"]');
    if (deleteCommentForms) {
      deleteCommentForms.forEach(form => {
        form.addEventListener('submit', (e) => this.handleDeleteComment(e));
      });
    }

    // Обработчик для кнопок смены статуса
    const statusForm = this.container?.querySelector('.request-status-form');
    if (statusForm) {
      statusForm.addEventListener('submit', (e) => this.handleStatusChange(e));
    }

    // Инициализация emoji picker если доступна
    this.initEmojiPicker();

    // Обновить счетчик комментариев
    this.updateCommentsCount();
  }

  /**
   * Обработчик отправки комментария
   */
  async handleCommentSubmit(e) {
    e.preventDefault();

    const form = e.target;
    const textarea = form.querySelector('textarea[name="text"]');
    const text = textarea?.value.trim();

    if (!text) {
      alert('Пожалуйста, введите текст комментария');
      return;
    }

    // Показать состояние загрузки
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn?.textContent || 'Отправить';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Отправка...';
    }

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''
        },
        body: JSON.stringify({ text: text }),
        credentials: 'same-origin'
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      // Очистить форму
      textarea.value = '';
      
      // Показать успешное сообщение
      if (submitBtn) {
        const originalClass = submitBtn.className;
        submitBtn.className = submitBtn.className.replace('btn-primary', 'btn-success');
        submitBtn.innerHTML = '<i class="bi-check-circle me-2"></i>Комментарий добавлен!';
        
        // Вернуть кнопку в исходное состояние
        setTimeout(() => {
          submitBtn.className = originalClass;
          submitBtn.innerHTML = originalBtnText;
          submitBtn.disabled = false;
        }, 2000);
      }
      
      // Перезагрузить содержимое модали
      if (this.currentRequestId) {
        // Небольшая задержка для лучшего UX
        setTimeout(() => {
          this.loadData(this.currentRequestId);
          this.updateCommentsCount();
        }, 500);
      }
    } catch (error) {
      console.error('Error submitting comment:', error);
      
      // Восстановить кнопку при ошибке
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
      }
      
      // Показать ошибку в UI
      const alertDiv = form.querySelector('.alert');
      if (alertDiv) {
        alertDiv.remove();
      }
      
      const errorAlert = document.createElement('div');
      errorAlert.className = 'alert alert-danger alert-dismissible fade show mb-2';
      errorAlert.innerHTML = `
        <strong>Ошибка:</strong> ${error.message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      `;
      form.parentNode.insertBefore(errorAlert, form);
    }
  }

  /**
   * Обработчик удаления комментария
   */
  async handleDeleteComment(e) {
    e.preventDefault();

    if (!confirm('Вы уверены, что хотите удалить этот комментарий?')) {
      return;
    }

    const form = e.target;
    
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: {
          'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''
        },
        credentials: 'same-origin'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      // Перезагрузить содержимое модали
      if (this.currentRequestId) {
        await this.loadData(this.currentRequestId);
        this.updateCommentsCount();
      }
    } catch (error) {
      console.error('Error deleting comment:', error);
      alert('Ошибка при удалении комментария: ' + error.message);
    }
  }

  /**
   * Инициализировать emoji picker если доступен
   */
  initEmojiPicker() {
    const emojiPicker = this.container?.querySelector('emoji-picker');
    const textarea = this.container?.querySelector('textarea[name="text"]');
    
    if (emojiPicker && textarea) {
      emojiPicker.addEventListener('emoji-click', (e) => {
        textarea.value += e.detail.emoji.native;
        textarea.focus();
      });
    }
  }

  /**
   * Обновить счетчик комментариев
   */
  updateCommentsCount() {
    const commentsContainer = this.container?.querySelector('.d-flex.flex-column.gap-2.mb-3');
    const countSpan = this.container?.querySelector('.comments-count');
    
    if (commentsContainer && countSpan) {
      const commentCount = commentsContainer.querySelectorAll('.bg-body-tertiary.border').length;
      countSpan.textContent = commentCount;
    }
  }

  /**
   * Обработчик изменения статуса заявления
   */
  async handleStatusChange(e) {
    e.preventDefault();

    const form = e.target;
    const selectField = form.querySelector('select[name="status"]');
    const newStatus = selectField?.value;

    if (!newStatus) {
      alert('Пожалуйста, выберите новый статус');
      return;
    }

    const confirmMsg = form.dataset.confirmMsg || 
      `Вы уверены, что хотите изменить статус на "${form.querySelector(`option[value="${newStatus}"]`)?.textContent}"?`;
    
    if (!confirm(confirmMsg)) {
      return;
    }

    // Показать состояние загрузки
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn?.textContent || 'Применить';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Обновление...';
    }

    try {
      // Использовать правильный endpoint для изменения статуса
      const action = newStatus === 'approved' ? 'approve' : 
                     newStatus === 'rejected' ? 'reject' : 
                     newStatus === 'cancelled' ? 'cancel' : null;

      if (!action) {
        throw new Error('Неподдерживаемый статус');
      }

      const response = await fetch(
        `/api/v1/requests/${this.currentRequestId}/${action}/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''
          },
          credentials: 'same-origin'
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      // Показать успешное сообщение
      if (submitBtn) {
        const originalClass = submitBtn.className;
        submitBtn.className = submitBtn.className.replace('btn-primary', 'btn-success');
        submitBtn.innerHTML = '<i class="bi-check-circle me-2"></i>Статус обновлен!';
        
        // Вернуть кнопку в исходное состояние
        setTimeout(() => {
          submitBtn.className = originalClass;
          submitBtn.innerHTML = originalBtnText;
          submitBtn.disabled = false;
        }, 2000);
      }
      
      // Перезагрузить содержимое модали
      if (this.currentRequestId) {
        setTimeout(() => {
          this.loadData(this.currentRequestId);
        }, 500);
      }
    } catch (error) {
      console.error('Error changing status:', error);
      
      // Восстановить кнопку при ошибке
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
      }
      
      // Показать ошибку в UI
      const alertDiv = form.querySelector('.alert');
      if (alertDiv) {
        alertDiv.remove();
      }
      
      const errorAlert = document.createElement('div');
      errorAlert.className = 'alert alert-danger alert-dismissible fade show mb-2';
      errorAlert.innerHTML = `
        <strong>Ошибка:</strong> ${error.message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      `;
      form.parentNode.insertBefore(errorAlert, form);
    }
  }

  /**
   * Закрыть модальное окно
   */
  close() {
    if (this.modal) {
      this.modal.hide();
    }
  }
}

/**
 * Инициализировать обработчики для открытия заявлений
 * Должна быть вызвана после загрузки страницы с списком заявлений
 */
export function initRequestDetailModal() {
  const detailModal = new RequestDetailModal();

  // Обработчик клика по строкам в таблице заявлений
  document.addEventListener('click', (e) => {
    // Проверить если клик был по элементу с data-request-id
    let target = e.target.closest('[data-request-id]');
    
    if (target) {
      const requestId = target.dataset.requestId;
      if (requestId) {
        e.preventDefault();
        detailModal.open(parseInt(requestId));
      }
    }

    // Или клик по ссылке на заявление
    if (e.target.classList.contains('request-link')) {
      const requestId = e.target.dataset.requestId;
      if (requestId) {
        e.preventDefault();
        detailModal.open(parseInt(requestId));
      }
    }
  });

  return detailModal;
}

export default RequestDetailModal;

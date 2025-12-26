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

    try {
      const formData = new FormData(form);
      const response = await fetch(form.action, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      // Очистить форму
      textarea.value = '';
      
      // Перезагрузить содержимое модали
      if (this.currentRequestId) {
        await this.loadData(this.currentRequestId);
      }
    } catch (error) {
      console.error('Error submitting comment:', error);
      alert('Ошибка при добавлении комментария: ' + error.message);
    }
  }

  /**
   * Обработчик отозвания заявления
   */
  handleCancel(e) {
    e.preventDefault();
    
    if (confirm('Вы уверены, что хотите отозвать это заявление?')) {
      // Перейти по ссылке или отправить форму
      window.location.href = e.target.href;
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

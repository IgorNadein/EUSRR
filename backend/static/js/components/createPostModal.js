/**
 * createPostModal.js
 * Обработчик модального окна создания публикации через API
 */

export function initCreatePostModal(options = {}) {
  const {
    modalId = 'createPostModal',
    formId = 'createPostForm',
    errorsId = 'createPostErrors',
    submitBtnId = 'createPostSubmit',
    apiUrl = '/api/v1/posts/'
  } = options;

  const modal = document.getElementById(modalId);
  const form = document.getElementById(formId);
  const errorsDiv = document.getElementById(errorsId);
  const submitBtn = document.getElementById(submitBtnId);
  
  if (!modal || !form) {
    console.error('Modal or form not found!', { modalId, formId });
    return;
  }
  
  console.log('Create post modal initialized with API:', apiUrl);
  
  // Получаем токен доступа
  const accessMeta = document.querySelector('meta[name="api-access"]');
  const ACCESS = accessMeta ? accessMeta.content : '';
  const headers = ACCESS ? { 'Authorization': 'Bearer ' + ACCESS } : {};
  
  // Маппинг полей для человекочитаемых названий
  const fieldLabels = {
    'title': 'Заголовок',
    'body': 'Содержание',
    'image': 'Изображение',
    'attachment': 'Вложение',
    'type': 'Тип публикации'
  };
  
  /**
   * Очистка формы и ошибок
   */
  function clearFormErrors() {
    errorsDiv.classList.add('d-none');
    errorsDiv.innerHTML = '';
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    form.querySelectorAll('.invalid-feedback').forEach(el => el.remove());
  }
  
  /**
   * Валидация обязательных полей
   */
  function validateRequiredFields() {
    const title = form.querySelector('[name="title"]');
    const body = form.querySelector('[name="body"]');
    let hasErrors = false;
    
    if (!title.value.trim()) {
      title.classList.add('is-invalid');
      const feedback = document.createElement('div');
      feedback.className = 'invalid-feedback';
      feedback.textContent = 'Заголовок обязателен для заполнения';
      title.parentElement.appendChild(feedback);
      hasErrors = true;
    }
    
    if (!body.value.trim()) {
      body.classList.add('is-invalid');
      const feedback = document.createElement('div');
      feedback.className = 'invalid-feedback';
      feedback.textContent = 'Содержание обязательно для заполнения';
      body.parentElement.appendChild(feedback);
      hasErrors = true;
    }
    
    return !hasErrors;
  }
  
  /**
   * Отображение ошибок по полям
   */
  function displayFieldErrors(errors) {
    const errorMessages = [];
    
    for (const [fieldName, messages] of Object.entries(errors)) {
      const field = form.querySelector(`[name="${fieldName}"]`);
      const errorText = Array.isArray(messages) ? messages.join(', ') : messages;
      const label = fieldLabels[fieldName] || fieldName;
      
      errorMessages.push(`<strong>${label}:</strong> ${errorText}`);
      
      if (field) {
        field.classList.add('is-invalid');
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = errorText;
        field.parentElement.appendChild(feedback);
      }
    }
    
    if (errorMessages.length > 0) {
      errorsDiv.innerHTML = errorMessages.join('<br>');
      errorsDiv.classList.remove('d-none');
    }
  }
  
  /**
   * Показать общее сообщение об ошибке
   */
  function displayGeneralError(message) {
    errorsDiv.textContent = message;
    errorsDiv.classList.remove('d-none');
  }
  
  /**
   * Показать уведомление об успехе
   */
  function showSuccessNotification(message) {
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-bg-success border-0 position-fixed top-0 start-50 translate-middle-x mt-3';
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.style.zIndex = '9999';
    
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi-check-circle me-2"></i>${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    `;
    
    document.body.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => {
      toast.remove();
    });
  }
  
  /**
   * Отправка формы через API
   */
  async function submitForm(e) {
    e.preventDefault();
    clearFormErrors();
    
    if (!validateRequiredFields()) {
      return false;
    }
    
    // Отключаем кнопку и показываем загрузку
    submitBtn.disabled = true;
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Публикация...';
    
    const formData = new FormData(form);
    
    try {
      // Для multipart/form-data НЕ передаём Content-Type, браузер установит сам с boundary
      const fetchHeaders = ACCESS ? { 'Authorization': 'Bearer ' + ACCESS } : {};
      
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: fetchHeaders,
        body: formData
      });

      if (response.ok) {
        showSuccessNotification('Публикация создана!');
        bootstrap.Modal.getInstance(modal).hide();
        form.reset();
        // Перезагружаем страницу для отображения новой публикации
        setTimeout(() => window.location.reload(), 500);
      } else {
        const error = await response.json();
        if (typeof error === 'object' && error !== null) {
          displayFieldErrors(error);
        } else {
          displayGeneralError('Ошибка создания публикации');
        }
      }
    } catch (error) {
      console.error('Error creating post:', error);
      displayGeneralError('Ошибка сети при создании публикации');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalText;
    }
    
    return false;
  }
  
  // Обработчик отправки формы
  form.addEventListener('submit', submitForm);
  
  // Очистка ошибок при открытии модала
  modal.addEventListener('show.bs.modal', () => {
    clearFormErrors();
    form.reset();
  });
}

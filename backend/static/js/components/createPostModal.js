/**
 * createPostModal.js
 * Обработчик модального окна создания публикации
 */

export function initCreatePostModal(options = {}) {
  const {
    modalId = 'createPostModal',
    formId = 'createPostForm',
    errorsId = 'createPostErrors',
    submitBtnId = 'createPostSubmit',
    submitUrl = '/feed/post/new/'
  } = options;

  const modal = document.getElementById(modalId);
  const form = document.getElementById(formId);
  const errorsDiv = document.getElementById(errorsId);
  const submitBtn = document.getElementById(submitBtnId);
  
  if (!modal || !form) {
    console.error('Modal or form not found!', { modalId, formId });
    return;
  }
  
  console.log('Create post modal initialized');
  
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
   * Отправка формы через обычный submit (не AJAX)
   * Проще использовать стандартную отправку формы Django
   */
  function submitForm(e) {
    clearFormErrors();
    
    if (!validateRequiredFields()) {
      e.preventDefault();
      return false;
    }
    
    // Отключаем кнопку и показываем загрузку
    submitBtn.disabled = true;
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Публикация...';
    
    // Позволяем форме отправиться обычным способом
    return true;
  }
  
  // Обработчик отправки формы
  form.addEventListener('submit', submitForm);
  
  // Очистка ошибок при открытии модала
  modal.addEventListener('show.bs.modal', () => {
    clearFormErrors();
    form.reset();
  });
}

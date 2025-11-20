/**
 * createEmployeeModal.js
 * Обработчик модального окна создания сотрудника
 */

export function initCreateEmployeeModal(options = {}) {
  const {
    modalId = 'createEmployeeModal',
    formId = 'createEmployeeForm',
    errorsId = 'createEmployeeErrors',
    submitBtnId = 'createEmployeeSubmit',
    submitUrl = '/employees/create/modal/'
  } = options;

  const modal = document.getElementById(modalId);
  const form = document.getElementById(formId);
  const errorsDiv = document.getElementById(errorsId);
  const submitBtn = document.getElementById(submitBtnId);
  
  if (!modal || !form) {
    console.error('Modal or form not found!', { modal, form });
    return;
  }
  
  console.log('Create employee modal initialized');
  
  // Маппинг полей для человекочитаемых названий
  const fieldLabels = {
    'email': 'Email',
    'phone_number': 'Телефон',
    'last_name': 'Фамилия',
    'first_name': 'Имя',
    'patronymic': 'Отчество',
    'gender': 'Пол',
    'birth_date': 'Дата рождения',
    'position': 'Должность',
    'password': 'Пароль',
    'telegram': 'Telegram',
    'whatsapp': 'WhatsApp',
    'wechat': 'WeChat',
    'avatar': 'Аватар'
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
    const email = form.querySelector('[name="email"]');
    const phone = form.querySelector('[name="phone_number"]');
    let hasErrors = false;
    
    if (!email.value.trim()) {
      email.classList.add('is-invalid');
      const feedback = document.createElement('div');
      feedback.className = 'invalid-feedback';
      feedback.textContent = 'Email обязателен для заполнения';
      email.parentElement.appendChild(feedback);
      hasErrors = true;
    }
    
    if (!phone.value.trim()) {
      phone.classList.add('is-invalid');
      const feedback = document.createElement('div');
      feedback.className = 'invalid-feedback';
      feedback.textContent = 'Телефон обязателен для заполнения';
      phone.parentElement.appendChild(feedback);
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
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show';
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container') || document.body;
    container.prepend(alertDiv);
    
    setTimeout(() => alertDiv.remove(), 5000);
  }
  
  /**
   * Блокировка/разблокировка кнопки отправки
   */
  function setSubmitButtonState(loading) {
    submitBtn.disabled = loading;
    submitBtn.innerHTML = loading
      ? '<span class="spinner-border spinner-border-sm me-1"></span>Создание...'
      : '<i class="bi-check-lg me-1"></i>Создать';
  }
  
  // Очистка формы при открытии модала
  modal.addEventListener('show.bs.modal', function() {
    form.reset();
    clearFormErrors();
  });
  
  // Обработка отправки формы
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    
    console.log('Form submit event triggered');
    
    // Очистка предыдущих ошибок
    clearFormErrors();
    
    // Валидация
    if (!validateRequiredFields()) {
      displayGeneralError('Пожалуйста, заполните все обязательные поля (отмечены <span class="text-danger">*</span>)');
      return false;
    }
    
    // Блокируем кнопку
    setSubmitButtonState(true);
    
    // Собираем данные
    const formData = new FormData(form);
    
    try {
      const response = await fetch(submitUrl, {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        }
      });
      
      const data = await response.json();
      
      if (response.ok && data.success) {
        // Успех - закрываем модал
        bootstrap.Modal.getInstance(modal).hide();
        
        // Показываем уведомление
        if (data.message) {
          showSuccessNotification(data.message);
        }
        
        // Перенаправление
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        } else {
          window.location.reload();
        }
      } else {
        // Обработка ошибок
        if (data.errors && typeof data.errors === 'object') {
          displayFieldErrors(data.errors);
        } else {
          displayGeneralError(data.error || 'Произошла ошибка при создании сотрудника');
        }
      }
    } catch (error) {
      console.error('Network error:', error);
      displayGeneralError('Ошибка сети. Проверьте подключение и попробуйте снова.');
    } finally {
      setSubmitButtonState(false);
    }
    
    return false;
  }, true); // capture phase
}

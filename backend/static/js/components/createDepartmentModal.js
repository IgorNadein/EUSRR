/**
 * createDepartmentModal.js
 * Обработчик модального окна создания отдела
 */

export function initCreateDepartmentModal(options = {}) {
  const {
    modalId = 'createDepartmentModal',
    formId = 'createDepartmentForm',
    errorsId = 'createDepartmentErrors',
    submitBtnId = 'createDepartmentSubmit',
    submitUrl = '/api/v1/departments/'
  } = options;

  const modal = document.getElementById(modalId);
  const form = document.getElementById(formId);
  const errorsDiv = document.getElementById(errorsId);
  const submitBtn = document.getElementById(submitBtnId);
  
  if (!modal || !form) {
    console.error('Modal or form not found!', { modalId, formId });
    return;
  }
  
  console.log('Create department modal initialized');
  
  // Маппинг полей для человекочитаемых названий
  const fieldLabels = {
    'name': 'Название',
    'description': 'Описание'
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
    const name = form.querySelector('[name="name"]');
    let hasErrors = false;
    
    if (!name.value.trim()) {
      name.classList.add('is-invalid');
      const feedback = document.createElement('div');
      feedback.className = 'invalid-feedback';
      feedback.textContent = 'Название обязательно для заполнения';
      name.parentElement.appendChild(feedback);
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
  
  /**
   * Получить JWT токен из мета-тега
   */
  function getJWTToken() {
    const meta = document.querySelector('meta[name="api-access"]');
    return meta ? meta.content : '';
  }
  
  /**
   * Получить CSRF токен из формы или cookie
   */
  function getCSRFToken() {
    // Сначала пробуем получить из формы
    const tokenInput = form.querySelector('[name="csrfmiddlewaretoken"]');
    if (tokenInput && tokenInput.value) {
      return tokenInput.value;
    }
    
    // Если нет в форме, пробуем получить из cookie
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='));
    return cookieValue ? cookieValue.split('=')[1] : '';
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
    
    console.log('Form submit event triggered');
    
    // Очистка предыдущих ошибок
    clearFormErrors();
    
    // Валидация
    if (!validateRequiredFields()) {
      displayGeneralError('Пожалуйста, заполните название отдела');
      return;
    }
    
    // Блокируем кнопку
    setSubmitButtonState(true);
    
    // Собираем данные
    const formData = {
      name: form.querySelector('[name="name"]').value.trim(),
      description: form.querySelector('[name="description"]').value.trim()
    };
    
    const token = getJWTToken();
    const csrfToken = getCSRFToken();
    const headers = {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }
    
    try {
      console.log('Sending request to:', submitUrl);
      console.log('Headers:', headers);
      console.log('Data:', formData);
      
      const response = await fetch(submitUrl, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(formData)
      });
      
      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);
      
      const data = await response.json();
      console.log('Response data:', data);
      
      if (response.ok) {
        // Успех - закрываем модал
        bootstrap.Modal.getInstance(modal).hide();
        
        // Показываем уведомление
        showSuccessNotification(`Отдел "${formData.name}" успешно создан`);
        
        // Перезагружаем страницу или перенаправляем
        if (data.id) {
          setTimeout(() => {
            window.location.href = `/employees/departments/${data.id}/`;
          }, 1000);
        } else {
          setTimeout(() => {
            window.location.reload();
          }, 1000);
        }
      } else {
        // Обработка ошибок
        if (data.errors && typeof data.errors === 'object') {
          displayFieldErrors(data.errors);
        } else if (data.detail) {
          displayGeneralError(data.detail);
        } else {
          displayGeneralError('Произошла ошибка при создании отдела');
        }
      }
    } catch (error) {
      console.error('Network error:', error);
      displayGeneralError('Ошибка сети. Проверьте подключение и попробуйте снова.');
    } finally {
      setSubmitButtonState(false);
    }
  });
}

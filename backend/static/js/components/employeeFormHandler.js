/**
 * employeeFormHandler.js
 * Обработка отправки формы редактирования сотрудника через AJAX
 * с отображением ошибок валидации inline без перезагрузки страницы
 */
export function initEmployeeForm(options = {}) {
  const formId = options.formId || 'apiEditForm';
  const form = document.getElementById(formId);

  if (!form) {
    console.warn('[EmployeeForm] Форма не найдена, инициализация пропущена');
    return null;
  }

  console.info('[EmployeeForm] Инициализация AJAX обработчика формы');

  // Перехватываем submit формы
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnLabel = submitBtn?.querySelector('.btn-label');
    const btnSpinner = submitBtn?.querySelector('.btn-spinner');
    
    // Очищаем предыдущие ошибки
    clearFormErrors(form);
    
    // Показываем индикатор загрузки
    if (submitBtn) submitBtn.disabled = true;
    if (btnLabel) btnLabel.classList.add('d-none');
    if (btnSpinner) btnSpinner.classList.remove('d-none');
    
    try {
      const endpoint = form.dataset.endpoint || form.action;
      const formData = new FormData(form);
      
      console.log('[EmployeeForm] Отправка данных на:', endpoint);
      
      const response = await fetch(endpoint, {
        method: 'PATCH',
        body: formData,
        headers: {
          'X-CSRFToken': formData.get('csrfmiddlewaretoken') || ''
        }
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log('[EmployeeForm] Успешно сохранено');
        showSuccessMessage('Изменения сохранены');
        
        // Обновляем страницу через 1 секунду
        setTimeout(() => {
          location.reload();
        }, 1000);
      } else {
        console.warn('[EmployeeForm] Ошибка валидации:', data);
        displayFormErrors(form, data);
        showErrorMessage('Исправьте ошибки в форме');
      }
    } catch (error) {
      console.error('[EmployeeForm] Ошибка отправки:', error);
      showErrorMessage('Произошла ошибка при сохранении');
    } finally {
      // Возвращаем кнопку в нормальное состояние
      if (submitBtn) submitBtn.disabled = false;
      if (btnLabel) btnLabel.classList.remove('d-none');
      if (btnSpinner) btnSpinner.classList.add('d-none');
    }
  });

  return {
    setSubmitting: (state) => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = state;
    },
    refresh: () => location.reload()
  };
}

/**
 * Очистка всех ошибок в форме
 */
function clearFormErrors(form) {
  // Убираем класс is-invalid со всех полей
  form.querySelectorAll('.is-invalid').forEach(el => {
    el.classList.remove('is-invalid');
  });
  
  // Очищаем все сообщения об ошибках
  form.querySelectorAll('.invalid-feedback').forEach(el => {
    el.textContent = '';
    el.style.display = 'none';
  });
}

/**
 * Отображение ошибок валидации в полях формы
 */
function displayFormErrors(form, errors) {
  // errors может быть объектом с полями или массивом строк
  if (Array.isArray(errors)) {
    // Общие ошибки (non_field_errors)
    showErrorMessage(errors.join(', '));
    return;
  }
  
  if (typeof errors === 'object') {
    // Обрабатываем специальный случай с полем "detail"
    if (errors.detail && Object.keys(errors).length === 1) {
      // Пытаемся распарсить detail, если там есть информация о полях
      const detailStr = String(errors.detail);
      
      // Проверяем, есть ли в detail информация о конкретных полях
      // Формат: "Internal server error: {'field': [ErrorDetail(...)]}"
      const fieldMatch = detailStr.match(/\{'(\w+)':\s*\[(.*?)\]/);
      
      if (fieldMatch) {
        const fieldName = fieldMatch[1];
        const errorText = fieldMatch[2];
        
        // Извлекаем читаемое сообщение об ошибке
        const msgMatch = errorText.match(/ErrorDetail\(string='([^']+)'/);
        const errorMessage = msgMatch ? msgMatch[1] : errorText;
        
        // Показываем ошибку в конкретном поле
        const field = form.querySelector(`[name="${fieldName}"]`);
        
        if (field) {
          field.classList.add('is-invalid');
          
          let feedbackEl = field.parentElement.querySelector('.invalid-feedback');
          
          if (!feedbackEl) {
            feedbackEl = document.createElement('div');
            feedbackEl.className = 'invalid-feedback';
            field.parentElement.appendChild(feedbackEl);
          }
          
          feedbackEl.textContent = errorMessage;
          feedbackEl.style.display = 'block';
          
          console.log(`[EmployeeForm] Ошибка в поле ${fieldName}:`, errorMessage);
        } else {
          // Если поле не найдено, показываем общую ошибку
          showErrorMessage(errorMessage);
        }
      } else {
        // Если не удалось распарсить, показываем как общую ошибку
        showErrorMessage(detailStr);
      }
      
      return;
    }
    
    // Стандартная обработка ошибок по полям
    Object.keys(errors).forEach(fieldName => {
      const errorMessages = Array.isArray(errors[fieldName]) 
        ? errors[fieldName] 
        : [errors[fieldName]];
      
      // Ищем поле по имени
      const field = form.querySelector(`[name="${fieldName}"]`);
      
      if (field) {
        // Добавляем класс ошибки
        field.classList.add('is-invalid');
        
        // Ищем или создаём контейнер для ошибки
        let feedbackEl = field.parentElement.querySelector('.invalid-feedback');
        
        if (!feedbackEl) {
          feedbackEl = document.createElement('div');
          feedbackEl.className = 'invalid-feedback';
          field.parentElement.appendChild(feedbackEl);
        }
        
        // Показываем сообщение об ошибке
        feedbackEl.textContent = errorMessages.join(', ');
        feedbackEl.style.display = 'block';
        
        console.log(`[EmployeeForm] Ошибка в поле ${fieldName}:`, errorMessages);
      } else if (fieldName === 'non_field_errors') {
        // Общие ошибки формы
        showErrorMessage(errorMessages.join(', '));
      } else {
        console.warn(`[EmployeeForm] Поле ${fieldName} не найдено в форме`);
        // Показываем как общую ошибку
        showErrorMessage(`${fieldName}: ${errorMessages.join(', ')}`);
      }
    });
  }
}

/**
 * Показ сообщения об успехе
 */
function showSuccessMessage(message) {
  // Можно использовать toast или простой alert
  const alertDiv = document.createElement('div');
  alertDiv.className = 'alert alert-success alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3';
  alertDiv.style.zIndex = '9999';
  alertDiv.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  document.body.appendChild(alertDiv);
  
  // Автоматически убираем через 3 секунды
  setTimeout(() => {
    alertDiv.remove();
  }, 3000);
}

/**
 * Показ сообщения об ошибке
 */
function showErrorMessage(message) {
  const alertDiv = document.createElement('div');
  alertDiv.className = 'alert alert-danger alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3';
  alertDiv.style.zIndex = '9999';
  alertDiv.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  document.body.appendChild(alertDiv);
  
  // Автоматически убираем через 5 секунд
  setTimeout(() => {
    alertDiv.remove();
  }, 5000);
}

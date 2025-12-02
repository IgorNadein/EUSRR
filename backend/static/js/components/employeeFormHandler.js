/**
 * employeeFormHandler.js
 * Минимальный стаб, оставленный ради обратной совместимости после
 * отказа от кастомного JS-сабмита. Теперь форма отправляется браузером
 * напрямую в фронтовую Django-вьюху, а модуль лишь возвращает
 * совместимое API без вмешательства в submit.
 */
export function initEmployeeForm(options = {}) {
  const formId = options.formId || 'apiEditForm';
  const form = document.getElementById(formId);
  if (!form) {
    console.warn('[EmployeeForm] Форма не найдена, инициализация пропущена');
    return null;
  }

  // Новый обработчик: submit через fetch
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    // Очищаем старые ошибки
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

    const endpoint = form.dataset.endpoint || form.action;
    const formData = new FormData(form);
    let payload = {};
    formData.forEach((value, key) => {
      if (payload[key]) {
        if (!Array.isArray(payload[key])) payload[key] = [payload[key]];
        payload[key].push(value);
      } else {
        payload[key] = value;
      }
    });

    // Если есть файл, отправляем multipart, иначе json
    let fetchOptions = {
      method: 'POST',
      headers: {
        'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
      }
    };
    if (form.enctype === 'multipart/form-data') {
      fetchOptions.body = formData;
      delete fetchOptions.headers['Content-Type'];
    } else {
      fetchOptions.headers['Content-Type'] = 'application/json';
      fetchOptions.body = JSON.stringify(payload);
    }

    try {
      const response = await fetch(endpoint, fetchOptions);
      const data = await response.json();
      if (response.ok) {
        // Успех: можно обновить данные или закрыть форму
        if (options.onSuccess) options.onSuccess(data);
        else location.reload();
      } else {
        // Ошибки: показываем в форме
        if (data && typeof data === 'object') {
          for (const [field, errors] of Object.entries(data)) {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
              input.classList.add('is-invalid');
              let feedback = input.parentElement.querySelector('.invalid-feedback');
              if (!feedback) {
                feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                input.parentElement.appendChild(feedback);
              }
              feedback.textContent = Array.isArray(errors) ? errors.join(' ') : errors;
            }
          }
        }
      }
    } catch (err) {
      alert('Ошибка отправки формы: ' + err);
    }
  });

  return {
    setSubmitting: (v) => {},
    refresh: () => location.reload()
  };
}

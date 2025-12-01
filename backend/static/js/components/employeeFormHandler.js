/**
 * employeeFormHandler.js
 * Обработчик формы редактирования сотрудника через API
 * 
 * @module employeeFormHandler
 * @version 1.0.0
 */

/**
 * Инициализация обработчика формы редактирования сотрудника
 * @param {Object} options - Параметры инициализации
 * @param {string} options.formId - ID формы (по умолчанию 'apiEditForm')
 * @param {string[]} options.contactFields - Список полей контактов для валидации
 * @returns {Object} API формы { refresh, submit, clearErrors }
 */
export function initEmployeeForm(options = {}) {
  const config = {
    formId: options.formId || 'apiEditForm',
    contactFields: options.contactFields || ['email', 'phone_number', 'telegram', 'whatsapp', 'wechat']
  };

  const form = document.getElementById(config.formId);
  if (!form) {
    return null; // Тихий выход, если форма не найдена
  }

  const endpoint = form.dataset.endpoint || '';
  if (!endpoint) {
    console.warn('Employee form: endpoint not found');
    return null;
  }

  const CONTACT_FIELDS = config.contactFields;
  const btn = form.querySelector('[type="submit"]');
  const btnLabel = btn?.querySelector('.btn-label');
  const btnSpin = btn?.querySelector('.btn-spinner');

  /**
   * Установить состояние отправки формы
   */
  function setSubmitting(on) {
    if (!btn) return;
    if (on) {
      btn.setAttribute('disabled', '');
      btnSpin?.classList.remove('d-none');
      btnLabel?.classList.add('visually-hidden');
    } else {
      btn.removeAttribute('disabled');
      btnSpin?.classList.add('d-none');
      btnLabel?.classList.remove('visually-hidden');
    }
  }

  /**
   * Очистить все ошибки валидации
   */
  function clearErrors() {
    form.querySelectorAll('.is-invalid').forEach((el) => el.classList.remove('is-invalid'));
    form.querySelectorAll('.invalid-feedback').forEach((el) => (el.textContent = ''));
  }

  /**
   * Показать ошибку для конкретного поля
   */
  function fieldError(name, message) {
    const el = form.querySelector(`[name="${CSS.escape(name)}"]`);
    if (!el) return;
    el.classList.add('is-invalid');
    const container = el.closest('[class^="col-"]') || el.parentElement;
    let fb = container?.querySelector('.invalid-feedback');
    if (!fb) {
      fb = document.createElement('div');
      fb.className = 'invalid-feedback';
      el.after(fb);
    }
    fb.textContent = message || 'Некорректное значение';
  }

  /**
   * Валидация наличия хотя бы одного контакта
   */
  function ensureOneContact() {
    const hasAny = CONTACT_FIELDS.some((n) => (form.elements[n]?.value || '').trim().length > 0);
    if (hasAny) return true;
    CONTACT_FIELDS.forEach((n) => fieldError(n, 'Укажите хотя бы один контакт'));
    form.elements[CONTACT_FIELDS[0]]?.focus();
    return false;
  }

  /**
   * Прочитать файл в Base64
   */
  function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(fr.result);
      fr.onerror = reject;
      fr.readAsDataURL(file);
    });
  }

  /**
   * Собрать skills_ids (массив) и сравнить с начальным значением
   */
  function collectSkillsPayload() {
    const sel = form.querySelector('select[name="skills_ids"]');
    if (!sel) return null;
    const selected = Array.from(sel.selectedOptions)
      .map((o) => o.value)
      .filter(Boolean);
    const initCsv = sel.dataset.init || '';
    const initArr = initCsv
      ? initCsv
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      : [];
    // Сравнение (без учёта порядка)
    const norm = (a) => a.slice().sort().join(',');
    if (norm(selected) === norm(initArr)) return null;
    return selected;
  }

  /**
   * Собрать общие поля (кроме skills_ids и avatar)
   */
  function buildScalarPayload() {
    const payload = {};
    const fields = form.querySelectorAll(
      'input[name]:not([type="file"]):not([name="clear_avatar"]):not(:disabled), select[name]:not([name="skills_ids"]):not(:disabled)'
    );

    fields.forEach((el) => {
      const name = el.name;
      const raw = (el.value ?? '').toString().trim();
      const init = (el.dataset.init ?? el.defaultValue ?? '').toString();

      // Ничего не менялось
      if (raw === init) return;

      // Пустое значение: для некоторых полей нужно слать null
      const shouldNull = raw === '' && ['gender', 'birth_date', 'position_id'].includes(name);

      if (shouldNull) {
        // Меняем непустое init -> null (очистка)
        if (init !== '') payload[name] = null;
        return;
      }

      // Типизация gender в число
      if (name === 'gender' && raw !== '') {
        payload[name] = Number(raw);
        return;
      }

      // Остальные — как есть (пустые строки допустимы для текстовых полей)
      payload[name] = raw;
    });

    return payload;
  }

  /**
   * Обработчик отправки формы
   */
  async function handleSubmit(e) {
    e.preventDefault();
    clearErrors();

    if (!ensureOneContact()) return;

    setSubmitting(true);
    try {
      const payload = buildScalarPayload();

      // skills_ids (массив)
      const skills = collectSkillsPayload();
      if (skills) payload.skills_ids = skills;

      // avatar (файл через FormData)
      const avatarInput = document.getElementById('avatarInput');
      const avatarFile = avatarInput?.files?.[0] || null;
      
      console.log('[EmployeeForm] Avatar input:', avatarInput);
      console.log('[EmployeeForm] Avatar file:', avatarFile);
      console.log('[EmployeeForm] Payload:', payload);
      
      let body;
      let headers = {
        'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''
      };

      if (avatarFile) {
        // Если есть файл - используем FormData
        console.log('[EmployeeForm] Using FormData with avatar:', avatarFile.name, avatarFile.size);
        const formData = new FormData();
        formData.append('avatar', avatarFile);
        
        // Добавляем остальные поля
        Object.entries(payload).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            value.forEach(v => formData.append(key, v));
          } else {
            formData.append(key, value);
          }
        });
        
        if (skills) {
          skills.forEach(id => formData.append('skills_ids', id));
        }
        
        body = formData;
        console.log('[EmployeeForm] FormData entries:');
        for (let [key, value] of formData.entries()) {
          console.log(`  ${key}:`, value);
        }
        // Не устанавливаем Content-Type для FormData - браузер сам добавит boundary
      } else {
        // Если файла нет - используем JSON
        console.log('[EmployeeForm] Using JSON (no avatar)');
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(payload);
      }

      // Если нечего отправлять — просто обновим UI
      if (Object.keys(payload).length === 0 && !avatarFile) {
        console.log('[EmployeeForm] Nothing to save, reloading...');
        setSubmitting(false);
        if (window.bootstrap) {
          try {
            new bootstrap.Collapse(document.getElementById('editFormWrap'), { toggle: false }).hide();
          } catch (_) {}
        }
        location.reload();
        return;
      }

      console.log('[EmployeeForm] Sending PATCH request to:', endpoint);
      console.log('[EmployeeForm] Headers:', headers);
      console.log('[EmployeeForm] Body type:', body instanceof FormData ? 'FormData' : typeof body);
      
      const resp = await fetch(endpoint, {
        method: 'PATCH',
        headers: headers,
        body: body,
        credentials: 'same-origin'
      });
      
      console.log('[EmployeeForm] Response status:', resp.status, resp.statusText);

      if (!resp.ok) {
        let body = null;
        try {
          body = await resp.json();
        } catch {}
        if (body && typeof body === 'object') {
          let shown = false;
          for (const [k, v] of Object.entries(body)) {
            if (k === 'detail') continue;
            const msg = Array.isArray(v) ? v.join(' ') : String(v);
            fieldError(k, msg);
            shown = true;
          }
          if (body.detail) alert(body.detail);
          else if (!shown) alert('Не удалось сохранить изменения (ошибка валидации).');
        } else {
          const t = await resp.text();
          alert('Не удалось сохранить изменения.\n' + (t || `HTTP ${resp.status}`));
        }
        setSubmitting(false);
        return;
      }

      // Успех
      try {
        if (window.bootstrap)
          new bootstrap.Collapse(document.getElementById('editFormWrap'), { toggle: false }).hide();
      } catch (_) {}
      location.reload();
    } catch (err) {
      console.error(err);
      alert('Не удалось сохранить изменения. Попробуйте ещё раз.');
      setSubmitting(false);
    }
  }

  form.addEventListener('submit', handleSubmit);

  // API возвращаем для внешнего использования
  return {
    clearErrors,
    setSubmitting,
    fieldError,
    refresh: () => location.reload()
  };
}

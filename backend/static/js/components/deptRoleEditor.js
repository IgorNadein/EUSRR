/**
 * deptRoleEditor.js
 * Валидация и управление редактором роли в отделе
 * Активирует кнопку OK только при изменении значения
 * 
 * @module deptRoleEditor
 * @version 1.0.0
 */

/**
 * Инициализация редакторов ролей в отделах
 * Находит все формы .dept-editor и активирует валидацию
 * @returns {Object} Публичный API
 */
export function initDeptRoleEditor() {
  const editors = document.querySelectorAll('.dept-editor form');
  
  if (!editors.length) {
    console.log('deptRoleEditor: no editors found');
    return null;
  }

  const instances = [];

  editors.forEach(form => {
    const select = form.querySelector('select[name="role_id"]');
    const okBtn = form.querySelector('.dept-role-save');
    
    if (!select || !okBtn) return;

    const initial = select.value ?? '';

    // Функция проверки изменений
    const checkChanges = () => {
      okBtn.disabled = (select.value === initial);
    };

    // Начальная проверка и подписка на изменения
    checkChanges();
    select.addEventListener('change', checkChanges);

    instances.push({ form, select, okBtn, initial });
  });

  // Инициализация tooltips для редакторов (если Bootstrap доступен)
  if (window.bootstrap?.Tooltip) {
    document.querySelectorAll('.dept-editor-wrap.collapse').forEach(col => {
      col.addEventListener('shown.bs.collapse', () => {
        col.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
          if (!el._tooltip) {
            el._tooltip = new bootstrap.Tooltip(el);
          }
        });
      });
    });
  }

  console.log(`deptRoleEditor: initialized ${instances.length} editor(s)`);

  return {
    instances,
    refresh: () => {
      instances.forEach(({ select, okBtn, initial }) => {
        okBtn.disabled = (select.value === initial);
      });
    }
  };
}

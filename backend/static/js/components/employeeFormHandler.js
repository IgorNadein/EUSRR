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

  console.info('[EmployeeForm] JS-обработчик отключён, используется нативная отправка формы');

  const noop = () => {};
  return {
    setSubmitting: noop,
    refresh: () => location.reload()
  };
}

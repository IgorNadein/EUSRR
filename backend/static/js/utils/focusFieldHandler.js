/**
 * @module focusFieldHandler
 * @description Утилита для автофокуса на элементе формы.
 * Устанавливает фокус после загрузки DOM или немедленно, если DOM уже готов.
 * 
 * Использование:
 * import { focusField } from './focusFieldHandler.js';
 * focusField('id_email');
 * 
 * @example
 * // С задержкой
 * focusField('id_code', 100);
 */

/**
 * Устанавливает фокус на элемент формы.
 * @param {string} elementId - ID элемента для фокуса
 * @param {number} [delay=0] - Задержка перед фокусом (мс)
 */
export function focusField(elementId, delay = 0) {
  if (!elementId) {
    console.warn('focusField: elementId не указан');
    return;
  }

  /**
   * Выполнить фокус на элементе.
   */
  function performFocus() {
    const element = document.getElementById(elementId);
    
    if (!element) {
      console.warn(`focusField: элемент #${elementId} не найден`);
      return;
    }

    if (delay > 0) {
      setTimeout(() => {
        element.focus();
      }, delay);
    } else {
      element.focus();
    }
  }

  // Если DOM уже готов, выполняем немедленно
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', performFocus);
  } else {
    performFocus();
  }
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.focusField = focusField;
}

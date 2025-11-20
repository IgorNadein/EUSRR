/**
 * @module phoneValidationHandler
 * @description Обработчик валидации и санитизации телефонных номеров.
 * Автоматически очищает ввод от недопустимых символов, поддерживает международный формат.
 * Использует HTML5 Constraint Validation API для показа ошибок.
 * 
 * Пример HTML:
 * <input type="tel" name="phone" data-phone-only>
 * 
 * Использование:
 * import { initPhoneValidation } from './phoneValidationHandler.js';
 * initPhoneValidation();
 */

/** Регулярное выражение для проверки телефонного номера (10-15 цифр, опционально +) */
const PHONE_RE = /^\+?\d{10,15}$/;

/**
 * Санитизация телефонного номера: оставляет только цифры и +.
 * @param {string} value - Исходное значение
 * @returns {string} Очищенное значение
 */
function sanitizePhone(value) {
  value = String(value || '');
  let output = '';
  
  for (let i = 0; i < value.length; i++) {
    const char = value[i];
    
    // Цифры пропускаем всегда
    if (char >= '0' && char <= '9') {
      output += char;
      continue;
    }
    
    // Плюс только в начале
    if (char === '+' && output.length === 0) {
      output = '+';
    }
  }
  
  return output;
}

/**
 * Валидация телефонного номера с установкой кастомного сообщения об ошибке.
 * @param {HTMLInputElement} element - Поле ввода телефона
 */
function validatePhone(element) {
  const value = element.value;
  const isValid = value === '' || PHONE_RE.test(value);
  
  element.setCustomValidity(
    isValid 
      ? '' 
      : 'Введите номер телефона в формате +79991234567 (10–15 цифр).'
  );
}

/**
 * Инициализирует валидацию телефонных номеров для всех элементов с атрибутом data-phone-only.
 * @param {Object} options - Опции инициализации
 * @param {string} [options.selector='[data-phone-only]'] - CSS-селектор для полей телефона
 * @param {RegExp} [options.pattern] - Пользовательский паттерн валидации
 * @param {string} [options.errorMessage] - Пользовательское сообщение об ошибке
 * @returns {Object} API с методом destroy
 */
export function initPhoneValidation(options = {}) {
  const {
    selector = '[data-phone-only]',
    pattern = PHONE_RE,
    errorMessage = 'Введите номер телефона в формате +79991234567 (10–15 цифр).'
  } = options;

  const phoneInputs = document.querySelectorAll(selector);
  const handlers = new WeakMap();

  /**
   * Обработчик ввода: санитизация и валидация.
   * @param {Event} e - Событие input
   */
  function handleInput(e) {
    const element = e.target;
    const previousValue = element.value;
    const currentValue = sanitizePhone(previousValue);
    
    if (previousValue !== currentValue) {
      const cursorPosition = element.selectionStart || currentValue.length;
      const diff = previousValue.length - currentValue.length;
      
      element.value = currentValue;
      
      try {
        const newPosition = Math.max(0, cursorPosition - diff);
        element.setSelectionRange(newPosition, newPosition);
      } catch (e) {
        // Игнорируем ошибки setSelectionRange (могут быть в некоторых браузерах)
      }
    }
    
    validatePhone(element);
  }

  /**
   * Обработчик вставки: очищает вставляемый текст.
   * @param {ClipboardEvent} e - Событие paste
   */
  function handlePaste(e) {
    e.preventDefault();
    const clipboardData = e.clipboardData || window.clipboardData;
    const text = clipboardData.getData('text');
    const cleanedText = sanitizePhone(text);
    
    // Используем document.execCommand для сохранения истории undo/redo
    document.execCommand('insertText', false, cleanedText);
  }

  /**
   * Обработчик потери фокуса: финальная санитизация и валидация.
   * @param {Event} e - Событие blur
   */
  function handleBlur(e) {
    const element = e.target;
    element.value = sanitizePhone(element.value);
    validatePhone(element);
  }

  // Установка обработчиков для каждого поля
  phoneInputs.forEach((element) => {
    const elementHandlers = {
      input: handleInput.bind(null),
      paste: handlePaste.bind(null),
      blur: handleBlur.bind(null)
    };
    
    element.addEventListener('input', elementHandlers.input);
    element.addEventListener('paste', elementHandlers.paste);
    element.addEventListener('blur', elementHandlers.blur);
    
    // Сохраняем ссылки на обработчики для последующего удаления
    handlers.set(element, elementHandlers);
    
    // Инициализация: санитизация и валидация начального значения
    element.value = sanitizePhone(element.value);
    validatePhone(element);
  });

  /**
   * Функция для удаления всех обработчиков.
   */
  function destroy() {
    phoneInputs.forEach((element) => {
      const elementHandlers = handlers.get(element);
      if (elementHandlers) {
        element.removeEventListener('input', elementHandlers.input);
        element.removeEventListener('paste', elementHandlers.paste);
        element.removeEventListener('blur', elementHandlers.blur);
        handlers.delete(element);
      }
    });
  }

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initPhoneValidation = initPhoneValidation;
}

/**
 * @module liveValidationHandler
 * @description Валидация формы в реальном времени с подсветкой ошибок.
 * Проверяет поля по мере ввода и показывает feedback сразу.
 * 
 * Использование:
 * import { initLiveValidation } from './liveValidationHandler.js';
 * 
 * initLiveValidation({
 *   formSelector: '#registrationForm',
 *   rules: {
 *     email: [
 *       { type: 'required', message: 'Email обязателен' },
 *       { type: 'email', message: 'Введите корректный email' }
 *     ],
 *     phone_number: [
 *       { type: 'required', message: 'Телефон обязателен' },
 *       { type: 'pattern', pattern: /^\+?\d{10,15}$/, message: 'Неверный формат телефона' }
 *     ],
 *     password1: [
 *       { type: 'required', message: 'Пароль обязателен' },
 *       { type: 'minLength', value: 6, message: 'Минимум 6 символов' }
 *     ],
 *     password2: [
 *       { type: 'required', message: 'Подтвердите пароль' },
 *       { type: 'match', field: 'password1', message: 'Пароли не совпадают' }
 *     ],
 *     gender: [
 *       { type: 'required', message: 'Укажите пол' }
 *     ]
 *   }
 * });
 */

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
 * Валидаторы для различных типов проверок
 */
const validators = {
  required: (value, input) => {
    // Специальная обработка для file input
    if (input && input.type === 'file') {
      return input.files && input.files.length > 0;
    }
    
    if (typeof value === 'string') {
      return value.trim().length > 0;
    }
    return value !== null && value !== undefined && value !== '';
  },

  email: (value) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value);
  },

  pattern: (value, pattern) => {
    return pattern.test(value);
  },

  minLength: (value, minLen) => {
    return value.length >= minLen;
  },

  maxLength: (value, maxLen) => {
    return value.length <= maxLen;
  },

  match: (value, formData, fieldName) => {
    return value === formData[fieldName];
  },

  // Специальная валидация для контактов (хотя бы один)
  anyContact: (value, formData, fieldName, fields) => {
    return fields.some(field => {
      const val = formData[field];
      return val && val.trim().length > 0;
    });
  }
};

/**
 * Проверяет поле на соответствие правилам
 * @param {HTMLInputElement|HTMLSelectElement} input - Элемент поля
 * @param {Array} rules - Массив правил валидации
 * @param {Object} formData - Данные всей формы
 * @returns {Object} { valid: boolean, message: string }
 */
function validateField(input, rules, formData) {
  if (!rules || rules.length === 0) {
    return { valid: true, message: '' };
  }

  const value = input.value;
  const fieldName = input.name;

  for (const rule of rules) {
    let isValid = true;

    switch (rule.type) {
      case 'required':
        isValid = validators.required(value, input);
        break;

      case 'email':
        // Email проверяем только если поле не пустое
        if (value.trim().length > 0) {
          isValid = validators.email(value);
        }
        break;

      case 'pattern':
        // Pattern проверяем только если поле не пустое
        if (value.trim().length > 0) {
          isValid = validators.pattern(value, rule.pattern);
        } else if (rule.required === false) {
          // Если поле опциональное и пустое - валидно
          isValid = true;
        } else {
          // Если поле обязательное, но пустое - будет проверено правилом required
          isValid = true;
        }
        break;

      case 'minLength':
        // MinLength проверяем только если поле не пустое
        if (value.trim().length > 0) {
          isValid = validators.minLength(value, rule.value);
        }
        break;

      case 'maxLength':
        isValid = validators.maxLength(value, rule.value);
        break;

      case 'match':
        isValid = validators.match(value, formData, rule.field);
        break;

      case 'anyContact':
        isValid = validators.anyContact(value, formData, fieldName, rule.fields);
        break;

      default:
        // Кастомная функция валидации
        if (typeof rule.validate === 'function') {
          isValid = rule.validate(value, formData, input);
        }
    }

    if (!isValid) {
      return { valid: false, message: rule.message };
    }
  }

  return { valid: true, message: '' };
}

/**
 * Отображает feedback для поля
 * @param {HTMLInputElement|HTMLSelectElement} input - Элемент поля
 * @param {boolean} valid - Валидно ли поле
 * @param {string} message - Сообщение об ошибке
 */
function showFieldFeedback(input, valid, message) {
  // Очищаем HTML5 custom validity чтобы не конфликтовать
  input.setCustomValidity('');
  
  // Удаляем старые классы
  input.classList.remove('is-valid', 'is-invalid');

  // Ищем существующий feedback или создаём новый
  let feedbackEl = input.parentElement.querySelector('.invalid-feedback');
  
  if (!feedbackEl) {
    feedbackEl = document.createElement('div');
    feedbackEl.className = 'invalid-feedback';
    input.parentElement.appendChild(feedbackEl);
  }

  if (valid) {
    input.classList.add('is-valid');
    feedbackEl.textContent = '';
    feedbackEl.style.display = 'none';
  } else {
    input.classList.add('is-invalid');
    feedbackEl.textContent = message;
    feedbackEl.style.display = 'block';
  }
}

/**
 * Очищает feedback для поля
 * @param {HTMLInputElement|HTMLSelectElement} input - Элемент поля
 */
function clearFieldFeedback(input) {
  input.classList.remove('is-valid', 'is-invalid');
  const feedbackEl = input.parentElement.querySelector('.invalid-feedback');
  if (feedbackEl) {
    feedbackEl.textContent = '';
    feedbackEl.style.display = 'none';
  }
}

/**
 * Собирает данные формы в объект
 * @param {HTMLFormElement} form - Элемент формы
 * @returns {Object} Данные формы
 */
function getFormData(form) {
  const formData = {};
  const elements = form.elements;

  for (let i = 0; i < elements.length; i++) {
    const element = elements[i];
    if (element.name) {
      if (element.type === 'radio') {
        if (element.checked) {
          formData[element.name] = element.value;
        }
      } else if (element.type === 'checkbox') {
        formData[element.name] = element.checked;
      } else {
        formData[element.name] = element.value;
      }
    }
  }

  return formData;
}

/**
 * Инициализирует live validation для формы
 * @param {Object} options - Настройки
 * @param {string} options.formSelector - CSS селектор формы
 * @param {Object} options.rules - Правила валидации для полей
 * @param {number} [options.debounce=300] - Задержка перед валидацией (мс)
 * @param {boolean} [options.validateOnBlur=true] - Валидировать при потере фокуса
 * @param {boolean} [options.validateOnInput=true] - Валидировать при вводе
 * @param {boolean} [options.validateOnSubmit=true] - Валидировать при отправке
 * @returns {Object} API для управления валидацией
 */
export function initLiveValidation(options = {}) {
  const {
    formSelector,
    rules = {},
    debounce = 300,
    validateOnBlur = true,
    validateOnInput = true,
    validateOnSubmit = true
  } = options;

  const form = document.querySelector(formSelector);
  if (!form) {
    console.error(`Form not found: ${formSelector}`);
    return null;
  }

  const validationTimers = {};
  const touchedFields = new Set();

  /**
   * Валидирует конкретное поле
   * @param {HTMLInputElement|HTMLSelectElement} input
   */
  const validateInput = (input) => {
    const fieldName = input.name;
    const fieldRules = rules[fieldName];

    if (!fieldRules) return;

    const formData = getFormData(form);
    const result = validateField(input, fieldRules, formData);

    showFieldFeedback(input, result.valid, result.message);
  };

  /**
   * Валидирует поле с задержкой (debounce)
   * @param {HTMLInputElement|HTMLSelectElement} input
   */
  const validateInputDebounced = (input) => {
    const fieldName = input.name;

    // Очищаем предыдущий таймер
    if (validationTimers[fieldName]) {
      clearTimeout(validationTimers[fieldName]);
    }

    // Устанавливаем новый таймер
    validationTimers[fieldName] = setTimeout(() => {
      validateInput(input);
    }, debounce);
  };

  /**
   * Обработчик ввода в поле
   */
  const handleInput = (e) => {
    const input = e.target;
    const fieldName = input.name;
    
    // Санитизация телефонных номеров
    if (input.type === 'tel') {
      const previousValue = input.value;
      const sanitized = sanitizePhone(previousValue);
      
      if (previousValue !== sanitized) {
        const cursorPosition = input.selectionStart || sanitized.length;
        const diff = previousValue.length - sanitized.length;
        
        input.value = sanitized;
        
        try {
          const newPosition = Math.max(0, cursorPosition - diff);
          input.setSelectionRange(newPosition, newPosition);
        } catch (err) {
          // Игнорируем ошибки setSelectionRange
        }
      }
    }

    if (!validateOnInput) return;

    // Валидируем только если поле уже было "тронуто"
    if (touchedFields.has(fieldName)) {
      validateInputDebounced(input);
    }
  };

  /**
   * Обработчик потери фокуса
   */
  const handleBlur = (e) => {
    const input = e.target;
    const fieldName = input.name;

    // Помечаем поле как "тронутое"
    touchedFields.add(fieldName);

    if (validateOnBlur && rules[fieldName]) {
      validateInput(input);
    }
  };

  /**
   * Обработчик отправки формы
   */
  const handleSubmit = (e) => {
    if (!validateOnSubmit) return;

    let isFormValid = true;
    const formData = getFormData(form);

    // Валидируем все поля с правилами
    for (const fieldName in rules) {
      const input = form.elements[fieldName];
      if (!input) continue;

      const result = validateField(input, rules[fieldName], formData);
      showFieldFeedback(input, result.valid, result.message);

      if (!result.valid) {
        isFormValid = false;
      }
    }

    // Прерываем отправку если есть ошибки
    if (!isFormValid) {
      e.preventDefault();
      
      // Фокусируем первое невалидное поле
      const firstInvalid = form.querySelector('.is-invalid');
      if (firstInvalid) {
        firstInvalid.focus();
      }
    }
  };

  // Навешиваем обработчики
  form.addEventListener('input', handleInput);
  form.addEventListener('blur', handleBlur, true); // true для capture phase
  form.addEventListener('submit', handleSubmit);

  /**
   * API для управления валидацией
   */
  return {
    /**
     * Валидирует конкретное поле вручную
     */
    validateField: (fieldName) => {
      const input = form.elements[fieldName];
      if (input) {
        touchedFields.add(fieldName);
        validateInput(input);
      }
    },

    /**
     * Валидирует всю форму
     */
    validateForm: () => {
      let isValid = true;
      const formData = getFormData(form);

      for (const fieldName in rules) {
        const input = form.elements[fieldName];
        if (!input) continue;

        const result = validateField(input, rules[fieldName], formData);
        showFieldFeedback(input, result.valid, result.message);

        if (!result.valid) {
          isValid = false;
        }
      }

      return isValid;
    },

    /**
     * Очищает валидацию для всех полей
     */
    clearValidation: () => {
      for (const fieldName in rules) {
        const input = form.elements[fieldName];
        if (input) {
          clearFieldFeedback(input);
        }
      }
      touchedFields.clear();
    },

    /**
     * Удаляет обработчики
     */
    destroy: () => {
      form.removeEventListener('input', handleInput);
      form.removeEventListener('blur', handleBlur, true);
      form.removeEventListener('submit', handleSubmit);
    }
  };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initLiveValidation = initLiveValidation;
}

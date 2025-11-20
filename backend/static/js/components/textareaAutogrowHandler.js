/**
 * @module textareaAutogrowHandler
 * @description Автоматическое изменение высоты textarea по мере ввода текста.
 * Поддерживает max-height с автоматическим включением скролла при достижении лимита.
 * 
 * Пример HTML:
 * <textarea class="form-control autogrow" maxlength="2000"></textarea>
 * 
 * Использование:
 * import { initTextareaAutogrow } from './textareaAutogrowHandler.js';
 * initTextareaAutogrow({ selector: 'textarea.autogrow' });
 */

/**
 * Подгоняет высоту textarea под содержимое.
 * @param {HTMLTextAreaElement} element - Элемент textarea
 */
function autosize(element) {
  // Сбрасываем высоту для корректного вычисления scrollHeight
  element.classList.remove('is-max');
  element.style.height = 'auto';

  const style = getComputedStyle(element);
  const isБorderBox = style.boxSizing === 'border-box';
  const borderHeight = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
  
  // Вычисляем необходимую высоту
  const desiredHeight = element.scrollHeight + (isBorderBox ? 0 : borderHeight);
  element.style.height = desiredHeight + 'px';

  // Если достигли max-height — включаем скролл
  const maxHeight = parseFloat(style.maxHeight);
  if (!Number.isNaN(maxHeight) && desiredHeight >= maxHeight) {
    element.style.height = style.maxHeight;
    element.classList.add('is-max');
  }
}

/**
 * Инициализирует автоматическое изменение размера для textarea.
 * @param {Object} options - Опции инициализации
 * @param {string} [options.selector='textarea.autogrow'] - CSS-селектор для textarea
 * @param {HTMLElement} [options.container=document] - Контейнер для поиска элементов
 * @returns {Object} API с методом destroy
 */
export function initTextareaAutogrow(options = {}) {
  const {
    selector = 'textarea.autogrow',
    container = document
  } = options;

  const textareas = Array.from(container.querySelectorAll(selector));
  
  if (!textareas.length) {
    console.warn('initTextareaAutogrow: элементы не найдены по селектору', selector);
    return { destroy: () => {} };
  }

  const handlers = new WeakMap();

  /**
   * Обработчик ввода текста.
   * @param {Event} e - Событие input
   */
  function handleInput(e) {
    autosize(e.target);
  }

  /**
   * Обработчик изменения размера окна.
   */
  function handleResize() {
    textareas.forEach(el => autosize(el));
  }

  // Устанавливаем обработчики для каждой textarea
  textareas.forEach(element => {
    element.classList.add('autogrow');
    autosize(element); // Начальная подгонка

    const handler = handleInput.bind(null);
    element.addEventListener('input', handler);
    handlers.set(element, handler);
  });

  // Подгонка при изменении размера окна
  let resizeFrame;
  const debouncedResize = () => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(handleResize);
  };
  
  window.addEventListener('resize', debouncedResize);

  /**
   * Функция для удаления всех обработчиков.
   */
  function destroy() {
    textareas.forEach(element => {
      const handler = handlers.get(element);
      if (handler) {
        element.removeEventListener('input', handler);
        handlers.delete(element);
      }
      element.classList.remove('autogrow', 'is-max');
      element.style.height = '';
    });

    window.removeEventListener('resize', debouncedResize);
    cancelAnimationFrame(resizeFrame);
  }

  return { destroy };
}

/**
 * Применяет автоматическое изменение размера к конкретному элементу.
 * @param {HTMLTextAreaElement} element - Элемент textarea
 * @returns {Function} Функция для удаления обработчика
 */
export function applyAutogrow(element) {
  if (!(element instanceof HTMLTextAreaElement)) {
    console.warn('applyAutogrow: элемент должен быть textarea');
    return () => {};
  }

  element.classList.add('autogrow');
  autosize(element);

  function handler() {
    autosize(element);
  }

  element.addEventListener('input', handler);

  return function cleanup() {
    element.removeEventListener('input', handler);
    element.classList.remove('autogrow', 'is-max');
    element.style.height = '';
  };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initTextareaAutogrow = initTextareaAutogrow;
  window.applyAutogrow = applyAutogrow;
}

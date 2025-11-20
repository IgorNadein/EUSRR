/**
 * textareaAutogrow.js
 * Автоматическое изменение высоты textarea при вводе текста
 * 
 * @module textareaAutogrow
 * @version 1.0.0
 */

/**
 * Инициализация автоматического роста для textarea элементов
 * Работает с атрибутом data-autogrow и опциональным data-max-height
 * 
 * @param {Object} options - Опции конфигурации
 * @param {string} options.selector - CSS селектор для textarea (по умолчанию 'textarea[data-autogrow]')
 * @param {number} options.defaultMaxHeight - Максимальная высота по умолчанию (по умолчанию 240px)
 * @returns {Object} Публичный API
 * 
 * @example
 * // HTML:
 * <textarea data-autogrow data-max-height="300"></textarea>
 * 
 * // JavaScript:
 * initTextareaAutogrow();
 */
export function initTextareaAutogrow(options = {}) {
  // Защита от повторной инициализации
  if (window.__textareaAutogrowBound) {
    console.log('textareaAutogrow: already initialized');
    return window.__textareaAutogrowBound;
  }

  const config = {
    selector: options.selector || 'textarea[data-autogrow]',
    defaultMaxHeight: options.defaultMaxHeight || 240
  };

  /**
   * Применить автоматический рост к textarea
   * @param {HTMLTextAreaElement} el - Textarea элемент
   */
  function autoGrow(el) {
    const maxHeight = parseInt(el.dataset.maxHeight || String(config.defaultMaxHeight), 10);
    
    // Сбросить высоту для пересчета scrollHeight
    el.style.height = 'auto';
    
    // Установить новую высоту (но не больше maxHeight)
    const newHeight = Math.min(el.scrollHeight, maxHeight);
    el.style.height = newHeight + 'px';
    
    // Показать scrollbar если контент больше maxHeight
    el.style.overflowY = (el.scrollHeight > maxHeight) ? 'auto' : 'hidden';
  }

  /**
   * Привязать обработчики к textarea
   * @param {HTMLTextAreaElement} el - Textarea элемент
   */
  function bind(el) {
    // Защита от повторной привязки
    if (el.dataset.autogrowBound === '1') {
      return;
    }
    
    el.dataset.autogrowBound = '1';
    el.addEventListener('input', () => autoGrow(el));
    
    // Применить сразу при инициализации
    autoGrow(el);
  }

  /**
   * Инициализировать все textarea на странице
   */
  function initAll() {
    document.querySelectorAll(config.selector).forEach(bind);
  }

  /**
   * Наблюдать за добавлением новых textarea через MutationObserver
   */
  function observeDOM() {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) { // Element node
            // Проверяем сам элемент
            if (node.matches && node.matches(config.selector)) {
              bind(node);
            }
            // Проверяем дочерние элементы
            if (node.querySelectorAll) {
              node.querySelectorAll(config.selector).forEach(bind);
            }
          }
        });
      });
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    return observer;
  }

  // Инициализация
  initAll();
  const observer = observeDOM();

  const api = {
    autoGrow,
    bind,
    initAll,
    observer,
    unbind: (el) => {
      el.dataset.autogrowBound = '0';
      el.removeEventListener('input', () => autoGrow(el));
    },
    destroy: () => {
      observer.disconnect();
      document.querySelectorAll(config.selector).forEach(el => {
        el.dataset.autogrowBound = '0';
      });
      window.__textareaAutogrowBound = null;
    }
  };

  // Сохраняем в window для защиты от повторной инициализации
  window.__textareaAutogrowBound = api;

  console.log('textareaAutogrow: initialized');

  return api;
}

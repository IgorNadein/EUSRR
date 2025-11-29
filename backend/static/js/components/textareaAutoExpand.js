/**
 * textareaAutoExpand.js
 * Универсальный модуль для автоматического расширения textarea
 * Используется во всех формах комментариев и сообщений
 */

(function() {
  'use strict';

  // Максимальная высота textarea (6 строк по 24px)
  const MAX_HEIGHT = 6 * 24; // 144px

  /**
   * Автоматически изменяет высоту textarea
   */
  function autoExpand(textarea) {
    if (!textarea) return;
    
    // Сбрасываем высоту для корректного вычисления scrollHeight
    textarea.style.height = 'auto';
    
    // Устанавливаем новую высоту, но не больше максимальной
    const newHeight = Math.min(textarea.scrollHeight, MAX_HEIGHT);
    textarea.style.height = newHeight + 'px';
  }

  /**
   * Инициализация автоматического расширения для textarea
   */
  function initAutoExpand(textarea) {
    if (!textarea || textarea.dataset.autoExpandInit) return;
    
    // Помечаем, что уже инициализировано
    textarea.dataset.autoExpandInit = 'true';
    
    // Обработчик ввода
    const handleInput = () => autoExpand(textarea);
    textarea.addEventListener('input', handleInput);
    
    // Начальная подгонка
    autoExpand(textarea);
    
    // Возвращаем функцию для отписки
    return () => {
      textarea.removeEventListener('input', handleInput);
      delete textarea.dataset.autoExpandInit;
    };
  }

  /**
   * Инициализация для всех textarea в формах комментариев и сообщений
   */
  function initAllTextareas() {
    // Селекторы для всех форм комментариев и сообщений
    const selectors = [
      '.comment-form-quick textarea',
      '.comment-form-modal textarea',
      '.request-comment-form textarea',
      '.comment-new textarea',
      '.composer-textarea', // Для чата
      '.message-input' // Общий класс для всех message-input
    ];

    const textareas = document.querySelectorAll(selectors.join(', '));
    textareas.forEach(textarea => {
      // Инициализируем только те, у которых rows="1"
      if (textarea.getAttribute('rows') === '1' || textarea.classList.contains('composer-textarea')) {
        initAutoExpand(textarea);
      }
    });
  }

  /**
   * Наблюдатель за добавлением новых textarea
   */
  function setupMutationObserver() {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) { // Element node
            // Проверяем, является ли добавленный узел textarea
            if (node.tagName === 'TEXTAREA' && (node.getAttribute('rows') === '1' || node.classList.contains('composer-textarea'))) {
              initAutoExpand(node);
            }
            // Или ищем textarea внутри добавленного узла
            if (node.querySelectorAll) {
              const textareas = node.querySelectorAll('textarea[rows="1"], textarea.composer-textarea');
              textareas.forEach(textarea => initAutoExpand(textarea));
            }
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  /**
   * Инициализация модуля
   */
  function init() {
    // Инициализируем существующие textarea
    initAllTextareas();
    
    // Настраиваем наблюдатель для динамически добавляемых textarea
    setupMutationObserver();
  }

  // Автоматическая инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Экспорт для использования извне
  window.textareaAutoExpand = {
    init: initAllTextareas,
    initTextarea: initAutoExpand,
    autoExpand: autoExpand
  };

})();

/**
 * requestComments.js
 * Обработка форм комментариев в модуле заявлений
 */

(function() {
  'use strict';

  /**
   * Обработка нажатия Enter в textarea
   */
  function handleTextareaKeydown(e) {
    // Enter без Shift - отправка формы
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const form = e.target.closest('form');
      if (form) {
        form.submit();
      }
    }
    // Shift+Enter - новая строка (поведение по умолчанию)
  }

  /**
   * Вставка emoji в textarea
   */
  function insertEmoji(textarea, emoji) {
    if (!textarea) return;
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;
    const value = textarea.value || '';
    const emojiText = typeof emoji === 'string' ? emoji : emoji.emoji || emoji.unicode || emoji;
    textarea.value = `${value.slice(0, start)}${emojiText}${value.slice(end)}`;
    const caret = start + emojiText.length;
    textarea.focus();
    textarea.setSelectionRange?.(caret, caret);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  }

  /**
   * Инициализация emoji picker для формы
   */
  function initEmojiPicker(form) {
    const picker = form.querySelector('[data-emoji-picker]');
    if (!picker) return;

    // Ищем textarea по name="text" или data-role="text"
    const textarea = form.querySelector('textarea[name="text"], textarea[data-role="text"]');
    if (!textarea) return;

    // Обработчик выбора emoji
    picker.addEventListener('emoji-click', (event) => {
      event.preventDefault();
      const emoji = event.detail?.unicode;
      if (emoji) {
        insertEmoji(textarea, emoji);
      }
    });

    // Предотвращаем закрытие dropdown при клике внутри emoji-picker
    const emojiDropdown = picker.closest('.dropdown-menu');
    if (emojiDropdown) {
      emojiDropdown.addEventListener('click', (event) => {
        event.stopPropagation();
      });
    }
  }

  /**
   * Инициализация обработчиков форм комментариев заявлений
   */
  function initRequestComments() {
    // Обработка нажатия Enter в textarea
    document.addEventListener('keydown', function(e) {
      const commentTextarea = e.target.closest('textarea[name="text"], textarea[data-role="text"]');
      if (commentTextarea && (commentTextarea.closest('.request-comment-form') || commentTextarea.closest('.comment-new'))) {
        handleTextareaKeydown(e);
      }
    });

    // Инициализация emoji picker для существующих форм
    document.querySelectorAll('.request-comment-form, .comment-new').forEach(form => {
      initEmojiPicker(form);
    });

    // Наблюдатель за добавлением новых форм (для динамически загружаемого контента)
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) { // Element node
            // Проверяем, является ли добавленный узел формой комментария
            if (node.classList && (node.classList.contains('request-comment-form') || node.classList.contains('comment-new'))) {
              initEmojiPicker(node);
            }
            // Или ищем формы внутри добавленного узла
            const forms = node.querySelectorAll ? node.querySelectorAll('.request-comment-form, .comment-new') : [];
            forms.forEach(form => initEmojiPicker(form));
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRequestComments);
  } else {
    initRequestComments();
  }

})();

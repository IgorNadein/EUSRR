/**
 * feedComments.js
 * Обработка быстрого добавления комментариев в карточках постов
 */

(function() {
  'use strict';

  /**
   * Получение CSRF токена из cookie
   */
  function getCookie(name) {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [cookieName, value] = cookie.trim().split('=');
      if (cookieName === name) {
        return decodeURIComponent(value);
      }
    }
    return null;
  }

  /**
   * Форматирование даты в формат "ДД.ММ.ГГГГ ЧЧ:ММ"
   */
  function formatDate(dateString) {
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${day}.${month}.${year} ${hours}:${minutes}`;
  }

  /**
   * Обработка нажатия Enter в textarea
   */
  function handleTextareaKeydown(e) {
    // Enter без Shift - отправка формы
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const form = e.target.closest('form');
      if (form) {
        form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
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

    const textarea = form.querySelector('textarea[name="text"]');
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
   * Добавление комментария в DOM
   */
  function appendCommentToDOM(postId, commentData) {
    // Находим контейнер с комментариями для этого поста
    const collapsibleBlock = document.querySelector(`#ccoll-${postId}`);
    if (!collapsibleBlock) return;

    // Ищем существующий контейнер комментариев или создаём новый
    let commentsContainer = collapsibleBlock.querySelector('.px-3.pt-2');
    
    if (!commentsContainer) {
      // Создаём контейнер если его нет
      commentsContainer = document.createElement('div');
      commentsContainer.className = 'px-3 pt-2';
      
      // Вставляем перед формой
      const form = collapsibleBlock.querySelector('.comment-form-quick');
      if (form) {
        collapsibleBlock.insertBefore(commentsContainer, form.parentElement);
      } else {
        collapsibleBlock.appendChild(commentsContainer);
      }
    }

    // Создаём HTML нового комментария с использованием SCSS классов
    const commentHTML = createCommentHTML(commentData);

    // Добавляем новый комментарий
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = commentHTML;
    commentsContainer.appendChild(tempDiv.firstElementChild);

    // Обновляем счётчик комментариев
    updateCommentCount(postId);
  }

  /**
   * Экранирование HTML для безопасного вывода
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Обновление счётчика комментариев
   */
  function updateCommentCount(postId) {
    // Находим кнопку с комментариями
    const commentBtn = document.querySelector(`[data-bs-target="#ccoll-${postId}"]`);
    if (!commentBtn) return;

    const countSpan = commentBtn.querySelector('span');
    if (countSpan) {
      const currentCount = parseInt(countSpan.textContent) || 0;
      countSpan.textContent = currentCount + 1;
    }

    // Также обновляем ссылку "Показать все комментарии"
    const collapsibleBlock = document.querySelector(`#ccoll-${postId}`);
    if (collapsibleBlock) {
      const showAllLink = collapsibleBlock.querySelector('.text-primary');
      if (showAllLink) {
        const linkText = showAllLink.textContent;
        const match = linkText.match(/\((\d+)\)/);
        if (match) {
          const newCount = parseInt(match[1]) + 1;
          showAllLink.textContent = linkText.replace(/\(\d+\)/, `(${newCount})`);
        }
      }
    }
  }

  /**
   * Добавление комментария
   */
  async function addComment(form, postId) {
    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
      alert('Необходимо авторизоваться');
      return;
    }

    const textarea = form.querySelector('textarea[name="text"]');
    const text = textarea.value.trim();
    
    if (!text) {
      alert('Введите текст комментария');
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    const formData = new FormData();
    formData.append('text', text);

    try {
      const response = await fetch(`/api/v1/posts/${postId}/comments/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
      });

      if (response.ok) {
        const commentData = await response.json();
        
        // Очищаем форму
        textarea.value = '';
        
        // Добавляем комментарий в DOM
        appendCommentToDOM(postId, commentData);
        
        // Показываем сообщение об успехе (опционально)
        console.log('Комментарий добавлен успешно');
      } else {
        const error = await response.json();
        let errorMsg = 'Ошибка добавления комментария:\n';
        for (const [field, errors] of Object.entries(error)) {
          errorMsg += `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}\n`;
        }
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка сети при добавлении комментария');
    } finally {
      submitBtn.disabled = false;
    }
  }

  /**
   * Инициализация обработчиков форм комментариев
   */
  function initFeedComments() {
    // Обработка нажатия Enter в textarea
    document.addEventListener('keydown', function(e) {
      const commentTextarea = e.target.closest('textarea[name="text"]');
      if (commentTextarea && (commentTextarea.closest('.comment-form-quick') || commentTextarea.closest('.comment-form-modal'))) {
        handleTextareaKeydown(e);
      }
    });

    // Используем делегирование событий для обеих форм
    document.addEventListener('submit', function(e) {
      // Быстрая форма в карточках
      const quickForm = e.target.closest('.comment-form-quick');
      if (quickForm) {
        e.preventDefault();
        const postId = quickForm.dataset.postId;
        if (postId) {
          addComment(quickForm, postId);
        }
        return;
      }
      
      // Форма в модальном окне
      const modalForm = e.target.closest('.comment-form-modal');
      if (modalForm) {
        e.preventDefault();
        const postId = modalForm.dataset.postId;
        if (postId) {
          addCommentToModal(modalForm, postId);
        }
        return;
      }
    });

    // Инициализация emoji picker для уже существующих форм
    document.querySelectorAll('.comment-form-quick, .comment-form-modal').forEach(form => {
      initEmojiPicker(form);
    });

    // Наблюдатель за добавлением новых форм (для динамически загружаемых постов)
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) { // Element node
            // Проверяем, является ли добавленный узел формой комментария
            if (node.classList && (node.classList.contains('comment-form-quick') || node.classList.contains('comment-form-modal'))) {
              initEmojiPicker(node);
            }
            // Или ищем формы внутри добавленного узла
            const forms = node.querySelectorAll ? node.querySelectorAll('.comment-form-quick, .comment-form-modal') : [];
            forms.forEach(form => initEmojiPicker(form));
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  /**
   * Добавление комментария в модальном окне
   */
  async function addCommentToModal(form, postId) {
    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
      alert('Необходимо авторизоваться');
      return;
    }

    const textarea = form.querySelector('textarea[name="text"]');
    const text = textarea.value.trim();
    
    if (!text) {
      alert('Введите текст комментария');
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    const formData = new FormData();
    formData.append('text', text);

    try {
      const response = await fetch(`/api/v1/posts/${postId}/comments/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
      });

      if (response.ok) {
        const commentData = await response.json();
        
        // Очищаем форму
        textarea.value = '';
        
        // Добавляем комментарий в список модального окна
        const commentsList = document.querySelector('.comments-scrollable');
        if (commentsList) {
          const commentHTML = createCommentHTML(commentData);
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = commentHTML;
          commentsList.appendChild(tempDiv.firstElementChild);
          
          // Прокручиваем к новому комментарию
          commentsList.scrollTop = commentsList.scrollHeight;
        }
        
        // Обновляем счётчик
        const countSpan = document.querySelector('.comments-count');
        if (countSpan) {
          const currentCount = parseInt(countSpan.textContent.replace(/[()]/g, '')) || 0;
          countSpan.textContent = `(${currentCount + 1})`;
        }
        
        console.log('Комментарий добавлен в модальное окно');
      } else {
        const error = await response.json();
        let errorMsg = 'Ошибка добавления комментария:\n';
        for (const [field, errors] of Object.entries(error)) {
          errorMsg += `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}\n`;
        }
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка сети при добавлении комментария');
    } finally {
      submitBtn.disabled = false;
    }
  }

  /**
   * Создание HTML комментария (вспомогательная функция)
   */
  function createCommentHTML(commentData) {
    const authorName = commentData.author?.full_name || 'Сотрудник';
    const authorId = commentData.author?.id;
    const authorLink = authorId 
      ? `/employees/${authorId}/`
      : '#';
    const commentDate = formatDate(commentData.created_at);
    
    return `
      <div class="comment-item">
        <div class="comment-header">
          ${authorId 
            ? `<a href="${authorLink}" class="comment-author">${authorName}</a>`
            : `<span class="comment-author">${authorName}</span>`
          }
          <span class="comment-separator">·</span>
          <time class="comment-date">${commentDate}</time>
        </div>
        <div class="comment-body">${escapeHtml(commentData.text)}</div>
      </div>
    `;
  }

  // Инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFeedComments);
  } else {
    initFeedComments();
  }

})();

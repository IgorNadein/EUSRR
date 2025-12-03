/**
 * postDetailModal.js
 * Модуль для открытия деталей поста в модальном окне
 * Полностью переработанная версия с правильной логикой определения автора
 */

(function() {
  'use strict';

  // Константы
  const INITIAL_COMMENTS_COUNT = 10;
  const DEBUG = true; // Включаем отладку для диагностики

  // Состояние модуля
  let modal = null;
  let modalElement = null;
  let currentPost = null; // Сохраняем текущий пост

  /**
   * Инициализация модального окна
   */
  function initPostDetailModal() {
    modalElement = document.getElementById('postDetailModal');
    if (!modalElement) {
      console.warn('postDetailModal: элемент #postDetailModal не найден');
      return;
    }

    modal = new bootstrap.Modal(modalElement);

    // Очистка при закрытии
    modalElement.addEventListener('hidden.bs.modal', function() {
      const contentDiv = document.getElementById('postDetailContent');
      if (contentDiv) {
        contentDiv.innerHTML = `
          <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Загрузка...</span>
            </div>
          </div>
        `;
      }
      currentPost = null;
    });

    // Добавляем обработчики на ссылки постов
    attachPostLinkHandlers();
  }

  /**
   * Получение CSRF токена из cookie
   */
  function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'csrftoken') {
        return decodeURIComponent(value);
      }
    }
    return null;
  }

  /**
   * Получение JWT токена из cookie (для загрузки данных)
   */
  function getAccessToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'access_token') {
        return decodeURIComponent(value);
      }
    }
    return null;
  }

  /**
   * Загрузка деталей поста через API
   */
  async function loadPostDetail(postId) {
    const accessToken = getAccessToken();
    const headers = {
      'Accept': 'application/json'
    };

    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    try {
      const response = await fetch(`/api/v1/posts/${postId}/`, {
        method: 'GET',
        headers: headers
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const post = await response.json();
      
      // Отладочная информация
      if (DEBUG) {
        console.log('=== POST DETAIL DEBUG ===');
        console.log('Post author:', post.author);
        console.log('Post author.id:', post.author?.id, 'type:', typeof post.author?.id);
        console.log('Post author_id:', post.author_id, 'type:', typeof post.author_id);
        if (post.comments && post.comments.length > 0) {
          console.log('First comment:', post.comments[0]);
          console.log('First comment author:', post.comments[0].author);
          console.log('First comment author.id:', post.comments[0].author?.id, 'type:', typeof post.comments[0].author?.id);
          console.log('First comment author_id:', post.comments[0].author_id, 'type:', typeof post.comments[0].author_id);
        }
        console.log('========================');
      }
      
      currentPost = post;
      renderPostDetail(post);
    } catch (error) {
      console.error('Ошибка загрузки поста:', error);
      showError('Не удалось загрузить пост');
    }
  }

  /**
   * Отображение деталей поста в модальном окне
   */
  function renderPostDetail(post) {
    const contentDiv = document.getElementById('postDetailContent');
    
    // Определяем ID автора поста (пробуем разные поля)
    const postAuthorId = getAuthorId(post.author) || post.author_id;
    
    if (DEBUG) {
      console.log('Rendering post with author ID:', postAuthorId);
    }
    
    // Формируем HTML с кнопкой закрытия
    let html = '<button type="button" class="btn-close position-absolute top-0 end-0 m-3" data-bs-dismiss="modal" aria-label="Закрыть" style="z-index: 1050;"></button>';
    html += '<article class="card">';

    // Заголовок с автором
    html += renderPostHeader(post);
    
    // Изображение
    if (post.image) {
      html += `<div class="feed-img"><img src="${post.image}" alt="${escapeHtml(post.title || 'Публикация')}"></div>`;
    }

    // Тело
    html += '<div class="card-body">';
    html += `<h3 class="feed-title mb-3">${escapeHtml(post.title || 'Без названия')}</h3>`;
    if (post.body) {
      html += `<div class="feed-text mb-3">${formatBody(post.body)}</div>`;
    }
    html += '</div>';

    // Футер с лайками
    html += renderPostFooter(post);

    // Секция комментариев
    html += renderCommentsSection(post, postAuthorId);

    html += '</article>';

    contentDiv.innerHTML = html;

    // Сохраняем данные для динамической подгрузки
    if (post.comments && post.comments.length > 0) {
      contentDiv.dataset.allComments = JSON.stringify(post.comments);
      contentDiv.dataset.postAuthorId = postAuthorId;
    }

    // Прокручиваем к последнему комментарию
    scrollToBottom();

    // Добавляем обработчики
    attachLikeHandlers();
    attachLoadMoreCommentsHandler();
    attachCommentFormHandler();
  }

  /**
   * Отображение комментария
   * @param {Object} comment - Объект комментария
   * @param {number} postAuthorId - ID автора поста
   */
  function renderComment(comment, postAuthorId) {
    // Приводим оба ID к числам для корректного сравнения
    const commentAuthorId = comment.author?.id ? parseInt(comment.author.id) : null;
    const postAuthorIdNum = postAuthorId ? parseInt(postAuthorId) : null;
    const isAuthor = commentAuthorId !== null && postAuthorIdNum !== null && commentAuthorId === postAuthorIdNum;
    
    const commentClass = isAuthor ? 'comment-item comment-item--author' : 'comment-item';
    
    let html = `<div class="${commentClass}">`;
    html += '<div class="comment-header">';
    
    // Автор и дата
    const authorName = comment.author?.full_name || 'Аноним';
    const authorId = comment.author?.id;
    
    if (authorId) {
      html += `<a href="/employees/${authorId}/" class="comment-author">${authorName}</a>`;
    } else {
      html += `<span class="comment-author">${authorName}</span>`;
    }
    
    html += '<span class="comment-separator">·</span>';
    html += `<time class="comment-date">${formatDate(comment.created_at)}</time>`;
    html += '</div>';
    
    // Текст комментария
    html += `<div class="comment-body">${formatBody(comment.text)}</div>`;
    html += '</div>';
    
    return html;
  }

  /**
   * Форматирование даты
   */
  function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return 'Сегодня, ' + date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return 'Вчера, ' + date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } else if (days < 7) {
      return days + ' дн. назад';
    } else {
      return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    }
  }

  /**
   * Форматирование текста (простая обработка переносов строк)
   */
  function formatBody(text) {
    return text.replace(/\n/g, '<br>');
  }

  /**
   * Показать ошибку
   */
  function showError(message) {
    const contentDiv = document.getElementById('postDetailContent');
    contentDiv.innerHTML = `
      <div class="alert alert-danger" role="alert">
        <i class="bi-exclamation-triangle"></i> ${message}
      </div>
    `;
  }

  /**
   * Открыть модальное окно с постом
   */
  function openPostModal(postId) {
    if (!modal) {
      console.error('Modal не инициализирован');
      return;
    }

    modal.show();
    loadPostDetail(postId);
  }

  /**
   * Добавление обработчиков на ссылки постов
   */
  function attachPostLinkHandlers() {
    // Обработка кликов по ссылкам на посты
    document.addEventListener('click', function(e) {
      const link = e.target.closest('a[data-post-link]');
      if (link) {
        e.preventDefault();
        const postId = link.dataset.postId;
        if (postId) {
          openPostModal(postId);
        }
      }
    });
  }

  /**
   * Обработчик для кнопки "Показать ещё комментарии"
   */
  function attachLoadMoreCommentsHandler() {
    const loadMoreBtn = document.querySelector('.load-more-comments');
    if (!loadMoreBtn) return;

    loadMoreBtn.addEventListener('click', function() {
      const contentDiv = document.getElementById('postDetailContent');
      const allComments = JSON.parse(contentDiv.dataset.allComments || '[]');
      const postAuthorId = parseInt(contentDiv.dataset.postAuthorId);
      const commentsContainer = document.getElementById('commentsListContainer');
      
      if (!commentsContainer || allComments.length === 0) return;

      // Сохраняем текущую позицию скролла и высоту
      const scrollHeight = commentsContainer.scrollHeight;
      const scrollTop = commentsContainer.scrollTop;
      
      // Показываем все комментарии
      let html = '';
      allComments.forEach(comment => {
        html += renderComment(comment, postAuthorId);
      });
      
      commentsContainer.innerHTML = html;
      
      // Восстанавливаем позицию скролла (с учётом добавленного контента)
      const newScrollHeight = commentsContainer.scrollHeight;
      const heightDiff = newScrollHeight - scrollHeight;
      commentsContainer.scrollTop = scrollTop + heightDiff;
      
      // Удаляем кнопку после загрузки
      this.remove();
    });
  }

  /**
   * Обработчики лайков в модальном окне
   */
  function attachLikeHandlers() {
    const likeButtons = document.querySelectorAll('#postDetailContent .like-btn');
    likeButtons.forEach(btn => {
      btn.addEventListener('click', async function(e) {
        e.preventDefault();
        const postId = this.dataset.postId;
        await toggleLike(postId, this);
      });
    });
  }

  /**
   * Переключение лайка
   */
  async function toggleLike(postId, button) {
    const csrfToken = getCsrfToken();
    if (!csrfToken) {
      alert('Необходимо авторизоваться');
      return;
    }

    const icon = button.querySelector('i');
    const isLiked = icon.classList.contains('bi-heart-fill');
    const endpoint = isLiked ? 'unlike' : 'like';

    try {
      const response = await fetch(`/api/v1/posts/${postId}/${endpoint}/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        }
      });

      if (response.ok) {
        const data = await response.json();
        
        // Обновляем иконку и счетчик
        if (isLiked) {
          icon.classList.remove('bi-heart-fill', 'text-danger');
          icon.classList.add('bi-heart');
        } else {
          icon.classList.remove('bi-heart');
          icon.classList.add('bi-heart-fill', 'text-danger');
        }

        // Обновляем счетчик
        const countText = button.childNodes[1];
        if (countText) {
          countText.textContent = ' ' + (data.likes_count || 0);
        }
      } else {
        alert('Ошибка при обработке лайка');
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка сети');
    }
  }

  // Инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPostDetailModal);
  } else {
    initPostDetailModal();
  }

  // Экспорт для использования извне
  window.openPostModal = openPostModal;

})();

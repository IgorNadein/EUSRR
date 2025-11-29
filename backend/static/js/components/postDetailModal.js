/**
 * postDetailModal.js
 * Модуль для открытия деталей поста в модальном окне
 */

(function() {
  'use strict';

  let modal = null;
  let modalElement = null;

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
    
    // Формируем HTML с кнопкой закрытия
    let html = '<button type="button" class="btn-close position-absolute top-0 end-0 m-3" data-bs-dismiss="modal" aria-label="Закрыть" style="z-index: 1050;"></button>';
    html += '<article class="card">';

    // Заголовок с автором
    html += '<header class="card-header">';
    html += '<div class="card-icon">';
    if (post.author && post.author.avatar) {
      html += `<img src="${post.author.avatar}" alt="">`;
    } else {
      html += '<i class="bi-person"></i>';
    }
    html += '</div>';
    html += '<div class="feed-info">';
    html += `<div class="card-title">${post.author?.full_name || 'Аноним'}</div>`;
    html += `<time class="feed-date">${formatDate(post.created_at)}</time>`;
    html += '</div>';
    
    // Закрепленный пост
    if (post.pinned) {
      html += '<span class="feed-pin"><i class="bi-pin-angle"></i></span>';
    }
    html += '</header>';

    // Изображение
    if (post.image) {
      html += `<div class="feed-img"><img src="${post.image}" alt="${post.title || 'Публикация'}"></div>`;
    }

    // Тело
    html += '<div class="card-body">';
    html += `<h3 class="feed-title mb-3">${post.title || 'Без названия'}</h3>`;
    if (post.body) {
      html += `<div class="feed-text mb-3">${formatBody(post.body)}</div>`;
    }
    html += '</div>';

    // Футер с лайками и комментариями
    html += '<footer class="feed-ft">';
    html += '<div class="feed-stats">';
    
    // Лайки
    const likeIcon = post.user_has_liked ? 'bi-heart-fill text-danger' : 'bi-heart';
    html += `<button class="btn btn-ghost btn-sm like-btn" data-post-id="${post.id}">`;
    html += `<i class="${likeIcon}"></i> ${post.likes_count || 0}`;
    html += '</button>';

    // Комментарии
    // html += `<span class="text-muted ms-3"><i class="bi-chat"></i> ${post.comments_count || 0}</span>`;
    
    html += '</div>';
    html += '</footer>';

    // Секция комментариев внутри карточки
    html += '<div class="comments-section-wrapper">';
    
    if (post.comments && post.comments.length > 0) {
      html += '<div class="px-3 pt-3">';
      html += '<hr class="my-3">';
      html += '<div class="comments-section-header">';
      html += '<i class="bi-chat-dots comments-icon"></i>';
      html += '<h5 class="comments-title">Комментарии</h5>';
      html += `<span class="comments-count">(${post.comments.length})</span>`;
      html += '</div>';
      html += '<div class="comments-list comments-scrollable">';
      post.comments.forEach(comment => {
        html += renderComment(comment);
      });
      html += '</div>';
      html += '</div>';
    }
    
    // Форма добавления комментария (sticky)
    html += '<div class="comment-form-sticky">';
    html += '<div class="px-3 py-2 border-top">';
    html += '<form class="comment-form-modal" data-post-id="' + post.id + '">';
    html += '<div class="message-field message-field--compact">';
    
    // Кнопка выбора эмодзи
    html += '<div class="dropdown message-emoji">';
    html += '<button type="button" class="btn btn-ghost btn-emoji message-icon-btn" ';
    html += 'data-bs-toggle="dropdown" aria-expanded="false" title="Вставить смайлик">';
    html += '<i class="bi-emoji-smile"></i>';
    html += '</button>';
    html += '<div class="dropdown-menu dropdown-menu-start message-emoji-menu">';
    html += '<emoji-picker data-emoji-picker class="chat-emoji-picker"></emoji-picker>';
    html += '</div>';
    html += '</div>';
    
    html += '<textarea name="text" class="form-control message-input" rows="1" placeholder="Оставить комментарий…" required></textarea>';
    html += '<button class="btn btn-primary message-send" type="submit" title="Отправить"><i class="bi-send"></i></button>';
    html += '</div>';
    html += '</form>';
    html += '</div>';
    html += '</div>';
    
    html += '</div>'; // comments-section-wrapper

    html += '</article>';

    contentDiv.innerHTML = html;

    // Добавляем обработчики
    attachLikeHandlers();
  }

  /**
   * Отображение комментария
   */
  function renderComment(comment) {
    let html = '<div class="comment-item">';
    html += '<div class="comment-header">';
    
    // Автор и дата
    const authorName = comment.author?.full_name || 'Аноним';
    const authorId = comment.author?.id;
    
    if (authorId) {
      html += `<a href="/employees/employee/${authorId}/" class="comment-author">${authorName}</a>`;
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

/**
 * postDetailModal.js
 * Модуль для открытия деталей поста в модальном окне
 * Полностью переработанная версия
 */

(function() {
  'use strict';

  // Константы
  const INITIAL_COMMENTS_COUNT = 10;
  const DEBUG = true;

  // Состояние
  let modal = null;
  let modalElement = null;
  let currentPost = null;

  /**
   * Инициализация
   */
  function initPostDetailModal() {
    modalElement = document.getElementById('postDetailModal');
    if (!modalElement) {
      console.warn('postDetailModal: элемент #postDetailModal не найден');
      return;
    }

    modal = new bootstrap.Modal(modalElement);

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

    attachPostLinkHandlers();
  }

  /**
   * Утилиты для работы с cookies
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
   * Утилиты
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function getAuthorId(authorObj) {
    if (!authorObj) return null;
    // API возвращает author.id
    return authorObj.id || null;
  }

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

  function formatBody(text) {
    return text.replace(/\n/g, '<br>');
  }

  function pluralizeComments(count) {
    const cases = [2, 0, 1, 1, 1, 2];
    const titles = ['комментарий', 'комментария', 'комментариев'];
    return titles[(count % 100 > 4 && count % 100 < 20) ? 2 : cases[(count % 10 < 5) ? count % 10 : 5]];
  }

  /**
   * Загрузка поста
   */
  async function loadPostDetail(postId) {
    const accessToken = getAccessToken();
    const headers = { 'Accept': 'application/json' };

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
      
      if (DEBUG) {
        console.log('=== POST DEBUG ===');
        console.log('Post:', post);
        console.log('Post author:', post.author);
        console.log('Post author ID:', getAuthorId(post.author), typeof getAuthorId(post.author));
        if (post.comments && post.comments.length > 0) {
          const firstComment = post.comments[0];
          console.log('First comment:', firstComment);
          console.log('Comment author:', firstComment.author);
          console.log('Comment author ID:', getAuthorId(firstComment.author), typeof getAuthorId(firstComment.author));
        }
        console.log('==================');
      }
      
      currentPost = post;
      renderPostDetail(post);
    } catch (error) {
      console.error('Ошибка загрузки поста:', error);
      showError('Не удалось загрузить пост');
    }
  }

  /**
   * Рендеринг
   */
  function renderPostDetail(post) {
    const contentDiv = document.getElementById('postDetailContent');
    const postAuthorId = getAuthorId(post.author);
    
    if (DEBUG) {
      console.log('Rendering with postAuthorId:', postAuthorId);
    }
    
    let html = '<button type="button" class="btn-close position-absolute top-0 end-0 m-3" data-bs-dismiss="modal" aria-label="Закрыть" style="z-index: 1050;"></button>';
    html += '<article class="card">';
    html += renderPostHeader(post);
    
    if (post.image) {
      html += `<div class="feed-img"><img src="${post.image}" alt="${escapeHtml(post.title || 'Публикация')}"></div>`;
    }

    html += '<div class="card-body">';
    html += `<h3 class="feed-title mb-3">${escapeHtml(post.title || 'Без названия')}</h3>`;
    if (post.body) {
      html += `<div class="feed-text mb-3">${formatBody(post.body)}</div>`;
    }
    html += '</div>';

    html += renderPostFooter(post);
    html += renderCommentsSection(post, postAuthorId);
    html += '</article>';

    contentDiv.innerHTML = html;

    if (post.comments && post.comments.length > 0) {
      contentDiv.dataset.allComments = JSON.stringify(post.comments);
      contentDiv.dataset.postAuthorId = postAuthorId || '';
    }

    scrollToBottom();
    attachLikeHandlers();
    attachLoadMoreCommentsHandler();
    attachCommentFormHandler();
  }

  function renderPostHeader(post) {
    let html = '<header class="card-header">';
    html += '<div class="card-icon">';
    if (post.author && post.author.avatar) {
      html += `<img src="${post.author.avatar}" alt="">`;
    } else {
      html += '<i class="bi-person"></i>';
    }
    html += '</div>';
    html += '<div class="feed-info">';
    html += `<div class="card-title">${escapeHtml(post.author?.full_name || 'Аноним')}</div>`;
    html += `<time class="feed-date">${formatDate(post.created_at)}</time>`;
    html += '</div>';
    
    if (post.pinned) {
      html += '<span class="feed-pin"><i class="bi-pin-angle"></i></span>';
    }
    html += '</header>';
    return html;
  }

  function renderPostFooter(post) {
    let html = '<footer class="feed-ft">';
    html += '<div class="feed-stats">';
    
    const likeIcon = post.user_has_liked ? 'bi-heart-fill text-danger' : 'bi-heart';
    html += `<button class="btn btn-ghost btn-sm like-btn" data-post-id="${post.id}">`;
    html += `<i class="${likeIcon}"></i> ${post.likes_count || 0}`;
    html += '</button>';
    
    html += '</div>';
    html += '</footer>';
    return html;
  }

  function renderCommentsSection(post, postAuthorId) {
    let html = '<div class="comments-section-wrapper">';
    
    if (post.comments && post.comments.length > 0) {
      html += '<div class="px-3 pt-3">';
      html += '<hr class="my-3">';
      html += '<div class="comments-section-header">';
      html += '<i class="bi-chat-dots comments-icon"></i>';
      html += '<h5 class="comments-title">Комментарии</h5>';
      html += `<span class="comments-count">(${post.comments.length})</span>`;
      html += '</div>';
      
      if (post.comments.length > INITIAL_COMMENTS_COUNT) {
        const remainingCount = post.comments.length - INITIAL_COMMENTS_COUNT;
        html += `<button class="btn btn-link btn-sm mb-2 load-more-comments">`;
        html += `<i class="bi-chevron-up"></i> Показать ещё ${remainingCount} ${pluralizeComments(remainingCount)}`;
        html += '</button>';
      }
      
      html += '<div class="comments-list comments-scrollable" id="commentsListContainer">';
      
      const visibleComments = post.comments.slice(-INITIAL_COMMENTS_COUNT);
      visibleComments.forEach(comment => {
        html += renderComment(comment, postAuthorId);
      });
      
      html += '</div>';
      html += '</div>';
    }
    
    html += renderCommentForm(post.id);
    html += '</div>';
    
    return html;
  }

  function renderComment(comment, postAuthorId) {
    // Используем флаг из API (приоритет) или fallback на сравнение ID
    let isAuthor = false;
    
    if (comment.hasOwnProperty('is_post_author')) {
      // Используем флаг из API
      isAuthor = comment.is_post_author;
    } else {
      // Fallback: сравниваем ID вручную
      const commentAuthorId = getAuthorId(comment.author);
      isAuthor = (commentAuthorId !== null && postAuthorId !== null && 
                  String(commentAuthorId) === String(postAuthorId));
    }
    
    if (DEBUG) {
      console.log(`Comment by ${comment.author?.full_name}:`, {
        is_post_author_flag: comment.is_post_author,
        calculated: isAuthor,
        comment_author_id: getAuthorId(comment.author),
        post_author_id: postAuthorId
      });
    }
    
    const commentClass = isAuthor ? 'comment-item comment-item--author' : 'comment-item';
    
    let html = `<div class="${commentClass}">`;
    html += '<div class="comment-header">';
    
    const authorName = comment.author?.full_name || 'Аноним';
    const authorId = getAuthorId(comment.author);
    
    if (authorId) {
      html += `<a href="/employees/employee/${authorId}/" class="comment-author">${escapeHtml(authorName)}</a>`;
    } else {
      html += `<span class="comment-author">${escapeHtml(authorName)}</span>`;
    }
    
    html += '<span class="comment-separator">·</span>';
    html += `<time class="comment-date">${formatDate(comment.created_at)}</time>`;
    html += '</div>';
    html += `<div class="comment-body">${formatBody(comment.text)}</div>`;
    html += '</div>';
    
    return html;
  }

  function renderCommentForm(postId) {
    let html = '<div class="comment-form-sticky">';
    html += '<div class="px-3 py-2">';
    html += `<form class="comment-form-modal" data-post-id="${postId}">`;
    html += '<div class="message-field message-field--compact">';
    
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
    return html;
  }

  /**
   * Обработчики
   */
  function scrollToBottom() {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const container = document.getElementById('commentsListContainer');
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    });
  }

  function attachPostLinkHandlers() {
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

  function attachLoadMoreCommentsHandler() {
    const loadMoreBtn = document.querySelector('.load-more-comments');
    if (!loadMoreBtn) return;

    loadMoreBtn.addEventListener('click', function() {
      const contentDiv = document.getElementById('postDetailContent');
      const allComments = JSON.parse(contentDiv.dataset.allComments || '[]');
      const postAuthorId = contentDiv.dataset.postAuthorId;
      const container = document.getElementById('commentsListContainer');
      
      if (!container || allComments.length === 0) return;

      const scrollHeight = container.scrollHeight;
      const scrollTop = container.scrollTop;
      
      let html = '';
      allComments.forEach(comment => {
        html += renderComment(comment, postAuthorId);
      });
      
      container.innerHTML = html;
      
      const newScrollHeight = container.scrollHeight;
      const heightDiff = newScrollHeight - scrollHeight;
      container.scrollTop = scrollTop + heightDiff;
      
      this.remove();
    });
  }

  function attachCommentFormHandler() {
    const form = document.querySelector('.comment-form-modal');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      const textarea = this.querySelector('textarea[name="text"]');
      const text = textarea.value.trim();
      
      if (!text) return;

      const postId = this.dataset.postId;
      await submitComment(postId, text);
      textarea.value = '';
    });
  }

  async function submitComment(postId, text) {
    const csrfToken = getCsrfToken();
    if (!csrfToken) {
      alert('Необходимо авторизоваться');
      return;
    }

    try {
      const response = await fetch(`/api/v1/posts/${postId}/comments/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ text: text })
      });

      if (response.ok) {
        // Перезагружаем пост
        await loadPostDetail(postId);
      } else {
        alert('Ошибка при отправке комментария');
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка сети');
    }
  }

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
        
        if (isLiked) {
          icon.classList.remove('bi-heart-fill', 'text-danger');
          icon.classList.add('bi-heart');
        } else {
          icon.classList.remove('bi-heart');
          icon.classList.add('bi-heart-fill', 'text-danger');
        }

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

  function showError(message) {
    const contentDiv = document.getElementById('postDetailContent');
    contentDiv.innerHTML = `
      <div class="alert alert-danger" role="alert">
        <i class="bi-exclamation-triangle"></i> ${escapeHtml(message)}
      </div>
    `;
  }

  function openPostModal(postId) {
    if (!modal) {
      console.error('Modal не инициализирован');
      return;
    }

    modal.show();
    loadPostDetail(postId);
  }

  // Инициализация
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPostDetailModal);
  } else {
    initPostDetailModal();
  }

  window.openPostModal = openPostModal;

})();

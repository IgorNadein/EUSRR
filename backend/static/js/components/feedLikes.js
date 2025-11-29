/**
 * feedLikes.js
 * Обработка лайков в карточках постов ленты
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
   * Переключение лайка
   */
  async function toggleLike(postId, button) {
    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
      alert('Необходимо авторизоваться');
      return;
    }

    const icon = button.querySelector('i');
    const countSpan = button.querySelector('.like-count');
    const isLiked = button.dataset.liked === 'true';
    const endpoint = isLiked ? 'unlike' : 'like';

    // Оптимистичное обновление UI
    button.disabled = true;

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
          button.dataset.liked = 'false';
        } else {
          icon.classList.remove('bi-heart');
          icon.classList.add('bi-heart-fill', 'text-danger');
          button.dataset.liked = 'true';
        }

        // Обновляем счетчик
        if (countSpan) {
          countSpan.textContent = data.likes_count || 0;
        }
      } else {
        alert('Ошибка при обработке лайка');
      }
    } catch (error) {
      console.error('Ошибка:', error);
      alert('Ошибка сети');
    } finally {
      button.disabled = false;
    }
  }

  /**
   * Инициализация обработчиков лайков
   */
  function initFeedLikes() {
    // Используем делегирование событий
    document.addEventListener('click', function(e) {
      const likeBtn = e.target.closest('.like-btn-card');
      if (likeBtn) {
        e.preventDefault();
        e.stopPropagation(); // Чтобы не сработал клик по карточке
        const postId = likeBtn.dataset.postId;
        if (postId) {
          toggleLike(postId, likeBtn);
        }
      }
    });
  }

  // Инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFeedLikes);
  } else {
    initFeedLikes();
  }

})();

/**
 * @module feedCrudHandler
 * @description Обработчик CRUD операций для постов и комментариев через API
 */

/**
 * Инициализирует обработчики CRUD операций для постов и комментариев
 * @param {Object} options - Опции инициализации
 * @param {string} options.postsApiUrl - URL API для списка постов
 * @param {string} options.commentsApiUrl - URL API для списка комментариев
 * @param {Object} [options.headers={}] - HTTP заголовки для запросов
 * @returns {Object} API с методом destroy
 */
export function initFeedCrudHandler(options) {
  const {
    postsApiUrl,
    commentsApiUrl,
    headers = {}
  } = options;

  // Для multipart/form-data убираем Content-Type, оставляем только Authorization
  const authHeaders = {};
  if (headers['Authorization']) {
    authHeaders['Authorization'] = headers['Authorization'];
  }

  // Формы постов
  const postCreateForm = document.getElementById('postCreateForm');
  const postEditForm = document.getElementById('postEditForm');
  const postDeleteForm = document.getElementById('postDeleteForm');
  
  // Формы комментариев
  const commentCreateForm = document.getElementById('commentCreateForm');
  const commentEditForm = document.getElementById('commentEditForm');
  const commentDeleteForm = document.getElementById('commentDeleteForm');

  // Массив для хранения обработчиков
  const handlers = [];

  /**
   * Обработчик создания поста
   */
  async function handlePostCreate(e) {
    e.preventDefault();
    
    const formData = new FormData(postCreateForm);
    
    try {
      const response = await fetch(postsApiUrl, {
        method: 'POST',
        headers: authHeaders,  // Только Authorization, без Content-Type
        body: formData
      });

      if (response.ok) {
        alert('Публикация создана!');
        window.location.reload();
      } else {
        const error = await response.json();
        let errorMsg = 'Ошибка создания публикации:\n';
        for (const [field, errors] of Object.entries(error)) {
          errorMsg += `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}\n`;
        }
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Error creating post:', error);
      alert('Ошибка сети при создании публикации');
    }
  }

  /**
   * Обработчик редактирования поста
   */
  async function handlePostEdit(e) {
    e.preventDefault();
    
    const postId = postEditForm.dataset.postId;
    if (!postId) {
      alert('ID поста не найден');
      return;
    }

    const formData = new FormData(postEditForm);
    
    try {
      const response = await fetch(`${postsApiUrl}${postId}/`, {
        method: 'PATCH',
        headers: authHeaders,  // Только Authorization
        body: formData
      });

      if (response.ok) {
        alert('Публикация обновлена!');
        window.location.reload();
      } else {
        const error = await response.json();
        let errorMsg = 'Ошибка обновления публикации:\n';
        for (const [field, errors] of Object.entries(error)) {
          errorMsg += `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}\n`;
        }
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Error updating post:', error);
      alert('Ошибка сети при обновлении публикации');
    }
  }

  /**
   * Обработчик удаления поста
   */
  async function handlePostDelete(e) {
    e.preventDefault();
    
    const postId = postDeleteForm.dataset.postId;
    if (!postId) {
      alert('ID поста не найден');
      return;
    }

    if (!confirm('Вы уверены, что хотите удалить эту публикацию?')) {
      return;
    }

    try {
      const response = await fetch(`${postsApiUrl}${postId}/`, {
        method: 'DELETE',
        headers: headers
      });

      if (response.ok || response.status === 204) {
        alert('Публикация удалена');
        // Перенаправляем на главную ленту
        window.location.href = postDeleteForm.dataset.redirectUrl || '/feed/';
      } else {
        alert(`Ошибка удаления: ${response.status}`);
      }
    } catch (error) {
      console.error('Error deleting post:', error);
      alert('Ошибка сети при удалении публикации');
    }
  }

  /**
   * Обработчик закрепления/открепления поста
   */
  async function handlePinPost(e) {
    e.preventDefault();
    
    const button = e.currentTarget;
    const postId = button.dataset.postId;
    const action = button.dataset.action; // 'pin' or 'unpin'
    
    if (!postId) {
      alert('ID поста не найден');
      return;
    }

    try {
      const response = await fetch(`${postsApiUrl}${postId}/${action}/`, {
        method: 'POST',
        headers: headers
      });

      if (response.ok) {
        alert(action === 'pin' ? 'Новость закреплена!' : 'Новость откреплена!');
        window.location.reload();
      } else {
        alert(`Ошибка: ${response.status}`);
      }
    } catch (error) {
      console.error('Error pinning/unpinning post:', error);
      alert('Ошибка сети');
    }
  }

  /**
   * Обработчик создания комментария
   */
  async function handleCommentCreate(e) {
    e.preventDefault();
    
    const formData = new FormData(commentCreateForm);
    
    try {
      const response = await fetch(commentsApiUrl, {
        method: 'POST',
        headers: authHeaders,  // Только Authorization
        body: formData
      });

      if (response.ok) {
        alert('Комментарий добавлен!');
        window.location.reload();
      } else {
        const error = await response.json();
        let errorMsg = 'Ошибка добавления комментария:\n';
        for (const [field, errors] of Object.entries(error)) {
          errorMsg += `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}\n`;
        }
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Error creating comment:', error);
      alert('Ошибка сети при добавлении комментария');
    }
  }

  /**
   * Обработчик редактирования комментария
   */
  async function handleCommentEdit(e) {
    e.preventDefault();
    
    const commentId = commentEditForm.dataset.commentId;
    if (!commentId) {
      alert('ID комментария не найден');
      return;
    }

    const formData = new FormData(commentEditForm);
    
    try {
      const response = await fetch(`${commentsApiUrl}${commentId}/`, {
        method: 'PATCH',
        headers: authHeaders,  // Только Authorization
        body: formData
      });

      if (response.ok) {
        alert('Комментарий обновлён!');
        const postId = commentEditForm.dataset.postId;
        if (postId) {
          window.location.href = `/feed/post/${postId}/#c${commentId}`;
        } else {
          window.location.reload();
        }
      } else {
        const error = await response.json();
        let errorMsg = 'Ошибка обновления комментария:\n';
        for (const [field, errors] of Object.entries(error)) {
          errorMsg += `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}\n`;
        }
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Error updating comment:', error);
      alert('Ошибка сети при обновлении комментария');
    }
  }

  /**
   * Обработчик удаления комментария
   */
  async function handleCommentDelete(e) {
    e.preventDefault();
    
    const commentId = commentDeleteForm.dataset.commentId;
    if (!commentId) {
      alert('ID комментария не найден');
      return;
    }

    if (!confirm('Вы уверены, что хотите удалить этот комментарий?')) {
      return;
    }

    try {
      const response = await fetch(`${commentsApiUrl}${commentId}/`, {
        method: 'DELETE',
        headers: headers
      });

      if (response.ok || response.status === 204) {
        alert('Комментарий удалён');
        const postId = commentDeleteForm.dataset.postId;
        if (postId) {
          window.location.href = `/feed/post/${postId}/`;
        } else {
          window.location.reload();
        }
      } else {
        alert(`Ошибка удаления: ${response.status}`);
      }
    } catch (error) {
      console.error('Error deleting comment:', error);
      alert('Ошибка сети при удалении комментария');
    }
  }

  // Привязываем обработчики к формам
  if (postCreateForm) {
    postCreateForm.addEventListener('submit', handlePostCreate);
    handlers.push({ element: postCreateForm, event: 'submit', handler: handlePostCreate });
  }

  if (postEditForm) {
    postEditForm.addEventListener('submit', handlePostEdit);
    handlers.push({ element: postEditForm, event: 'submit', handler: handlePostEdit });
  }

  if (postDeleteForm) {
    postDeleteForm.addEventListener('submit', handlePostDelete);
    handlers.push({ element: postDeleteForm, event: 'submit', handler: handlePostDelete });
  }

  if (commentCreateForm) {
    commentCreateForm.addEventListener('submit', handleCommentCreate);
    handlers.push({ element: commentCreateForm, event: 'submit', handler: handleCommentCreate });
  }

  if (commentEditForm) {
    commentEditForm.addEventListener('submit', handleCommentEdit);
    handlers.push({ element: commentEditForm, event: 'submit', handler: handleCommentEdit });
  }

  if (commentDeleteForm) {
    commentDeleteForm.addEventListener('submit', handleCommentDelete);
    handlers.push({ element: commentDeleteForm, event: 'submit', handler: handleCommentDelete });
  }

  // Привязываем обработчики к кнопкам закрепления
  const pinButtons = document.querySelectorAll('[data-action="pin"], [data-action="unpin"]');
  pinButtons.forEach(button => {
    button.addEventListener('click', handlePinPost);
    handlers.push({ element: button, event: 'click', handler: handlePinPost });
  });

  // Возвращаем API для очистки
  return {
    destroy() {
      handlers.forEach(({ element, event, handler }) => {
        element.removeEventListener(event, handler);
      });
      handlers.length = 0;
    }
  };
}

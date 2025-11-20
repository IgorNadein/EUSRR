/**
 * likeHandler.js
 * Глобальный обработчик лайков для постов
 * Работает через data-атрибуты и поддерживает AJAX-запросы
 * 
 * @module likeHandler
 * @version 1.0.0
 */

import { getCookie } from '../utils/stringUtils.js';

/**
 * Инициализация глобального обработчика лайков
 * Работает через делегирование событий на document
 */
export function initLikeHandler() {
  document.addEventListener('click', handleLikeClick, { passive: false });
  console.log('likeHandler: initialized');

  return {
    destroy: () => document.removeEventListener('click', handleLikeClick)
  };
}

/**
 * Обработчик клика на кнопку лайка
 * @param {MouseEvent} e - Событие клика
 */
async function handleLikeClick(e) {
  const btn = e.target.closest('[data-like-post]');
  if (!btn) return;

  e.preventDefault();

  const url = btn.getAttribute('data-like-url');
  if (!url || btn.disabled) return;

  // Определяем текущее состояние и операцию
  const currentlyLiked =
    btn.classList.contains('is-liked') ||
    btn.getAttribute('aria-pressed') === 'true';
  const op = currentlyLiked ? 'unlike' : 'like';

  btn.disabled = true;
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: new URLSearchParams({ op })
    });

    if (!resp.ok) throw new Error('HTTP ' + resp.status);

    const data = await resp.json().catch(() => ({}));

    // Совместимость с разными ключами API
    const liked = (data.liked !== undefined) ? !!data.liked
                : (data.is_liked !== undefined) ? !!data.is_liked
                : !currentlyLiked; // fallback - инвертируем

    const count = (data.likes !== undefined) ? data.likes
                : (data.likes_count !== undefined) ? data.likes_count
                : null;

    // Обновляем UI кнопки
    updateLikeButton(btn, liked);

    // Обновляем счетчик
    updateLikeCount(btn, count);

    // Поддержка серверного постбэка (для форм)
    updateFormOpInput(btn, liked);

  } catch (err) {
    console.error('likeHandler error:', err);
  } finally {
    btn.disabled = false;
  }
}

/**
 * Обновить визуальное состояние кнопки лайка
 * @param {HTMLElement} btn - Кнопка лайка
 * @param {boolean} liked - Новое состояние (лайкнуто/не лайкнуто)
 */
function updateLikeButton(btn, liked) {
  btn.classList.toggle('is-liked', liked);
  btn.setAttribute('aria-pressed', liked ? 'true' : 'false');

  // Переключаем иконку (пустое/заполненное сердце)
  const icon = btn.querySelector('.bi');
  if (icon) {
    icon.classList.toggle('bi-heart', !liked);
    icon.classList.toggle('bi-heart-fill', liked);
  }
}

/**
 * Обновить счетчик лайков
 * @param {HTMLElement} btn - Кнопка лайка
 * @param {number|null} count - Новое количество лайков
 */
function updateLikeCount(btn, count) {
  if (count === null) return;

  const card = btn.closest('[data-post-card]');
  const cnt = card?.querySelector('[data-like-count]');
  if (cnt) {
    cnt.textContent = String(count);
  }
}

/**
 * Обновить скрытый input для серверного постбэка
 * @param {HTMLElement} btn - Кнопка лайка
 * @param {boolean} liked - Текущее состояние
 */
function updateFormOpInput(btn, liked) {
  const form = btn.closest('form');
  const opInput = form?.querySelector('input[name="op"]');
  if (opInput) {
    opInput.value = liked ? 'unlike' : 'like';
  }
}

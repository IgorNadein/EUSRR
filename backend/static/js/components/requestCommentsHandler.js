/**
 * @fileoverview Request Comments Handler - управление комментариями к заявкам
 * Загрузка, отображение и добавление комментариев через AJAX
 * @module components/requestCommentsHandler
 */

import { esc } from '../utils/stringUtils.js';

/**
 * Инициализирует обработчик комментариев к заявкам
 * 
 * @param {Object} options - Опции инициализации
 * @param {string} options.commentsUrlTemplate - URL шаблон для получения комментариев (с /0/)
 * @param {string} options.addCommentUrlTemplate - URL шаблон для добавления комментария (с /0/)
 * @param {string} [options.collapseSelector='[data-comments-collapse]'] - Селектор collapse элементов
 * @param {boolean} [options.autoloadCounts=true] - Автозагрузка счётчиков комментариев
 * @returns {Object} API обработчика
 */
export function initRequestCommentsHandler(options) {
  const {
    commentsUrlTemplate,
    addCommentUrlTemplate,
    collapseSelector = '[data-comments-collapse]',
    autoloadCounts = true
  } = options;
  
  if (!commentsUrlTemplate || !addCommentUrlTemplate) {
    console.warn('RequestCommentsHandler: URL templates are required');
    return null;
  }
  
  /**
   * Рендерит HTML комментария
   * @param {Object} comment - Объект комментария
   * @returns {string} HTML строка
   */
  function renderComment(comment) {
    const authorName = (comment.author && 
      (comment.author.full_name || comment.author.display_name || comment.author.username)) || '—';
    const authorId = comment.author?.id;
    const authorLink = authorId 
      ? `/employees/${authorId}/`
      : '#';
    const commentDate = esc(comment.created_at || '');
    
    return `<div class="comment-item">
      <div class="comment-header">
        ${authorId 
          ? `<a href="${authorLink}" class="comment-author">${esc(authorName)}</a>`
          : `<span class="comment-author">${esc(authorName)}</span>`
        }
        <span class="comment-separator">·</span>
        <time class="comment-date">${commentDate}</time>
      </div>
      <div class="comment-body">${esc(comment.text || '')}</div>
    </div>`;
  }
  
  /**
   * Обновляет счётчик комментариев для заявки
   * @param {string} reqId - ID заявки
   * @param {number} count - Количество комментариев
   */
  function updateCount(reqId, count) {
    const btn = document.querySelector(`[data-bs-target="#rcoll-${reqId}"] [data-role="count"]`) ||
                document.querySelector(`#req-${reqId} [data-role="count"]`);
    
    if (btn) {
      btn.textContent = count;
    }
  }
  
  /**
   * Загружает комментарии для заявки
   * @param {HTMLElement} collapseEl - Collapse элемент
   */
  async function loadComments(collapseEl) {
    const reqId = collapseEl.getAttribute('data-request-id');
    const block = collapseEl.querySelector('.comments-block');
    const listEl = block.querySelector('[data-role=list]');
    const spinner = block.querySelector('.spinner-border');
    
    // Проверяем, загружены ли уже комментарии
    if (collapseEl.dataset.loaded === '1') return;
    
    spinner.style.display = 'inline-block';
    
    try {
      const url = commentsUrlTemplate.replace('/0/', `/${reqId}/`);
      const resp = await fetch(url, {
        headers: { 'Accept': 'application/json' }
      });
      
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      
      const data = await resp.json();
      
      // Рендерим комментарии
      if (data.length) {
        listEl.innerHTML = data.map(renderComment).join('');
      } else {
        listEl.innerHTML = '<div class="small text-body-secondary">Комментариев нет.</div>';
      }
      
      collapseEl.dataset.loaded = '1';
      updateCount(reqId, data.length);
    } catch (e) {
      listEl.innerHTML = '<div class="small text-danger">Не удалось загрузить.</div>';
      console.error('Failed to load comments:', e);
    } finally {
      spinner.style.display = 'none';
    }
  }
  
  /**
   * Отправляет новый комментарий
   * @param {HTMLElement} block - Блок комментариев
   * @param {string} text - Текст комментария
   * @returns {Promise<Object>} Сохранённый комментарий
   */
  async function postComment(block, text) {
    const reqId = block.closest(collapseSelector).getAttribute('data-request-id');
    const form = block.querySelector('form[data-role="form"]');
    const formData = new FormData(form);
    formData.set('text', text);
    
    const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
    const url = addCommentUrlTemplate.replace('/0/', `/${reqId}/`);
    
    const resp = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: { 'X-CSRFToken': csrfToken },
      credentials: 'same-origin'
    });
    
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    
    return resp.json();
  }
  
  /**
   * Обработчик открытия collapse с комментариями
   */
  function handleCollapseShow(e) {
    if (!e.target.matches(collapseSelector)) return;
    loadComments(e.target);
  }
  
  /**
   * Обработчик отправки формы комментария
   */
  async function handleCommentSubmit(e) {
    const form = e.target;
    
    // Проверяем, что это форма комментария
    if (!form.matches('form[data-role=form]')) return;
    
    // Проверяем, что форма находится внутри блока заявки
    if (!form.closest(collapseSelector)) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const block = form.closest('.comments-block');
    const textarea = form.querySelector('[data-role=text]');
    const submitBtn = form.querySelector('button[type="submit"]');
    const txt = (textarea.value || '').trim();
    
    if (!txt) return;
    
    submitBtn.disabled = true;
    
    try {
      const saved = await postComment(block, txt);
      const listEl = block.querySelector('[data-role=list]');
      
      // Удаляем заглушку "нет комментариев"
      if (listEl.querySelector('.text-body-secondary')) {
        listEl.innerHTML = '';
      }
      
      // Добавляем новый комментарий
      listEl.insertAdjacentHTML('beforeend', renderComment(saved));
      textarea.value = '';
      
      // Обновляем счётчик
      const reqId = block.closest(collapseSelector).getAttribute('data-request-id');
      updateCount(reqId, listEl.querySelectorAll('.comment-item').length);
    } catch (err) {
      alert('Ошибка отправки комментария');
      console.error('Failed to post comment:', err);
    } finally {
      submitBtn.disabled = false;
    }
  }
  
  /**
   * Загружает счётчик комментариев для одной заявки
   */
  async function fetchCount(reqId, span) {
    try {
      const url = commentsUrlTemplate.replace('/0/', `/${reqId}/`);
      const resp = await fetch(url, {
        headers: { 'Accept': 'application/json' }
      });
      
      if (!resp.ok) return;
      
      const data = await resp.json();
      span.textContent = Array.isArray(data) ? data.length : 0;
    } catch (e) {
      // Игнорируем ошибки при загрузке счётчиков
    }
  }
  
  /**
   * Автозагрузка всех счётчиков комментариев
   */
  function autoloadAllCounts() {
    document.querySelectorAll(collapseSelector).forEach(el => {
      const reqId = el.getAttribute('data-request-id');
      const span = document.querySelector(`[data-bs-target="#rcoll-${reqId}"] [data-role="count"]`);
      
      if (span && span.textContent.trim() === '0') {
        fetchCount(reqId, span);
      }
    });
  }
  
  // Подключаем обработчики событий
  document.addEventListener('show.bs.collapse', handleCollapseShow);
  document.addEventListener('submit', handleCommentSubmit);
  
  // Автозагрузка счётчиков
  if (autoloadCounts) {
    document.addEventListener('DOMContentLoaded', autoloadAllCounts);
  }
  
  // API
  return {
    loadComments,
    postComment,
    updateCount,
    renderComment,
    
    /**
     * Уничтожение обработчиков
     */
    destroy: () => {
      document.removeEventListener('show.bs.collapse', handleCollapseShow);
      document.removeEventListener('submit', handleCommentSubmit);
    }
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initRequestCommentsHandler = initRequestCommentsHandler;
}

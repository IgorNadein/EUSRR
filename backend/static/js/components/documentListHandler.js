/**
 * @module documentListHandler
 * @description Загружает и отображает список документов через API
 */

/**
 * Инициализирует обработчик списка документов
 * @param {Object} options - Опции инициализации
 * @param {string} options.apiListUrl - URL API для списка документов
 * @param {string} options.acknowledgeUrlTemplate - Шаблон URL для ознакомления: "/documents/ack/{id}/"
 * @param {number} options.userId - ID текущего пользователя
 * @param {boolean} options.canManage - Может ли пользователь управлять документами
 * @param {Object} options.headers - HTTP заголовки для запросов
 * @returns {Object} API с методами load, destroy
 */
export function initDocumentListHandler(options) {
  const {
    apiListUrl,
    acknowledgeUrlTemplate,
    userId,
    canManage,
    headers = {}
  } = options;

  const listElement = document.getElementById('docList');
  const paginationElement = document.querySelector('.pagination-container');
  
  if (!listElement) {
    console.warn('initDocumentListHandler: #docList not found');
    return { load: () => {}, destroy: () => {} };
  }

  // Текущее состояние
  let currentScope = 'mine'; // 'mine' | 'all'
  let currentPage = 1;
  let currentAckStatus = ''; // '' | 'acked' | 'not_acked'

  /**
   * Загружает документы с API
   */
  async function loadDocuments() {
    try {
      const params = new URLSearchParams({ page: currentPage });
      const response = await fetch(`${apiListUrl}?${params}`, { headers });
      
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      const data = await response.json();
      renderDocuments(data);
    } catch (error) {
      console.error('Ошибка загрузки документов:', error);
      listElement.innerHTML = '<div class="p-4 text-center text-danger">Не удалось загрузить документы</div>';
    }
  }

  /**
   * Фильтрует документы для текущего пользователя
   * @param {Array} items - Список документов
   * @returns {Array} Отфильтрованный список
   */
  function filterForUser(items) {
    if (currentScope === 'all') {
      return items;
    }

    return items.filter(doc => {
      // 1. Отправлен всем
      if (doc.sent_to_all) return true;

      // 2. Загружен текущим пользователем
      if (doc.uploaded_by && doc.uploaded_by.id === userId) return true;

      // 3. В списке получателей
      if (doc.recipients && doc.recipients.some(r => r.id === userId)) return true;

      // 4. Есть отделы (упрощённая проверка)
      if (doc.departments && doc.departments.length > 0) return true;

      return false;
    });
  }

  /**
   * Фильтрует по статусу ознакомления
   * @param {Array} items - Список документов
   * @returns {Array} Отфильтрованный список
   */
  function filterByAckStatus(items) {
    if (!currentAckStatus) return items;
    
    if (currentAckStatus === 'acked') {
      return items.filter(doc => doc.is_acknowledged);
    } else if (currentAckStatus === 'not_acked') {
      return items.filter(doc => !doc.is_acknowledged);
    }
    
    return items;
  }

  /**
   * Отображает список документов
   * @param {Object} data - Данные от API
   */
  function renderDocuments(data) {
    const allItems = data.results || [];
    let items = filterForUser(allItems);
    items = filterByAckStatus(items);

    if (items.length === 0) {
      listElement.innerHTML = '<div class="p-4 text-center text-secondary">Нет доступных документов.</div>';
      if (paginationElement) paginationElement.innerHTML = '';
      return;
    }

    // Рендерим документы
    listElement.innerHTML = items.map(doc => renderDocumentRow(doc)).join('');

    // Рендерим пагинацию
    if (paginationElement) {
      renderPagination(data);
    }
  }

  /**
   * Рендерит строку документа
   * @param {Object} doc - Документ
   * @returns {string} HTML
   */
  function renderDocumentRow(doc) {
    const isAcked = doc.is_acknowledged;
    const showAdminControls = canManage && currentScope === 'all';
    
    let linkUrl = doc.file_url || '#';
    if (!isAcked && currentScope === 'mine') {
      linkUrl = acknowledgeUrlTemplate.replace('{id}', doc.id);
    }

    return `
      <div class="doc-row ${!isAcked ? 'doc-unacked' : ''}" 
           data-doc-id="${doc.id}"
           data-is-acked="${isAcked ? '1' : '0'}">
        <div class="card-header">
          <div class="feed-ico" aria-hidden="true"><i class="bi-file-earmark-text"></i></div>

          <div class="feed-main">
            <div class="card-title">
              ${doc.file_url ? `
                <a href="${linkUrl}" 
                   class="text-decoration-none doc-link" 
                   target="_blank" 
                   rel="noopener">
                  ${doc.title || 'Без названия'}
                </a>
              ` : doc.title || 'Без названия'}
            </div>
            <div class="card-subtitle">
              ${doc.description || '— без описания —'}
              ${doc.uploaded_at ? ` • Загружен: ${formatDate(doc.uploaded_at)}` : ''}
              ${doc.sent_to_all ? ' • Для всех' : ''}
            </div>
          </div>

          <div class="doc-actions">
            ${currentScope === 'mine' && isAcked ? `
              <span class="badge-acked">✓ Ознакомлен</span>
            ` : ''}

            ${currentScope === 'all' ? `
              <button type="button"
                      class="btn btn-outline-secondary"
                      data-action="show-acks"
                      data-doc-id="${doc.id}"
                      data-doc-title="${escapeHtml(doc.title || 'Документ')}">
                Ознакомления
              </button>
            ` : ''}

            ${showAdminControls ? `
              <button type="button"
                      class="btn-icon"
                      data-bs-toggle="tooltip"
                      title="Редактировать"
                      data-action="edit"
                      data-doc-id="${doc.id}"
                      data-doc-title="${escapeHtml(doc.title || '')}"
                      data-doc-description="${escapeHtml(doc.description || '')}"
                      data-doc-sent_to_all="${doc.sent_to_all ? '1' : '0'}">
                <i class="bi-pencil-square"></i>
              </button>
              <button type="button"
                      class="btn-icon btn-icon--danger"
                      data-bs-toggle="tooltip"
                      title="Удалить"
                      data-action="delete"
                      data-doc-id="${doc.id}">
                <i class="bi-trash"></i>
              </button>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Рендерит пагинацию
   * @param {Object} data - Данные от API с next/previous
   */
  function renderPagination(data) {
    if (!data.next && !data.previous && currentPage === 1) {
      paginationElement.innerHTML = '';
      return;
    }

    paginationElement.innerHTML = `
      <div class="d-flex justify-content-between mb-3">
        <button class="btn btn-outline-secondary ${!data.previous ? 'disabled' : ''}"
                data-action="prev-page">
          <i class="bi-chevron-left"></i> Назад
        </button>
        <button class="btn btn-outline-secondary ${!data.next ? 'disabled' : ''}"
                data-action="next-page">
          Вперёд <i class="bi-chevron-right"></i>
        </button>
      </div>
    `;
  }

  /**
   * Обработчик кликов по пагинации
   */
  function handlePaginationClick(e) {
    const button = e.target.closest('button[data-action]');
    if (!button || button.classList.contains('disabled')) return;

    const action = button.getAttribute('data-action');
    
    if (action === 'prev-page') {
      currentPage = Math.max(1, currentPage - 1);
      loadDocuments();
    } else if (action === 'next-page') {
      currentPage += 1;
      loadDocuments();
    }
  }

  /**
   * Форматирует дату
   * @param {string} dateStr - ISO дата
   * @returns {string} Отформатированная дата
   */
  function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * Экранирует HTML
   * @param {string} str - Строка
   * @returns {string} Экранированная строка
   */
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Установка обработчиков
  if (paginationElement) {
    paginationElement.addEventListener('click', handlePaginationClick);
  }

  /**
   * Публичный API для изменения фильтров
   */
  function setScope(scope) {
    currentScope = scope;
    currentPage = 1;
    loadDocuments();
  }

  function setAckStatus(status) {
    currentAckStatus = status;
    currentPage = 1;
    loadDocuments();
  }

  /**
   * Очистка обработчиков
   */
  function destroy() {
    if (paginationElement) {
      paginationElement.removeEventListener('click', handlePaginationClick);
    }
  }

  // Начальная загрузка
  loadDocuments();

  return {
    load: loadDocuments,
    setScope,
    setAckStatus,
    destroy
  };
}

// Экспорт для совместимости
if (typeof window !== 'undefined') {
  window.initDocumentListHandler = initDocumentListHandler;
}

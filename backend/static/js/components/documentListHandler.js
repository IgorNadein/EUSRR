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
  const urlParams = new URLSearchParams(window.location.search);
  let currentScope = urlParams.get('scope') || 'mine'; // 'mine' | 'all'
  let currentAckStatus = urlParams.get('ack_status') || ''; // '' | 'acked' | 'not_acked'
  let allDocuments = []; // Все загруженные документы
  let loading = false;
  let hasMore = true;
  let nextUrl = null;
  let totalCount = 0;
  
  console.log('documentListHandler: init with scope =', currentScope, 'ack_status =', currentAckStatus);
  
  // Intersection Observer для бесконечной прокрутки
  let observerTarget = null;
  let observer = null;

  /**
   * Загружает документы с API
   * @param {boolean} append - Добавить к существующим или заменить
   * @returns {Promise<Array>} Массив новых документов
   */
  async function loadDocuments(append = false) {
    if (loading || (append && !hasMore)) {
      console.log('loadDocuments: skipped', { loading, append, hasMore });
      return [];
    }
    
    loading = true;
    showLoadingSpinner();
    
    try {
      let url;
      if (append && nextUrl) {
        url = nextUrl;
        console.log('loadDocuments: using nextUrl', url);
      } else if (append && !nextUrl) {
        console.warn('loadDocuments: append=true but no nextUrl, stopping');
        loading = false;
        hideLoadingSpinner();
        return [];
      } else {
        // Формируем URL с параметрами scope
        const params = new URLSearchParams();
        if (currentScope === 'mine') {
          params.append('scope', 'mine');
        }
        // ack_status фильтруется на клиенте, не в API
        
        url = `${apiListUrl}?${params}`;
        console.log('loadDocuments: initial load', url, 'scope:', currentScope);
      }
      
      const response = await fetch(url, { headers });
      
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      const data = await response.json();
      const newDocuments = data.results || [];
      
      console.log('loadDocuments: received', {
        newCount: newDocuments.length,
        totalCount: data.count,
        hasNext: !!data.next,
        currentDocuments: allDocuments.length
      });
      
      // Сохраняем метаданные
      totalCount = data.count || newDocuments.length;
      nextUrl = data.next || null;
      hasMore = !!nextUrl;
      
      if (append) {
        allDocuments = [...allDocuments, ...newDocuments];
        console.log('loadDocuments: appended, total now:', allDocuments.length);
      } else {
        allDocuments = newDocuments;
        console.log('loadDocuments: replaced, total now:', allDocuments.length);
      }
      
      loading = false;
      hideLoadingSpinner();
      
      return newDocuments;
    } catch (error) {
      console.error('Ошибка загрузки документов:', error);
      loading = false;
      hideLoadingSpinner();
      listElement.innerHTML = '<div class="p-4 text-center text-danger">Не удалось загрузить документы</div>';
      return [];
    }
  }
  
  /**
   * Показать спиннер загрузки
   */
  function showLoadingSpinner() {
    const existing = listElement.querySelector('.loading-spinner');
    if (existing) return;
    
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner text-center py-4';
    spinner.innerHTML = `
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    `;
    listElement.appendChild(spinner);
  }
  
  /**
   * Скрыть спиннер загрузки
   */
  function hideLoadingSpinner() {
    const spinner = listElement.querySelector('.loading-spinner');
    if (spinner) {
      spinner.remove();
    }
  }
  
  /**
   * Загрузка следующей порции документов
   */
  async function loadMore() {
    console.log('loadMore: triggered', {
      hasMore,
      loading,
      nextUrl,
      currentCount: allDocuments.length
    });
    
    try {
      const newDocuments = await loadDocuments(true); // append = true
      renderDocuments(newDocuments, true); // append = true
    } catch (error) {
      console.error('Failed to load more documents:', error);
    }
  }
  
  /**
   * Настройка Intersection Observer для бесконечной прокрутки
   */
  function setupInfiniteScroll() {
    if (!observerTarget) return;
    
    // Создаем observer
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting && hasMore && !loading) {
            loadMore();
          }
        });
      },
      {
        root: null,
        rootMargin: '100px',
        threshold: 0.01
      }
    );
    
    // Наблюдаем за observer target
    observer.observe(observerTarget);
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
   * @param {Array} documents - Документы для рендеринга
   * @param {boolean} append - Добавить к существующим или заменить
   */
  function renderDocuments(documents, append = false) {
    if (!documents || documents.length === 0) {
      if (!append) {
        listElement.innerHTML = '<div class="p-4 text-center text-secondary">Нет доступных документов.</div>';
        if (paginationElement) paginationElement.innerHTML = '';
      }
      return;
    }

    let items = filterForUser(documents);
    items = filterByAckStatus(items);
    
    if (items.length === 0 && !append) {
      listElement.innerHTML = '<div class="p-4 text-center text-secondary">Нет доступных документов.</div>';
      if (paginationElement) paginationElement.innerHTML = '';
      return;
    }

    console.log('renderDocuments: rendering', {
      count: items.length,
      append,
      totalInMemory: allDocuments.length
    });

    const itemsHtml = items.map(doc => renderDocumentRow(doc)).join('');
    
    if (append) {
      // Удаляем observer target перед добавлением
      if (observerTarget && observerTarget.parentNode) {
        observerTarget.remove();
      }
      // Добавляем новые карточки
      listElement.insertAdjacentHTML('beforeend', itemsHtml);
      console.log('renderDocuments: appended to DOM');
      // Возвращаем observer target обратно
      if (observerTarget) {
        listElement.appendChild(observerTarget);
      }
    } else {
      listElement.innerHTML = itemsHtml;
      console.log('renderDocuments: replaced DOM');
      // Создаем observer target при первой загрузке
      if (hasMore && !observerTarget) {
        observerTarget = document.createElement('div');
        observerTarget.className = 'load-more-trigger';
        observerTarget.style.height = '1px';
        listElement.appendChild(observerTarget);
      }
    }

    // Убираем старую пагинацию
    if (paginationElement) {
      paginationElement.innerHTML = '';
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

  /**
   * Публичный API для изменения фильтров
   */
  async function setScope(scope) {
    currentScope = scope;
    hasMore = true;
    nextUrl = null;
    allDocuments = [];
    const docs = await loadDocuments(false);
    renderDocuments(docs, false);
    setupInfiniteScroll();
  }

  async function setAckStatus(status) {
    currentAckStatus = status;
    hasMore = true;
    nextUrl = null;
    allDocuments = [];
    const docs = await loadDocuments(false);
    renderDocuments(docs, false);
    setupInfiniteScroll();
  }

  /**
   * Очистка обработчиков
   */
  function destroy() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  }

  // Начальная загрузка
  (async () => {
    hasMore = true;
    const docs = await loadDocuments(false);
    renderDocuments(docs, false);
    setupInfiniteScroll();
  })();

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

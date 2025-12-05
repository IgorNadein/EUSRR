/**
 * @module requestListHandler
 * @description Загружает и отображает список заявлений через API с бесконечной прокруткой
 */

/**
 * Инициализирует обработчик списка заявлений
 * @param {Object} options - Опции инициализации
 * @param {string} options.apiListUrl - URL API для списка заявлений
 * @param {string} options.scope - Область ('my' | 'all')
 * @param {number} options.userId - ID текущего пользователя
 * @param {Object} options.headers - HTTP заголовки для запросов
 * @returns {Object} API с методами load, destroy
 */
export function initRequestListHandler(options) {
  const {
    apiListUrl,
    scope = 'my',
    userId,
    headers = {}
  } = options;

  const listElement = document.getElementById('requestList');
  const searchInput = document.getElementById('requestFilter');
  
  if (!listElement) {
    console.warn('initRequestListHandler: #requestList not found');
    return { load: () => {}, destroy: () => {} };
  }

  // Текущее состояние
  const urlParams = new URLSearchParams(window.location.search);
  let currentScope = scope;
  let currentStatus = urlParams.get('status') || ''; // 'pending', 'approved', 'rejected', 'cancelled', 'draft'
  let searchQuery = ''; // Поисковый запрос
  let allRequests = []; // Все загруженные заявления
  let loading = false;
  let hasMore = true;
  let nextUrl = null;
  let totalCount = 0;
  
  console.log('requestListHandler: init with scope =', currentScope, 'status =', currentStatus);
  
  // Intersection Observer для бесконечной прокрутки
  let observerTarget = null;
  let observer = null;

  /**
   * Загружает заявления с API
   * @param {boolean} append - Добавить к существующим или заменить
   * @returns {Promise<Array>} Массив новых заявлений
   */
  async function loadRequests(append = false) {
    if (loading || (append && !hasMore)) {
      console.log('loadRequests: skipped', { loading, append, hasMore });
      return [];
    }
    
    loading = true;
    showLoadingSpinner();
    
    try {
      let url;
      if (append && nextUrl) {
        url = nextUrl;
        console.log('loadRequests: using nextUrl', url);
      } else if (append && !nextUrl) {
        console.warn('loadRequests: append=true but no nextUrl, stopping');
        loading = false;
        hideLoadingSpinner();
        return [];
      } else {
        // Формируем URL с параметрами
        const params = new URLSearchParams();
        if (currentScope === 'my') {
          params.append('scope', 'my');
        }
        if (currentStatus) {
          params.append('status', currentStatus);
        }
        
        url = `${apiListUrl}?${params}`;
        console.log('loadRequests: initial load', url, 'scope:', currentScope, 'status:', currentStatus);
      }
      
      const response = await fetch(url, { headers });
      
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      const data = await response.json();
      const newRequests = data.results || [];
      
      console.log('loadRequests: received', {
        newCount: newRequests.length,
        totalCount: data.count,
        hasNext: !!data.next,
        currentRequests: allRequests.length
      });
      
      // Сохраняем метаданные
      totalCount = data.count || newRequests.length;
      nextUrl = data.next || null;
      hasMore = !!nextUrl;
      
      if (append) {
        allRequests = [...allRequests, ...newRequests];
        console.log('loadRequests: appended, total now:', allRequests.length);
      } else {
        allRequests = newRequests;
        console.log('loadRequests: replaced, total now:', allRequests.length);
      }
      
      loading = false;
      hideLoadingSpinner();
      
      return newRequests;
    } catch (error) {
      console.error('Ошибка загрузки заявлений:', error);
      loading = false;
      hideLoadingSpinner();
      listElement.innerHTML = '<div class="p-4 text-center text-danger">Не удалось загрузить заявления</div>';
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
   * Загрузка следующей порции заявлений
   */
  async function loadMore() {
    console.log('loadMore: triggered', {
      hasMore,
      loading,
      nextUrl,
      currentCount: allRequests.length
    });
    
    try {
      const newRequests = await loadRequests(true); // append = true
      renderRequests(newRequests, true); // append = true
    } catch (error) {
      console.error('Failed to load more requests:', error);
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
   * Фильтрует по поисковому запросу
   * @param {Array} items - Список заявлений
   * @returns {Array} Отфильтрованный список
   */
  function filterBySearch(items) {
    if (!searchQuery.trim()) return items;
    
    const query = searchQuery.toLowerCase().trim();
    return items.filter(req => {
      const type = (req.type_display || req.type || '').toLowerCase();
      const comment = (req.comment || '').toLowerCase();
      return type.includes(query) || comment.includes(query);
    });
  }

  /**
   * Отображает список заявлений
   * @param {Array} requests - Заявления для рендеринга
   * @param {boolean} append - Добавить к существующим или заменить
   */
  function renderRequests(requests, append = false) {
    if (!requests || requests.length === 0) {
      if (!append) {
        listElement.innerHTML = '<div class="p-4 text-center text-secondary">Нет заявлений.</div>';
      }
      return;
    }

    let items = filterBySearch(requests);
    
    if (items.length === 0 && !append) {
      listElement.innerHTML = '<div class="p-4 text-center text-secondary">Нет заявлений.</div>';
      return;
    }

    console.log('renderRequests: rendering', {
      count: items.length,
      append,
      totalInMemory: allRequests.length
    });

    const itemsHtml = items.map(req => renderRequestCard(req)).join('');
    
    if (append) {
      // Удаляем observer target перед добавлением
      if (observerTarget && observerTarget.parentNode) {
        observerTarget.remove();
      }
      // Добавляем новые карточки
      listElement.insertAdjacentHTML('beforeend', itemsHtml);
      console.log('renderRequests: appended to DOM');
      // Возвращаем observer target обратно
      if (observerTarget) {
        listElement.appendChild(observerTarget);
      }
    } else {
      listElement.innerHTML = itemsHtml;
      console.log('renderRequests: replaced DOM');
      // Создаем observer target при первой загрузке
      if (hasMore && !observerTarget) {
        observerTarget = document.createElement('div');
        observerTarget.className = 'load-more-trigger';
        observerTarget.style.height = '1px';
        listElement.appendChild(observerTarget);
      }
    }
  }

  /**
   * Рендерит карточку заявления
   * @param {Object} req - Заявление
   * @returns {string} HTML
   */
  function renderRequestCard(req) {
    const statusBadge = getStatusBadge(req.status);
    const typeDisplay = req.type_display || req.type || 'Неизвестный тип';
    const createdAt = formatDate(req.created_at);
    const detailUrl = `/requests/${req.id}/`;
    
    return `
      <article class="card">
        <header class="card-header">
          <div class="card-icon" style="width:48px;height:48px;">
            <i class="bi-file-earmark-text"></i>
          </div>

          <div class="card-meta flex-grow-1">
            <div class="d-flex align-items-center gap-2 flex-wrap">
              <div class="card-title">${escapeHtml(typeDisplay)}</div>
              ${statusBadge}
            </div>
            <div class="card-subtitle mt-1">
              <time datetime="${req.created_at}">${createdAt}</time>
              ${req.comment ? ` • ${escapeHtml(req.comment.substring(0, 100))}${req.comment.length > 100 ? '...' : ''}` : ''}
            </div>
          </div>

          <div class="ms-auto">
            <a href="${detailUrl}" class="btn btn-outline-primary btn-sm">
              <i class="bi-eye"></i> Подробнее
            </a>
          </div>
        </header>
      </article>
    `;
  }

  /**
   * Возвращает HTML для бейджа статуса
   * @param {string} status - Статус заявления
   * @returns {string} HTML
   */
  function getStatusBadge(status) {
    const badges = {
      'pending': '<span class="badge bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle">На рассмотрении</span>',
      'approved': '<span class="badge bg-success-subtle text-success-emphasis border border-success-subtle">Одобрено</span>',
      'rejected': '<span class="badge bg-danger-subtle text-danger-emphasis border border-danger-subtle">Отклонено</span>',
      'cancelled': '<span class="badge bg-dark-subtle text-dark-emphasis border border-dark-subtle">Отменено</span>',
      'draft': '<span class="badge bg-light text-body border">Черновик</span>'
    };
    return badges[status] || '<span class="badge bg-light text-body border">Неизвестно</span>';
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
  async function setStatus(status) {
    currentStatus = status;
    hasMore = true;
    nextUrl = null;
    allRequests = [];
    const reqs = await loadRequests(false);
    renderRequests(reqs, false);
    setupInfiniteScroll();
  }
  
  /**
   * Обработчик поиска (работает только с уже загруженными заявлениями)
   */
  function handleSearch() {
    // Применяем фильтрацию ко всем загруженным заявлениям
    renderRequests(allRequests, false);
  }
  
  /**
   * Настройка обработчика поиска
   */
  function setupSearch() {
    if (!searchInput) return;
    
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchQuery = e.target.value;
      
      // Debounce: ждем 300ms после последнего ввода
      searchTimeout = setTimeout(() => {
        console.log('Search query:', searchQuery);
        handleSearch();
      }, 300);
    });
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
    const reqs = await loadRequests(false);
    renderRequests(reqs, false);
    setupInfiniteScroll();
    setupSearch();
  })();

  return {
    load: loadRequests,
    setStatus,
    destroy
  };
}

// Экспорт для совместимости
if (typeof window !== 'undefined') {
  window.initRequestListHandler = initRequestListHandler;
}

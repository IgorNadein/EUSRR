/**
 * @module requestListHandler
 * @description Загружает и отображает список заявлений через API
 */

/**
 * Инициализирует обработчик списка заявлений
 * @param {Object} options - Опции инициализации
 * @param {string} options.apiListUrl - URL API для списка заявлений
 * @param {string} options.detailUrlTemplate - Шаблон URL для детального просмотра: "/requests/{id}/"
 * @param {number} options.userId - ID текущего пользователя
 * @param {boolean} options.canProcess - Может ли пользователь обрабатывать заявления
 * @param {Object} options.headers - HTTP заголовки для запросов
 * @returns {Object} API с методами load, destroy
 */
export function initRequestListHandler(options) {
  const {
    apiListUrl,
    detailUrlTemplate,
    userId,
    canProcess,
    headers = {}
  } = options;

  const listElement = document.getElementById('requestList');
  const searchInput = document.getElementById('reqFilter');
  
  if (!listElement) {
    console.warn('initRequestListHandler: #requestList not found');
    return { load: () => {}, destroy: () => {} };
  }

  // Текущее состояние
  const urlParams = new URLSearchParams(window.location.search);
  let currentView = urlParams.get('view') || ''; // 'mine' | 'addressed' | ''
  let currentType = urlParams.get('type') || '';
  let currentStatus = urlParams.get('status') || '';
  let searchQuery = ''; // Поисковый запрос
  let allRequests = []; // Все загруженные заявления
  let loading = false;
  let hasMore = true;
  let nextUrl = null;
  let totalCount = 0;
  
  console.log('requestListHandler: init with view =', currentView, 'type =', currentType, 'status =', currentStatus);
  
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
        // Формируем URL с параметрами фильтров
        const params = new URLSearchParams();
        if (currentView === 'mine') {
          params.append('view', 'mine');
        } else if (currentView === 'addressed') {
          params.append('addressed_to_me', 'true');
        }
        if (currentType) {
          params.append('type', currentType);
        }
        if (currentStatus) {
          params.append('status', currentStatus);
        }
        
        url = `${apiListUrl}?${params}`;
        console.log('loadRequests: initial load', url);
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
      const title = (req.display_title || req.title || '').toLowerCase();
      const comment = (req.comment || '').toLowerCase();
      const employeeName = (req.employee?.full_name || '').toLowerCase();
      return title.includes(query) || comment.includes(query) || employeeName.includes(query);
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
        listElement.innerHTML = '<div class="p-4 text-center text-secondary">Нет доступных заявлений.</div>';
      }
      return;
    }

    let items = filterBySearch(requests);
    
    if (items.length === 0 && !append) {
      listElement.innerHTML = '<div class="p-4 text-center text-secondary">Нет заявлений, соответствующих фильтрам.</div>';
      return;
    }

    console.log('renderRequests: rendering', {
      count: items.length,
      append,
      totalInMemory: allRequests.length
    });

    const itemsHtml = items.map(req => renderRequestRow(req)).join('');
    
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
   * Рендерит строку заявления
   * @param {Object} req - Заявление
   * @returns {string} HTML
   */
  function renderRequestRow(req) {
    const statusClass = getStatusClass(req.status);
    const statusText = getStatusText(req.status);
    const detailUrl = detailUrlTemplate.replace('{id}', req.id);
    
    return `
      <article class="req-item" data-request-id="${req.id}">
        <header class="req-header">
          <div class="req-title-row">
            <a href="${detailUrl}" class="req-link">
              <i class="bi-file-earmark-text"></i>
              <strong>${escapeHtml(req.display_title || req.title || 'Заявление')}</strong>
            </a>
            <span class="badge badge-${statusClass}">${statusText}</span>
          </div>
          
          <div class="req-meta">
            <span class="req-employee">
              <i class="bi-person"></i> ${escapeHtml(req.employee?.full_name || 'Неизвестно')}
            </span>
            ${req.date_from ? `
              <span class="req-date">
                <i class="bi-calendar3"></i> 
                ${formatDate(req.date_from)}${req.date_to ? ' — ' + formatDate(req.date_to) : ''}
              </span>
            ` : ''}
            <span class="req-created">
              <i class="bi-clock"></i> ${formatDate(req.created_at)}
            </span>
          </div>
        </header>
        
        ${req.comment ? `
          <div class="req-comment">${escapeHtml(req.comment)}</div>
        ` : ''}
        
        <footer class="req-footer">
          ${req.approver ? `
            <div class="req-approver">
              <i class="bi-person-check"></i> 
              <span>Согласующий: ${escapeHtml(req.approver.full_name)}</span>
            </div>
          ` : ''}
          
          ${req.recipient_count > 0 ? `
            <div class="req-recipients">
              <i class="bi-people"></i> 
              <span>Получатели: ${req.recipient_count}</span>
            </div>
          ` : ''}
          
          ${req.attachment_url ? `
            <a href="${req.attachment_url}" class="btn btn-ghost btn-sm d-inline-flex align-items-center gap-1" target="_blank">
              <i class="bi-paperclip"></i><span>Вложение</span>
            </a>
          ` : ''}
        </footer>
      </article>
    `;
  }

  /**
   * Получает CSS класс для статуса
   * @param {string} status - Статус заявления
   * @returns {string} CSS класс
   */
  function getStatusClass(status) {
    const classes = {
      'pending': 'warning',
      'approved': 'success',
      'rejected': 'danger',
      'cancelled': 'secondary'
    };
    return classes[status] || 'secondary';
  }

  /**
   * Получает текст статуса
   * @param {string} status - Статус заявления
   * @returns {string} Текст статуса
   */
  function getStatusText(status) {
    const texts = {
      'pending': 'На рассмотрении',
      'approved': 'Одобрено',
      'rejected': 'Отклонено',
      'cancelled': 'Отменено'
    };
    return texts[status] || status;
  }

  /**
   * Форматирует дату
   * @param {string} dateStr - ISO дата
   * @returns {string} Отформатированная дата
   */
  function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  }

  /**
   * Экранирует HTML
   * @param {string} str - Строка
   * @returns {string} Экранированная строка
   */
  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * Публичный API для изменения фильтров
   */
  async function setView(view) {
    currentView = view;
    hasMore = true;
    nextUrl = null;
    allRequests = [];
    const reqs = await loadRequests(false);
    renderRequests(reqs, false);
    setupInfiniteScroll();
  }

  async function setType(type) {
    currentType = type;
    hasMore = true;
    nextUrl = null;
    allRequests = [];
    const reqs = await loadRequests(false);
    renderRequests(reqs, false);
    setupInfiniteScroll();
  }

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
    setupSearch(); // Настраиваем поиск после первой загрузки
  })();

  return {
    load: loadRequests,
    setView,
    setType,
    setStatus,
    destroy
  };
}

// Экспорт для совместимости
if (typeof window !== 'undefined') {
  window.initRequestListHandler = initRequestListHandler;
}

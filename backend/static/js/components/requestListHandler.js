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
    headers = {},
  } = options;

  const listElement = document.getElementById("reqListContent");
  const searchInput = document.getElementById("reqFilter");

  if (!listElement) {
    console.warn("initRequestListHandler: #reqListContent not found");
    return { load: () => {}, destroy: () => {} };
  }

  // Текущее состояние
  const urlParams = new URLSearchParams(window.location.search);
  let currentView = urlParams.get("view") || ""; // 'mine' | 'addressed' | ''
  let currentType = urlParams.get("type") || "";
  let currentStatus = urlParams.get("status") || "";
  let currentEmployeeId = urlParams.get("employee_id") || "";
  let currentDateFrom = urlParams.get("date_from") || "";
  let currentDateTo = urlParams.get("date_to") || "";
  let searchQuery = ""; // Поисковый запрос
  let allRequests = []; // Все загруженные заявления
  let loading = false;
  let hasMore = true;
  let nextUrl = null;
  let totalCount = 0;

  console.log(
    "requestListHandler: init with view =",
    currentView,
    "type =",
    currentType,
    "status =",
    currentStatus,
    "employee_id =",
    currentEmployeeId,
    "date_from =",
    currentDateFrom,
    "date_to =",
    currentDateTo
  );

  // Intersection Observer для бесконечной прокрутки
  let observerTarget = null;
  let observer = null;

  // Мобильная оптимизация: слушаем сетевые события
  let isOnline = navigator.onLine;
  window.addEventListener("online", () => {
    isOnline = true;
    console.log("Network restored");
  });
  window.addEventListener("offline", () => {
    isOnline = false;
    console.log("Network lost");
    listElement.innerHTML =
      '<div class="p-4 text-center text-warning">Потеряна связь с интернетом</div>';
  });

  /**
   * Загружает заявления с API
   * @param {boolean} append - Добавить к существующим или заменить
   * @returns {Promise<Array>} Массив новых заявлений
   */
  async function loadRequests(append = false) {
    if (loading || (append && !hasMore)) {
      console.log("loadRequests: skipped", { loading, append, hasMore });
      return [];
    }

    // Проверка сети на мобильных
    if (!isOnline) {
      console.warn("loadRequests: offline");
      listElement.innerHTML =
        '<div class="p-4 text-center text-warning">Нет интернет-соединения. Проверьте подключение.</div>';
      return [];
    }

    loading = true;
    showLoadingSpinner();

    try {
      let url;
      if (append && nextUrl) {
        url = nextUrl;
        console.log("loadRequests: using nextUrl", url);
      } else if (append && !nextUrl) {
        console.warn("loadRequests: append=true but no nextUrl, stopping");
        loading = false;
        hideLoadingSpinner();
        return [];
      } else {
        // Формируем URL с параметрами фильтров
        const params = new URLSearchParams();
        if (currentView === "mine") {
          params.append("view", "mine");
        } else if (currentView === "addressed") {
          params.append("addressed_to_me", "true");
        }
        if (currentType) {
          params.append("type", currentType);
        }
        if (currentStatus) {
          params.append("status", currentStatus);
        }
        if (currentEmployeeId) {
          params.append("employee_id", currentEmployeeId);
        }
        if (currentDateFrom) {
          params.append("date_from", currentDateFrom);
        }
        if (currentDateTo) {
          params.append("date_to", currentDateTo);
        }

        url = `${apiListUrl}?${params}`;
        console.log("loadRequests: initial load", url);
      }

      const controller = new AbortController();
      // На мобильных устройствах увеличиваем таймаут до 15 секунд
      const timeoutMs = /iPhone|iPad|Android|Mobile/.test(navigator.userAgent)
        ? 15000
        : 10000;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const response = await fetch(url, {
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      const data = await response.json();
      const newRequests = data.results || [];

      console.log("loadRequests: received", {
        newCount: newRequests.length,
        totalCount: data.count,
        hasNext: !!data.next,
        currentRequests: allRequests.length,
      });

      // Сохраняем метаданные
      totalCount = data.count || newRequests.length;
      nextUrl = data.next || null;
      hasMore = !!nextUrl;

      if (append) {
        allRequests = [...allRequests, ...newRequests];
        console.log("loadRequests: appended, total now:", allRequests.length);
      } else {
        allRequests = newRequests;
        console.log("loadRequests: replaced, total now:", allRequests.length);
      }

      loading = false;
      hideLoadingSpinner();

      return newRequests;
    } catch (error) {
      console.error("Ошибка загрузки заявлений:", error);
      loading = false;
      hideLoadingSpinner();

      // Более информативное сообщение об ошибке
      let errorMsg = "Не удалось загрузить заявления";
      if (error.name === "AbortError") {
        errorMsg = "Время ожидания истекло. Проверьте интернет-соединение.";
      } else if (!navigator.onLine) {
        errorMsg = "Нет интернет-соединения.";
      }

      listElement.innerHTML = `
        <div class="p-4 text-center">
          <div class="text-danger mb-2">${errorMsg}</div>
          <small class="text-body-secondary d-block">Попробуйте обновить страницу</small>
        </div>
      `;
      return [];
    }
  }

  /**
   * Показать спиннер загрузки
   */
  function showLoadingSpinner() {
    const existing = listElement.querySelector(".loading-spinner");
    if (existing) return;

    const spinner = document.createElement("div");
    spinner.className = "loading-spinner text-center py-4";
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
    const spinner = listElement.querySelector(".loading-spinner");
    if (spinner) {
      spinner.remove();
    }
    // Удаляем начальный спиннер из шаблона
    const initialSpinner = document.getElementById("reqListLoading");
    if (initialSpinner) {
      initialSpinner.remove();
    }
  }

  /**
   * Загрузка следующей порции заявлений
   */
  async function loadMore() {
    console.log("loadMore: triggered", {
      hasMore,
      loading,
      nextUrl,
      currentCount: allRequests.length,
    });

    try {
      const newRequests = await loadRequests(true); // append = true
      renderRequests(newRequests, true); // append = true
    } catch (error) {
      console.error("Failed to load more requests:", error);
    }
  }

  /**
   * Настройка Intersection Observer для бесконечной прокрутки
   */
  function setupInfiniteScroll() {
    if (!observerTarget) return;

    // Создаем observer с адаптивными параметрами для мобильных
    const isMobile = /iPhone|iPad|Android|Mobile/.test(navigator.userAgent);
    const rootMargin = isMobile ? "200px" : "100px"; // На мобильных загружаем раньше

    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && hasMore && !loading) {
            console.log("Intersection observer: triggering loadMore");
            loadMore();
          }
        });
      },
      {
        root: null,
        rootMargin,
        threshold: 0.01,
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
    return items.filter((req) => {
      const title = (req.display_title || req.title || "").toLowerCase();
      const comment = (req.comment || "").toLowerCase();
      const employeeName = (req.employee?.full_name || "").toLowerCase();
      return (
        title.includes(query) ||
        comment.includes(query) ||
        employeeName.includes(query)
      );
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
        listElement.innerHTML =
          '<div class="p-4 text-center text-secondary">Нет доступных заявлений.</div>';
      }
      return;
    }

    let items = filterBySearch(requests);

    if (items.length === 0 && !append) {
      listElement.innerHTML =
        '<div class="p-4 text-center text-secondary">Нет заявлений, соответствующих фильтрам.</div>';
      return;
    }

    console.log("renderRequests: rendering", {
      count: items.length,
      append,
      totalInMemory: allRequests.length,
    });

    const itemsHtml = items.map((req) => renderRequestRow(req)).join("");

    if (append) {
      // Удаляем observer target перед добавлением
      if (observerTarget && observerTarget.parentNode) {
        observerTarget.remove();
      }
      // Добавляем новые карточки
      listElement.insertAdjacentHTML("beforeend", itemsHtml);
      console.log("renderRequests: appended to DOM");
      // Возвращаем observer target обратно
      if (observerTarget) {
        listElement.appendChild(observerTarget);
      }
    } else {
      listElement.innerHTML = itemsHtml;
      console.log("renderRequests: replaced DOM");
      // Создаем observer target при первой загрузке
      if (hasMore && !observerTarget) {
        observerTarget = document.createElement("div");
        observerTarget.className = "load-more-trigger";
        observerTarget.style.height = "1px";
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
    const type = (req.type || "").toLowerCase();
    const status = (req.status || "").toLowerCase();

    // Иконка типа
    let typeIcon = "bi-clipboard-check text-secondary";
    if (type === "vacation") typeIcon = "bi-calendar-check text-primary";
    else if (type === "sick_leave") typeIcon = "bi-capsule text-danger";
    else if (type === "day_off") typeIcon = "bi-umbrella-fill text-info";
    else if (type === "transfer") typeIcon = "bi-box-arrow-right text-info";
    else if (type === "dismissal") typeIcon = "bi-door-open text-warning";

    // Текст типа
    const typeText =
      {
        vacation: "Отпуск",
        sick_leave: "Больничный",
        day_off: "Отгул",
        transfer: "Перевод",
        dismissal: "Увольнение",
        other: "Другое",
      }[type] || req.type;

    // Класс и текст статуса
    let statusBadgeClass = "text-bg-light";
    let statusText = req.status;
    if (status === "draft") {
      statusBadgeClass = "text-bg-info";
      statusText = "Черновик";
    } else if (status === "pending") {
      statusBadgeClass = "text-bg-warning";
      statusText = "На рассмотр.";
    } else if (status === "approved") {
      statusBadgeClass = "text-bg-success";
      statusText = "Одобрено";
    } else if (status === "rejected") {
      statusBadgeClass = "text-bg-danger";
      statusText = "Отклонено";
    } else if (status === "cancelled") {
      statusBadgeClass = "text-bg-secondary";
      statusText = "Отменено";
    }

    // URL для сотрудника
    const employeeUrl = `/employees/${req.employee?.id}/`;
    const employeeName =
      req.employee?.id === userId
        ? "Вы"
        : req.employee?.full_name || req.employee?.display_name || "Сотрудник";

    // Кнопки действий
    let actionButtons = "";

    // Если уже принято решение (не pending), показываем ссылку на того кто принял решение
    if (req.status !== "pending" && req.approver) {
      const approverName = req.approver.full_name || req.approver.display_name || "Пользователь";
      const approverUrl = `/employees/${req.approver.id}/`;
      let approverLabel = "";



      actionButtons = `
        <a href="${approverUrl}" class="text-decoration-none d-block">
          <span class="badge ${req.status === "approved" ? "text-bg-success" : req.status === "rejected" ? "text-bg-danger" : "text-bg-secondary"}">
            ${escapeHtml(approverName)}
          </span>
        </a>
      `;
    } else if (req.employee?.id !== userId && canProcess && req.status === "pending") {
      // Если pending и не автор и есть права - показываем кнопки действий
      actionButtons = `
        <button type="button" class="btn btn-ghost btn-sm text-success"
                data-bs-toggle="modal" data-bs-target="#reqApproveModal"
                data-id="${req.id}" title="Одобрить">
          <i class="bi-hand-thumbs-up"></i>
        </button>
        <button type="button" class="btn btn-ghost btn-sm text-danger"
                data-bs-toggle="modal" data-bs-target="#reqRejectModal"
                data-id="${req.id}" title="Отклонить">
          <i class="bi-hand-thumbs-down"></i>
        </button>
      `;
    } else if (req.employee?.id === userId) {
      // Если автор - показываем кнопки Изменить/Отменить
      actionButtons = `
        <button type="button" class="btn btn-ghost btn-sm text-primary"
                data-bs-toggle="modal" data-bs-target="#reqEditModal"
                data-id="${req.id}"
                data-title="${escapeHtml(req.title || "")}"
                data-type="${req.type || ""}"
                data-date_from="${req.date_from || ""}"
                data-date_to="${req.date_to || ""}"
                data-comment="${escapeHtml(req.comment || "")}"
                data-status="${status}" title="Изменить">
          <i class="bi-pencil"></i>
        </button>
        <button type="button" class="btn btn-ghost btn-sm text-secondary"
                data-bs-toggle="modal" data-bs-target="#reqCancelModal"
                data-id="${req.id}" title="Отменить">
          <i class="bi-slash-circle"></i>
        </button>
      `;
    }

    return `
      <article class="req-row" id="req-${req.id}">
        <div class="req-table-row">
          <!-- Иконка типа -->
          <div class="req-cell req-cell-icon">
            <div class="card-icon d-flex align-items-center justify-content-center">
              <i class="${typeIcon}"></i>
            </div>
          </div>

          <!-- Заголовок и тип -->
          <div class="req-cell req-cell-title">
            <div class="req-cell-content">
              <a href="/requests/${req.id}/" class="text-decoration-none">
                <strong>${escapeHtml(req.title || "Без заголовка")}</strong>
              </a>
              ${
                type
                  ? `<span class="badge text-bg-light ms-1">${typeText}</span>`
                  : ""
              }
              ${
                req.comment
                  ? `<div class="small text-body-secondary mt-1">${escapeHtml(
                      req.comment.substring(0, 100)
                    )}</div>`
                  : ""
              }
            </div>
          </div>

          <!-- Автор -->
          <div class="req-cell req-cell-author">
            <div class="req-cell-content">
              ${
                req.employee
                  ? `<a href="${employeeUrl}" class="text-decoration-none">${employeeName}</a>`
                  : ""
              }
            </div>
          </div>

          <!-- Период -->
          <div class="req-cell req-cell-dates">
            <div class="req-cell-content text-mono">
              ${
                req.date_from || req.date_to
                  ? `
                ${req.date_from ? formatDate(req.date_from) : "—"}<br>
                ${req.date_to ? formatDate(req.date_to) : "—"}
              `
                  : '<span class="text-body-secondary">—</span>'
              }
            </div>
          </div>

          <!-- Статус -->
          <div class="req-cell req-cell-status">
            <div class="req-cell-content">
              ${
                req.status
                  ? `<span class="badge ${statusBadgeClass}">${statusText}</span>`
                  : ""
              }
            </div>
          </div>

          <!-- Дата создания -->
          <div class="req-cell req-cell-created">
            <div class="req-cell-content small text-body-secondary">
              ${
                req.created_at
                  ? formatDate(req.created_at)
                  : '<span class="text-body-secondary">—</span>'
              }
            </div>
          </div>

          <!-- Действия -->
          <div class="req-cell req-cell-actions">
            <div class="req-cell-content">
              ${actionButtons}
            </div>
          </div>
        </div>

        <!-- Футер с комментариями -->
        <footer class="req-footer">
          <button class="btn btn-ghost btn-sm d-inline-flex align-items-center gap-1 collapsed"
                  type="button"
                  data-bs-toggle="collapse"
                  data-bs-target="#rcoll-${req.id}"
                  aria-controls="rcoll-${req.id}"
                  aria-expanded="false">
            <i class="bi-chat-dots"></i>
            <span class="txt-open" data-role="count">${
              req.comments_count || 0
            }</span>
            <span class="txt-close">Скрыть</span>
          </button>
          ${
            req.attachment_url
              ? `
            <a href="${req.attachment_url}" class="btn btn-ghost btn-sm d-inline-flex align-items-center gap-1" target="_blank">
              <i class="bi-paperclip"></i><span>Вложение</span>
            </a>
          `
              : ""
          }
        </footer>

        <div id="rcoll-${req.id}" class="collapse" data-request-id="${
      req.id
    }" data-comments-collapse>
          <div class="comments-block p-3">
            <div class="d-flex align-items-center gap-2 mb-3">
              <strong class="small mb-0">Комментарии</strong>
              <div class="spinner-border spinner-border-sm text-secondary" role="status" style="display:none;"></div>
            </div>
            <div class="comments-list" data-role="list"></div>
            <form class="comment-new mt-3 request-comment-form" data-role="form" autocomplete="off">
              <input type="hidden" name="csrfmiddlewaretoken" value="${getCsrfToken()}">
              <div class="message-field message-field--compact">
                <div class="dropdown message-emoji">
                  <button type="button" class="btn btn-ghost btn-emoji message-icon-btn"
                          data-bs-toggle="dropdown"
                          aria-expanded="false"
                          title="Вставить смайлик">
                    <i class="bi-emoji-smile"></i>
                  </button>
                  <div class="dropdown-menu dropdown-menu-start message-emoji-menu">
                    <emoji-picker data-emoji-picker class="chat-emoji-picker"></emoji-picker>
                  </div>
                </div>
                <textarea class="form-control message-input" rows="1" placeholder="Написать…" data-role="text"></textarea>
                <button class="btn btn-primary message-send" type="submit" title="Отправить"><i class="bi-send"></i></button>
              </div>
            </form>
          </div>
        </div>
      </article>
    `;
  }

  /**
   * Получает CSRF токен из cookie
   * @returns {string} CSRF токен
   */
  function getCsrfToken() {
    const name = "csrftoken";
    let cookieValue = "";
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /**
   * Получает CSS класс для статуса
   * @param {string} status - Статус заявления
   * @returns {string} CSS класс
   */
  function getStatusClass(status) {
    const classes = {
      pending: "warning",
      approved: "success",
      rejected: "danger",
      cancelled: "secondary",
    };
    return classes[status] || "secondary";
  }

  /**
   * Получает текст статуса
   * @param {string} status - Статус заявления
   * @returns {string} Текст статуса
   */
  function getStatusText(status) {
    const texts = {
      pending: "На рассмотрении",
      approved: "Одобрено",
      rejected: "Отклонено",
      cancelled: "Отменено",
    };
    return texts[status] || status;
  }

  /**
   * Форматирует дату
   * @param {string} dateStr - ISO дата
   * @returns {string} Отформатированная дата
   */
  function formatDate(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  /**
   * Экранирует HTML
   * @param {string} str - Строка
   * @returns {string} Экранированная строка
   */
  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
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
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      searchQuery = e.target.value;

      // Debounce: ждем 300ms после последнего ввода
      searchTimeout = setTimeout(() => {
        console.log("Search query:", searchQuery);
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
    destroy,
  };
}

// Экспорт для совместимости
if (typeof window !== "undefined") {
  window.initRequestListHandler = initRequestListHandler;
}

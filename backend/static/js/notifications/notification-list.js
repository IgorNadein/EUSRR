/**
 * Управление страницей списка уведомлений
 */
class NotificationListManager {
  constructor() {
    this.currentPage = 1;
    this.pageSize = 20;
    this.currentFilter = {
      category: "",
      is_read: "",
      search: "",
    };
    this.init();
  }

  init() {
    this.setupFilters();
    this.setupSearch();
    this.setupMarkAllButton();
    this.loadNotifications();
  }

  setupFilters() {
    // Фильтр по категории
    const categoryFilter = document.getElementById("categoryFilter");
    if (categoryFilter) {
      categoryFilter.addEventListener("change", (e) => {
        this.currentFilter.category = e.target.value;
        this.currentPage = 1;
        this.loadNotifications();
      });
    }

    // Фильтр по статусу прочитанности
    const statusFilter = document.getElementById("statusFilter");
    if (statusFilter) {
      statusFilter.addEventListener("change", (e) => {
        this.currentFilter.is_read = e.target.value;
        this.currentPage = 1;
        this.loadNotifications();
      });
    }
  }

  setupSearch() {
    const searchInput = document.getElementById("notificationSearch");
    const searchBtn = document.getElementById("searchBtn");

    if (searchInput && searchBtn) {
      searchBtn.addEventListener("click", () => {
        this.currentFilter.search = searchInput.value.trim();
        this.currentPage = 1;
        this.loadNotifications();
      });

      searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          this.currentFilter.search = searchInput.value.trim();
          this.currentPage = 1;
          this.loadNotifications();
        }
      });
    }
  }

  setupMarkAllButton() {
    const markAllBtn = document.getElementById("markAllReadBtn");
    if (markAllBtn) {
      markAllBtn.addEventListener("click", async () => {
        await this.markAllAsRead();
      });
    }
  }

  async loadNotifications() {
    const container = document.getElementById("notificationListContainer");
    if (!container) return;

    // Показать загрузку
    container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
            </div>
        `;

    try {
      const params = new URLSearchParams({
        page: this.currentPage,
        page_size: this.pageSize,
      });

      if (this.currentFilter.category) {
        params.append("category", this.currentFilter.category);
      }
      if (this.currentFilter.is_read !== "") {
        params.append("is_read", this.currentFilter.is_read);
      }
      if (this.currentFilter.search) {
        params.append("search", this.currentFilter.search);
      }

      const response = await fetch(`/api/v1/notifications/?${params}`, {
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      this.renderNotifications(data);
    } catch (error) {
      console.error("[NotificationList] Error loading:", error);
      container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi-exclamation-triangle"></i>
                    Ошибка загрузки уведомлений: ${error.message}
                </div>
            `;
    }
  }

  renderNotifications(data) {
    const container = document.getElementById("notificationListContainer");
    if (!container) return;

    if (!data.notifications || data.notifications.length === 0) {
      container.innerHTML = `
                <div class="text-center py-5">
                    <i class="bi-bell-slash" style="font-size: 3rem; color: #ccc;"></i>
                    <p class="text-muted mt-3">Уведомлений нет</p>
                </div>
            `;
      return;
    }

    const notificationsHtml = data.notifications
      .map((n) => this.renderNotificationCard(n))
      .join("");
    const paginationHtml = this.renderPagination(data);

    container.innerHTML = `
            <div class="row row-cols-1 g-3">
                ${notificationsHtml}
            </div>
            ${paginationHtml}
        `;

    // Добавить обработчики событий
    this.attachEventHandlers();
  }

  renderNotificationCard(notification) {
    const categoryColors = {
      communications: "primary",
      documents: "success",
      requests: "warning",
      calendar: "info",
      department: "secondary",
      profile: "dark",
      feed: "danger",
      system: "light",
    };

    const categoryIcons = {
      communications: "bi-chat-dots",
      documents: "bi-file-earmark-text",
      requests: "bi-clipboard-check",
      calendar: "bi-calendar-event",
      department: "bi-people",
      profile: "bi-person",
      feed: "bi-newspaper",
      system: "bi-gear",
    };

    const color = categoryColors[notification.category] || "secondary";
    const icon = categoryIcons[notification.category] || "bi-bell";
    const readClass = notification.is_read
      ? "notification-read"
      : "notification-unread";

    return `
            <div class="col">
                <div class="card ${readClass}" data-notification-id="${
      notification.id
    }">
                    <div class="card-body">
                        <div class="d-flex align-items-start">
                            <div class="flex-shrink-0">
                                <div class="notification-icon bg-${color} bg-opacity-10">
                                    <i class="bi ${icon} text-${color}"></i>
                                </div>
                            </div>
                            <div class="flex-grow-1 ms-3">
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <h6 class="mb-0">${this.escapeHtml(
                                      notification.title
                                    )}</h6>
                                    <small class="text-muted ms-2">${this.formatTime(
                                      notification.created_at
                                    )}</small>
                                </div>
                                <p class="mb-2 text-muted">${this.escapeHtml(
                                  notification.message
                                )}</p>
                                <div class="d-flex gap-2">
                                    ${
                                      notification.action_url
                                        ? `
                                        <a href="${
                                          notification.action_url
                                        }" class="btn btn-sm btn-outline-primary">
                                            <i class="bi-arrow-right-circle"></i> ${
                                              notification.action_text ||
                                              "Посмотреть"
                                            }
                                        </a>
                                    `
                                        : ""
                                    }
                                    ${
                                      !notification.is_read
                                        ? `
                                        <button class="btn btn-sm btn-outline-secondary mark-read-btn" data-id="${notification.id}">
                                            <i class="bi-check2"></i> Прочитано
                                        </button>
                                    `
                                        : ""
                                    }
                                    <button class="btn btn-sm btn-outline-danger delete-btn" data-id="${
                                      notification.id
                                    }">
                                        <i class="bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
  }

  renderPagination(data) {
    if (data.total <= this.pageSize) {
      return "";
    }

    const totalPages = Math.ceil(data.total / this.pageSize);
    const pages = [];

    // Всегда показываем первую страницу
    pages.push(1);

    // Показываем страницы вокруг текущей
    for (
      let i = Math.max(2, this.currentPage - 1);
      i <= Math.min(totalPages - 1, this.currentPage + 1);
      i++
    ) {
      if (!pages.includes(i)) {
        pages.push(i);
      }
    }

    // Всегда показываем последнюю страницу
    if (!pages.includes(totalPages)) {
      pages.push(totalPages);
    }

    let paginationHtml =
      '<nav class="mt-4"><ul class="pagination justify-content-center">';

    // Кнопка "Предыдущая"
    paginationHtml += `
            <li class="page-item ${this.currentPage === 1 ? "disabled" : ""}">
                <a class="page-link" href="#" data-page="${
                  this.currentPage - 1
                }">
                    <i class="bi-chevron-left"></i>
                </a>
            </li>
        `;

    // Страницы
    let prevPage = 0;
    pages.forEach((page) => {
      if (page - prevPage > 1) {
        paginationHtml +=
          '<li class="page-item disabled"><span class="page-link">...</span></li>';
      }
      paginationHtml += `
                <li class="page-item ${
                  page === this.currentPage ? "active" : ""
                }">
                    <a class="page-link" href="#" data-page="${page}">${page}</a>
                </li>
            `;
      prevPage = page;
    });

    // Кнопка "Следующая"
    paginationHtml += `
            <li class="page-item ${
              this.currentPage === totalPages ? "disabled" : ""
            }">
                <a class="page-link" href="#" data-page="${
                  this.currentPage + 1
                }">
                    <i class="bi-chevron-right"></i>
                </a>
            </li>
        `;

    paginationHtml += "</ul></nav>";

    return paginationHtml;
  }

  attachEventHandlers() {
    // Обработчики для кнопок "Прочитано"
    document.querySelectorAll(".mark-read-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        const id = btn.dataset.id;
        await this.markAsRead(id);
      });
    });

    // Обработчики для кнопок удаления
    document.querySelectorAll(".delete-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        const id = btn.dataset.id;
        if (confirm("Удалить это уведомление?")) {
          await this.deleteNotification(id);
        }
      });
    });

    // Обработчики для пагинации
    document.querySelectorAll(".pagination .page-link").forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const page = parseInt(link.dataset.page);
        if (page && page !== this.currentPage) {
          this.currentPage = page;
          this.loadNotifications();
          window.scrollTo({ top: 0, behavior: "smooth" });
        }
      });
    });
  }

  async markAsRead(id) {
    try {
      const response = await fetch(`/api/v1/notifications/${id}/read/`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
      });

      if (response.ok) {
        // Обновить карточку
        const card = document.querySelector(`[data-notification-id="${id}"]`);
        if (card) {
          card.classList.remove("notification-unread");
          card.classList.add("notification-read");
          card.querySelector(".mark-read-btn")?.remove();
        }

        // Обновить счетчик в navbar
        if (window.notificationManager) {
          const badge = document.getElementById("notificationBadge");
          if (badge) {
            const currentCount = parseInt(badge.textContent) || 0;
            if (currentCount > 0) {
              window.notificationManager.updateBadge(currentCount - 1);
            }
          }
        }
      }
    } catch (error) {
      console.error("[NotificationList] Error marking as read:", error);
      alert("Ошибка при обновлении уведомления");
    }
  }

  async markAllAsRead() {
    if (!confirm("Отметить все уведомления как прочитанные?")) {
      return;
    }

    try {
      const response = await fetch("/api/v1/notifications/read-all/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
      });

      if (response.ok) {
        // Перезагрузить список
        this.loadNotifications();

        // Обновить счетчик
        if (window.notificationManager) {
          window.notificationManager.updateBadge(0);
        }
      }
    } catch (error) {
      console.error("[NotificationList] Error marking all as read:", error);
      alert("Ошибка при обновлении уведомлений");
    }
  }

  async deleteNotification(id) {
    try {
      const response = await fetch(`/api/v1/notifications/${id}/`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": this.getCsrfToken(),
        },
      });

      if (response.ok) {
        // Удалить карточку
        const card = document
          .querySelector(`[data-notification-id="${id}"]`)
          ?.closest(".col");
        if (card) {
          card.remove();
        }

        // Если список пуст, показать заглушку
        const container = document.getElementById("notificationListContainer");
        if (container && !container.querySelector(".card")) {
          this.loadNotifications();
        }
      }
    } catch (error) {
      console.error("[NotificationList] Error deleting:", error);
      alert("Ошибка при удалении уведомления");
    }
  }

  getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  formatTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000); // секунды

    if (diff < 60) return "только что";
    if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} дн назад`;

    return date.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "short",
      year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    });
  }
}

// Инициализация при загрузке страницы
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("notificationListContainer")) {
    window.notificationListManager = new NotificationListManager();
  }
});

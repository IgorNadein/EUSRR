/**
 * LDAP Login Field Component
 * =============================================================================
 * Компонент для отображения LDAP логина с кэшированием
 * - Автоматическая загрузка при инициализации (из кэша или LDAP)
 * - Кнопка обновления для принудительного запроса из LDAP
 * - Визуальная индикация источника данных (cached/fresh)
 */

class LdapLoginField {
  constructor(fieldElement) {
    this.field = fieldElement;
    this.container = this.field.querySelector(".ldap-login-container");
    this.valueSpan = this.field.querySelector(".ldap-login-value");
    this.refreshBtn = this.field.querySelector(".ldap-refresh-btn");
    this.employeeId = this.field.dataset.employeeId;

    this.ldapLogin = null;
    this.isCached = false;

    this.init();
  }

  init() {
    if (!this.container || !this.valueSpan || !this.refreshBtn) {
      console.error("LDAP Login Field: Required elements not found", {
        field: this.field,
        container: this.container,
        valueSpan: this.valueSpan,
        refreshBtn: this.refreshBtn,
        html: this.field ? this.field.innerHTML : "field is null"
      });
      return;
    }

    // Загрузить данные при инициализации
    this.loadLdapInfo();

    // Обработчик кнопки обновления
    this.refreshBtn.addEventListener("click", () => this.refreshLdapInfo());
  }

  async loadLdapInfo(forceRefresh = false) {
    if (!this.employeeId) {
      this.showError("ID сотрудника не указан");
      return;
    }

    // Показать состояние загрузки
    this.field.classList.add("loading");
    this.valueSpan.textContent = "Загрузка...";

    try {
      const url = forceRefresh
        ? `/api/v1/employees/${this.employeeId}/ldap-info/?force_refresh=true`
        : `/api/v1/employees/${this.employeeId}/ldap-info/`;

      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error("У вас нет прав для просмотра LDAP информации");
        } else if (response.status === 404) {
          throw new Error("LDAP информация не найдена");
        } else {
          throw new Error("Ошибка загрузки LDAP информации");
        }
      }

      const data = await response.json();

      if (!data.sAMAccountName) {
        throw new Error("LDAP логин не найден");
      }

      this.ldapLogin = data.sAMAccountName;
      this.isCached = data.cached || false;
      this.showLogin(this.ldapLogin, this.isCached);
    } catch (error) {
      console.error("LDAP Login Field Error:", error);
      this.showError(error.message || "Не удалось загрузить LDAP логин");
    } finally {
      this.field.classList.remove("loading");
    }
  }

  async refreshLdapInfo() {
    await this.loadLdapInfo(true);

    // Показать уведомление об обновлении
    if (this.ldapLogin && !this.field.classList.contains("error")) {
      this.showToast("LDAP логин обновлен из Active Directory", "success");
    }
  }

  showLogin(login, cached = false) {
    this.valueSpan.textContent = login;
    this.field.classList.remove("error");

    // Визуальная индикация источника
    if (cached) {
      this.container.classList.add("cached");
      this.updateRefreshTooltip("Данные из кэша. Нажмите для обновления из AD");
    } else {
      this.container.classList.remove("cached");
      this.updateRefreshTooltip("Данные из AD. Нажмите для повторного обновления");
    }
  }

  showError(message) {
    this.valueSpan.textContent = "Ошибка";
    this.field.classList.add("error");
    this.container.classList.remove("cached");

    this.showToast(message, "error");
  }

  updateRefreshTooltip(text) {
    this.refreshBtn.setAttribute("title", text);
    if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
      const tooltip = bootstrap.Tooltip.getInstance(this.refreshBtn);
      if (tooltip) {
        tooltip.dispose();
      }
      new bootstrap.Tooltip(this.refreshBtn);
    }
  }

  showToast(message, type = "info") {
    const toastContainer =
      document.querySelector(".toast-container") || this.createToastContainer();

    const toastEl = document.createElement("div");
    toastEl.className = `toast align-items-center text-bg-${type} border-0`;
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");

    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto"
                data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    toastContainer.appendChild(toastEl);

    if (typeof bootstrap !== "undefined" && bootstrap.Toast) {
      const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 5000 });
      toast.show();

      toastEl.addEventListener("hidden.bs.toast", () => {
        toastEl.remove();
      });
    }
  }

  createToastContainer() {
    const container = document.createElement("div");
    container.className = "toast-container position-fixed top-0 end-0 p-3";
    container.style.zIndex = "1056";
    document.body.appendChild(container);
    return container;
  }
}

/**
 * Инициализация всех LDAP Login полей на странице
 */
function initLdapLoginFields() {
  const fields = document.querySelectorAll(".ldap-login-field");
  fields.forEach((field) => {
    new LdapLoginField(field);
  });
}

// Экспорт для использования в других модулях
export { LdapLoginField, initLdapLoginFields };

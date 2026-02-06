/**
 * LDAP Login Field Component
 * =============================================================================
 * Компонент для безопасного отображения LDAP логина пользователя
 * - Blur-эффект по умолчанию
 * - Раскрытие по клику (только для админов/HR)
 * - AJAX запрос к API для получения реального sAMAccountName
 */

class LdapLoginField {
  constructor(fieldElement) {
    this.field = fieldElement;
    this.button = this.field.querySelector(".ldap-login-toggle");
    this.textSpan = this.field.querySelector(".ldap-login-text");
    this.icon = this.field.querySelector(".ldap-icon");
    this.employeeId = this.field.dataset.employeeId;

    this.isRevealed = false;
    this.ldapLogin = null;

    this.init();
  }

  init() {
    if (!this.button || !this.textSpan || !this.icon) {
      console.error("LDAP Login Field: Required elements not found");
      return;
    }

    this.button.addEventListener("click", () => this.toggleReveal());
  }

  async toggleReveal() {
    if (this.isRevealed) {
      this.hide();
    } else {
      await this.reveal();
    }
  }

  async reveal() {
    if (!this.employeeId) {
      this.showError("ID сотрудника не указан");
      return;
    }

    // Уже загружено
    if (this.ldapLogin) {
      this.showLogin(this.ldapLogin);
      return;
    }

    // Показать состояние загрузки
    this.field.classList.add("loading");
    this.icon.classList.remove("bi-lock-fill");
    this.icon.classList.add("bi-hourglass");

    try {
      const response = await fetch(
        `/api/v1/employees/${this.employeeId}/ldap-info/`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
          credentials: "same-origin",
        },
      );

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
      this.showLogin(this.ldapLogin);
    } catch (error) {
      console.error("LDAP Login Field Error:", error);
      this.showError(error.message || "Не удалось загрузить LDAP логин");
    } finally {
      this.field.classList.remove("loading");
    }
  }

  showLogin(login) {
    this.textSpan.textContent = login;
    this.textSpan.classList.remove("blurred");
    this.textSpan.classList.add("revealed");

    this.icon.classList.remove("bi-lock-fill", "bi-hourglass");
    this.icon.classList.add("bi-unlock-fill");

    this.field.classList.add("revealed");
    this.isRevealed = true;

    // Обновить tooltip
    this.button.setAttribute("title", "Нажмите, чтобы скрыть LDAP логин");
    if (bootstrap && bootstrap.Tooltip) {
      const tooltip = bootstrap.Tooltip.getInstance(this.button);
      if (tooltip) {
        tooltip.dispose();
      }
    }
  }

  hide() {
    this.textSpan.textContent = "••••••••";
    this.textSpan.classList.remove("revealed");
    this.textSpan.classList.add("blurred");

    this.icon.classList.remove("bi-unlock-fill");
    this.icon.classList.add("bi-lock-fill");

    this.field.classList.remove("revealed");
    this.isRevealed = false;

    // Обновить tooltip
    this.button.setAttribute("title", "Нажмите, чтобы показать LDAP логин");
  }

  showError(message) {
    this.field.classList.add("error");
    this.icon.classList.remove("bi-lock-fill", "bi-hourglass");
    this.icon.classList.add("bi-exclamation-triangle-fill");

    // Показать сообщение об ошибке через tooltip или alert
    if (typeof bootstrap !== "undefined" && bootstrap.Toast) {
      this.showToast("Ошибка", message, "danger");
    } else {
      alert(message);
    }

    // Убрать состояние ошибки через 3 секунды
    setTimeout(() => {
      this.field.classList.remove("error");
      this.icon.classList.remove("bi-exclamation-triangle-fill");
      this.icon.classList.add("bi-lock-fill");
    }, 3000);
  }

  showToast(title, message, type = "info") {
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
                    <strong>${title}:</strong> ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

    toastContainer.appendChild(toastEl);

    const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 5000 });
    toast.show();

    toastEl.addEventListener("hidden.bs.toast", () => {
      toastEl.remove();
    });
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

// Инициализация при загрузке DOM
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initLdapLoginFields);
} else {
  initLdapLoginFields();
}

// Экспорт для использования в других модулях
export { LdapLoginField, initLdapLoginFields };

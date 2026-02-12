/**
 * @fileoverview Calendar Manage Modal - модальное окно создания/редактирования календаря
 * @module components/calendarManageModal
 */

import {
  createCalendar,
  updateCalendar,
  deleteCalendar,
} from "../api/calendarsApi.js";
import { getMyDepartments } from "../api/departmentsApi.js";

/**
 * Инициализация модального окна управления календарём
 * @param {Object} options - Параметры
 * @param {Function} options.onSuccess - Callback при успешном сохранении/удалении
 * @returns {Object} API модального окна
 */
export function initCalendarManageModal(options = {}) {
  const { onSuccess = () => {} } = options;

  const modal = document.getElementById("calendarManageModal");
  if (!modal) {
    console.warn("[CalendarManageModal] Modal element not found");
    return null;
  }

  const bsModal = new bootstrap.Modal(modal);

  // Elements
  const form = document.getElementById("calendarManageForm");
  const titleEl = document.getElementById("calendarManageModalTitle");
  const calendarIdInput = document.getElementById("calendarId");
  const titleInput = document.getElementById("calendarTitle");
  const descInput = document.getElementById("calendarDescription");
  const colorInput = document.getElementById("calendarColor");
  const colorTextInput = document.getElementById("calendarColorText");
  const iconInput = document.getElementById("calendarIcon");
  const ownerTypeInputs = document.querySelectorAll('input[name="owner_type"]');
  const visibilitySelect = document.getElementById("calendarVisibility");
  const deptSelect = document.getElementById("calendarDepartment");
  const deptSelectWrapper = document.getElementById("calendarDepartmentSelect");
  const autoSubscribeDeptWrapper = document.getElementById(
    "calendarAutoSubscribeDeptWrapper",
  );
  const defaultCanEditCheckbox = document.getElementById(
    "calendarDefaultCanEdit",
  );
  const saveBtn = document.getElementById("calendarSaveBtn");
  const deleteBtn = document.getElementById("calendarDeleteBtn");
  const errorEl = document.getElementById("calendarManageError");

  let currentCalendar = null;

  /**
   * Открыть модальное окно для создания календаря
   */
  function openForCreate() {
    currentCalendar = null;
    titleEl.textContent = "Создать календарь";
    deleteBtn.classList.add("d-none");
    resetForm();
    bsModal.show();
  }

  /**
   * Открыть модальное окно для редактирования календаря
   * @param {Object} calendar - Данные календаря
   */
  function openForEdit(calendar) {
    console.log("[CalendarManageModal] openForEdit called with:", calendar);

    currentCalendar = calendar;
    titleEl.textContent = "Редактировать календарь";
    deleteBtn.classList.remove("d-none");

    // Заполнить форму
    calendarIdInput.value = calendar.id;
    titleInput.value = calendar.title;
    descInput.value = calendar.description || "";
    colorInput.value = calendar.color || "#0d6efd";
    colorTextInput.value = calendar.color || "#0d6efd";
    iconInput.value = calendar.icon || "";
    visibilitySelect.value = calendar.visibility || "custom";

    // Определить тип владельца
    let ownerType = "personal";
    if (calendar.is_global) {
      ownerType = "global";
    } else if (calendar.is_department || calendar.owner_department) {
      ownerType = "department";
    } else if (calendar.is_personal || calendar.owner_user) {
      ownerType = "personal";
    }

    ownerTypeInputs.forEach((input) => {
      input.checked = input.value === ownerType;
    });

    // Если отдел, выбрать его
    if (calendar.owner_department) {
      deptSelect.value = calendar.owner_department;
    }

    // Настройки
    defaultCanEditCheckbox.checked = calendar.default_can_edit || false;
    document.getElementById("calendarAutoSubscribeNewUsers").checked =
      calendar.auto_subscribe_new_users || false;
    document.getElementById("calendarAutoSubscribeDept").checked =
      calendar.auto_subscribe_department_members || false;

    updateOwnerTypeVisibility();
    bsModal.show();
  }

  /**
   * Сбросить форму
   */
  function resetForm() {
    form.reset();
    calendarIdInput.value = "";
    colorInput.value = "#0d6efd";
    colorTextInput.value = "#0d6efd";
    visibilitySelect.value = "custom";
    errorEl.classList.add("d-none");
    updateOwnerTypeVisibility();
  }

  /**
   * Обновить видимость полей в зависимости от типа владельца
   */
  function updateOwnerTypeVisibility() {
    const selectedType = document.querySelector(
      'input[name="owner_type"]:checked',
    )?.value;

    if (selectedType === "department") {
      deptSelectWrapper.classList.remove("d-none");
      autoSubscribeDeptWrapper.classList.remove("d-none");
    } else {
      deptSelectWrapper.classList.add("d-none");
      autoSubscribeDeptWrapper.classList.add("d-none");
    }
  }

  /**
   * Загрузить список отделов
   */
  async function loadDepartments() {
    try {
      const departments = await getMyDepartments();

      // Заполнить select
      deptSelect.innerHTML =
        '<option value="">Выберите отдел...</option>' +
        departments
          .map((dept) => `<option value="${dept.id}">${dept.name}</option>`)
          .join("");
    } catch (error) {
      console.error("[CalendarManageModal] Failed to load departments:", error);
    }
  }

  /**
   * Собрать данные формы
   * @returns {Object}
   */
  function getFormData() {
    const data = {
      title: titleInput.value.trim(),
      description: descInput.value.trim(),
      color: colorInput.value,
      icon: iconInput.value.trim(),
      visibility: visibilitySelect.value,
      default_can_edit: defaultCanEditCheckbox.checked,
      auto_subscribe_new_users: document.getElementById(
        "calendarAutoSubscribeNewUsers",
      ).checked,
      auto_subscribe_department_members: document.getElementById(
        "calendarAutoSubscribeDept",
      ).checked,
    };

    const ownerType = document.querySelector(
      'input[name="owner_type"]:checked',
    )?.value;

    if (ownerType === "personal") {
      // owner_user будет установлен автоматически на backend
      data.owner_user = null; // Явно указываем что это личный календарь
      data.owner_department = null;
    } else if (ownerType === "department") {
      data.owner_user = null;
      data.owner_department = parseInt(deptSelect.value);

      if (!data.owner_department) {
        throw new Error("Выберите отдел");
      }
    } else if (ownerType === "global") {
      // Глобальный календарь - без владельца
      data.owner_user = null;
      data.owner_department = null;
    }

    return data;
  }

  /**
   * Сохранить календарь
   */
  async function save() {
    try {
      errorEl.classList.add("d-none");
      saveBtn.disabled = true;

      const data = getFormData();

      if (currentCalendar) {
        // Обновление
        await updateCalendar(currentCalendar.id, data);
      } else {
        // Создание
        await createCalendar(data);
      }

      bsModal.hide();
      onSuccess();
    } catch (error) {
      console.error("[CalendarManageModal] Save failed:", error);
      errorEl.textContent = error.message || "Не удалось сохранить календарь";
      errorEl.classList.remove("d-none");
    } finally {
      saveBtn.disabled = false;
    }
  }

  /**
   * Удалить календарь
   */
  async function remove() {
    if (!currentCalendar) return;

    if (
      !confirm(
        `Удалить календарь "${currentCalendar.title}"?\n\nВсе события этого календаря будут удалены.`,
      )
    ) {
      return;
    }

    try {
      deleteBtn.disabled = true;
      await deleteCalendar(currentCalendar.id);
      bsModal.hide();
      onSuccess();
    } catch (error) {
      console.error("[CalendarManageModal] Delete failed:", error);
      errorEl.textContent = error.message || "Не удалось удалить календарь";
      errorEl.classList.remove("d-none");
    } finally {
      deleteBtn.disabled = false;
    }
  }

  // Event listeners

  // Синхронизация цвета
  colorInput.addEventListener("input", (e) => {
    colorTextInput.value = e.target.value;
  });

  colorTextInput.addEventListener("input", (e) => {
    const value = e.target.value;
    if (/^#[0-9A-Fa-f]{6}$/.test(value)) {
      colorInput.value = value;
    }
  });

  // Изменение типа владельца
  ownerTypeInputs.forEach((input) => {
    input.addEventListener("change", updateOwnerTypeVisibility);
  });

  // Сохранить
  saveBtn.addEventListener("click", save);

  // Удалить
  deleteBtn.addEventListener("click", remove);

  // Сброс при закрытии
  modal.addEventListener("hidden.bs.modal", resetForm);

  // Слушать событие редактирования из других компонентов
  document.addEventListener("calendar:edit", (e) => {
    openForEdit(e.detail);
  });

  // Инициализация
  loadDepartments();

  // Public API
  return {
    openForCreate,
    openForEdit,
    show: () => bsModal.show(),
    hide: () => bsModal.hide(),
  };
}

/**
 * @fileoverview Calendar Manager Component - управление списком календарей
 * @module components/calendarManager
 */

import {
  getMyCalendars,
  invalidateCalendarsCache,
  invalidateCalendarEventsCache,
} from "../api/calendarsApi.js";
import {
  CALENDAR_TYPES,
  CALENDAR_COLORS,
  createLegacyDeptId,
} from "../constants/calendarTypes.js";
import { initCalendarEventDragDrop } from "./calendarEventDragDrop.js";

/**
 * Инициализация менеджера календарей
 * @param {Object} options - Параметры
 * @param {string} options.containerId - ID контейнера для списка календарей
 * @param {Function} options.onCalendarToggle - Callback при переключении видимости календаря
 * @param {Function} options.onCalendarsChange - Callback при изменении списка календарей
 * @returns {Object} API менеджера
 */
export function initCalendarManager(options = {}) {
  const {
    containerId = "calendarListContainer",
    onCalendarToggle = () => {},
    onCalendarsChange = () => {},
  } = options;

  const container = document.getElementById(containerId);
  if (!container) {
    console.warn(`[CalendarManager] Container #${containerId} not found`);
    return null;
  }

  // Состояние
  let calendars = [];
  let visibleCalendarIds = new Set();
  let eventCounts = new Map(); // Счётчики событий для папок: folderId -> count
  let dragDropInstance = null;

  /**
   * Создать псевдо-календари для legacy режима
   * @returns {Array} Legacy календари
   */
  function createLegacyCalendars() {
    const legacyCalendars = [
      {
        id: CALENDAR_TYPES.LEGACY_COMPANY,
        title: "Компания",
        description: "Корпоративные события",
        color: CALENDAR_COLORS.COMPANY,
        calendar_type: CALENDAR_TYPES.COMPANY,
        is_legacy: true,
        is_global: true,
        user_can_edit: false,
        user_can_view: true,
        is_subscribed: true,
      },
      {
        id: CALENDAR_TYPES.LEGACY_PERSONAL,
        title: "Личный календарь",
        description: "Мои личные события",
        color: CALENDAR_COLORS.PERSONAL,
        calendar_type: CALENDAR_TYPES.PERSONAL,
        is_legacy: true,
        is_personal: true,
        user_can_edit: true,
        user_can_view: true,
        is_subscribed: true,
      },
    ];

    // Добавить календари отделов из calendarWidget
    const deptObjects = window.calendarWidget?.getDepartments?.() || [];
    console.log("[CalendarManager] Department objects:", deptObjects);

    deptObjects.forEach((dept) => {
      const deptId = dept?.id || dept?.pk || dept?.department_id;
      if (!deptId) {
        console.warn("[CalendarManager] Department object missing ID:", dept);
        return;
      }

      legacyCalendars.push({
        id: createLegacyDeptId(deptId),
        title: dept.name || `Отдел ${deptId}`,
        description: "События отдела",
        color: CALENDAR_COLORS.DEPARTMENT,
        calendar_type: CALENDAR_TYPES.DEPARTMENT,
        department_id: parseInt(deptId, 10),
        is_legacy: true,
        is_department: true,
        user_can_edit: false,
        user_can_view: true,
        is_subscribed: true,
      });
    });

    console.log("[CalendarManager] Created legacy calendars:", legacyCalendars);
    return legacyCalendars;
  }

  /**
   * Загрузить список календарей
   */
  async function loadCalendars() {
    try {
      // Загрузить календари из django-scheduler API
      const newCalendars = await getMyCalendars();

      // Добавить legacy календари
      const legacyCalendars = createLegacyCalendars();

      // Объединить оба списка
      calendars = [...legacyCalendars, ...newCalendars];

      console.log("[CalendarManager] Loaded calendars:", {
        legacy: legacyCalendars.length,
        new: newCalendars.length,
        total: calendars.length,
        calendarIds: calendars.map((c) => ({ id: c.id, title: c.title })),
      });

      // Детальная информация о новых календарях
      console.log(
        "[CalendarManager] New calendars details:",
        newCalendars.map((c) => ({
          id: c.id,
          title: c.title,
          name: c.name,
          slug: c.slug,
        })),
      );

      // Загрузить видимость календарей из localStorage
      visibleCalendarIds = new Set();

      calendars.forEach((cal) => {
        // Используем localStorage для всех календарей
        const storageKey = `calendar_visible_${cal.id}`;
        const stored = localStorage.getItem(storageKey);
        const isVisible = stored === null ? true : stored === "true";

        if (isVisible) {
          visibleCalendarIds.add(cal.id);
        }
      });

      console.log(
        "[CalendarManager] Visible calendar IDs:",
        Array.from(visibleCalendarIds),
      );

      // Загружаем счётчики событий для папок
      await loadEventCounts();

      render();
      onCalendarsChange(calendars, Array.from(visibleCalendarIds));
    } catch (error) {
      console.error("[CalendarManager] Failed to load calendars:", error);
      container.innerHTML = `
        <div class="alert alert-danger alert-sm">
          <i class="bi-exclamation-triangle me-2"></i>
          Не удалось загрузить календари
        </div>
      `;
    }
  }

  /**
   * Загрузить счётчики событий для папок и календарей
   */
  async function loadEventCounts() {
    try {
      const { getEvents } = await import("../api/calendarsApi.js");

      // Диапазон для загрузки событий (например, 1 год назад - 1 год вперед)
      const now = new Date();
      const start = new Date(now.getFullYear() - 1, 0, 1); // 1 янв прошлого года
      const end = new Date(now.getFullYear() + 1, 11, 31); // 31 дек следующего года

      const startStr = start.toISOString().split("T")[0]; // YYYY-MM-DD
      const endStr = end.toISOString().split("T")[0];

      // Для каждой legacy папки загружаем количество событий
      const legacyFolders = calendars.filter((cal) =>
        String(cal.id).startsWith("legacy-"),
      );

      for (const folder of legacyFolders) {
        let eventsParams = { start: startStr, end: endStr };

        if (folder.id === "legacy-company") {
          // Для компании: не передаем ничего, бэкенд по умолчанию вернет company события
          // eventsParams уже содержит start/end
        } else if (folder.id === "legacy-personal") {
          // Для личного: передаем ID текущего пользователя
          const currentUserId =
            window.currentUserId || document.body.dataset.userId;
          if (currentUserId) {
            eventsParams.employee_id = parseInt(currentUserId, 10);
          }
        } else if (folder.id.startsWith("legacy-dept-")) {
          const deptId = parseInt(folder.id.replace("legacy-dept-", ""), 10);
          eventsParams.department_id = deptId;
        }

        try {
          const events = await getEvents(eventsParams);
          eventCounts.set(folder.id, events.length || 0);
        } catch (err) {
          console.warn(
            `[CalendarManager] Failed to load event count for ${folder.id}:`,
            err,
          );
          eventCounts.set(folder.id, 0);
        }
      }

      // Для настраиваемых календарей загружаем количество событий
      const customCalendars = calendars.filter(
        (cal) => !String(cal.id).startsWith("legacy-"),
      );

      for (const calendar of customCalendars) {
        try {
          const events = await getEvents({
            calendar_id: calendar.id,
            start: startStr,
            end: endStr,
          });
          eventCounts.set(calendar.id, events.length || 0);
        } catch (err) {
          console.warn(
            `[CalendarManager] Failed to load event count for calendar ${calendar.id}:`,
            err,
          );
          eventCounts.set(calendar.id, 0);
        }
      }

      console.log(
        "[CalendarManager] Event counts loaded:",
        Object.fromEntries(eventCounts),
      );
    } catch (error) {
      console.error("[CalendarManager] Failed to load event counts:", error);
    }
  }

  /**
   * Переключить видимость календаря
   * @param {string|number} calendarId
   */
  async function toggleCalendarVisibility(calendarId) {
    const isVisible = !visibleCalendarIds.has(calendarId);

    // Обновить локальное состояние
    if (isVisible) {
      visibleCalendarIds.add(calendarId);
    } else {
      visibleCalendarIds.delete(calendarId);
    }

    // Сохранить в localStorage (django-scheduler не имеет subscriptions)
    try {
      const storageKey = `calendar_visible_${calendarId}`;
      localStorage.setItem(storageKey, String(isVisible));
      console.log(
        `[CalendarManager] Saved calendar visibility to localStorage: ${calendarId} = ${isVisible}`,
      );
    } catch (error) {
      console.error("[CalendarManager] Failed to save visibility:", error);
      // Откатить изменение при ошибке
      if (isVisible) {
        visibleCalendarIds.delete(calendarId);
      } else {
        visibleCalendarIds.add(calendarId);
      }
    }

    render();
    onCalendarToggle(calendarId, visibleCalendarIds.has(calendarId));
  }

  /**
   * Подписаться на календарь (заглушка для совместимости)
   * @deprecated django-scheduler не использует subscriptions
   * @param {number} calendarId
   */
  async function subscribe(calendarId) {
    console.warn(
      "[CalendarManager] subscribe() deprecated - django-scheduler doesn't use subscriptions",
    );
    const calendar = calendars.find((c) => c.id === calendarId);
    if (calendar) {
      // Просто показываем календарь
      if (!visibleCalendarIds.has(calendarId)) {
        await toggleCalendarVisibility(calendarId);
      }
    }
  }

  /**
   * Отписаться от календаря (заглушка для совместимости)
   * @deprecated django-scheduler не использует subscriptions
   * @param {number} calendarId
   */
  async function unsubscribe(calendarId) {
    console.warn(
      "[CalendarManager] unsubscribe() deprecated - django-scheduler doesn't use subscriptions",
    );
    const calendar = calendars.find((c) => c.id === calendarId);
    if (calendar) {
      // Просто скрываем календарь
      if (visibleCalendarIds.has(calendarId)) {
        await toggleCalendarVisibility(calendarId);
      }
    }
  }

  /**
   * Преобразовать legacy календарь в настраиваемый Calendar
   * @param {string} legacyId - например "legacy-company", "legacy-personal", "legacy-dept-4"
   */
  async function convertLegacyToCalendar(legacyId) {
    // Находим legacy календарь
    const legacyCalendar = calendars.find((cal) => cal.id === legacyId);
    if (!legacyCalendar) {
      alert("Календарь не найден");
      return;
    }

    const confirmMessage = `Преобразовать "${legacyCalendar.title}" в настраиваемый календарь?\n\nВсе события будут перенесены в новый календарь.`;
    if (!confirm(confirmMessage)) return;

    try {
      // Определяем параметры нового календаря на основе legacy ID
      let calendarData = {
        title: legacyCalendar.title,
        description: `Преобразован из системного календаря`,
        color: legacyCalendar.color,
        visibility: "public",
      };

      if (legacyId === "legacy-company") {
        calendarData.visibility = "public";
      } else if (legacyId === "legacy-personal") {
        calendarData.visibility = "private";
      } else if (legacyId.startsWith("legacy-dept-")) {
        const deptId = legacyId.replace("legacy-dept-", "");
        calendarData.owner_department = parseInt(deptId, 10);
        calendarData.visibility = "department";
      }

      console.log("[CalendarManager] Creating new calendar:", calendarData);

      // Создаём новый Calendar
      const { createCalendar } = await import("../api/calendarsApi.js");
      const newCalendar = await createCalendar(calendarData);

      console.log("[CalendarManager] New calendar created:", newCalendar);

      // Получаем все события из legacy календаря
      const { getEvents } = await import("../api/calendarsApi.js");
      let eventsParams = {};

      if (legacyId === "legacy-personal") {
        eventsParams.employee_id = "me"; // Личные события
      } else if (legacyId.startsWith("legacy-dept-")) {
        const deptId = legacyId.replace("legacy-dept-", "");
        eventsParams.department_id = parseInt(deptId, 10);
      } else if (legacyId === "legacy-company") {
        // Компания - события без department и employee
        eventsParams.scope = "company";
      }

      console.log(
        "[CalendarManager] Fetching events with params:",
        eventsParams,
      );
      const events = await getEvents(eventsParams);
      console.log(`[CalendarManager] Found ${events.length} events to migrate`);

      if (events.length === 0) {
        alert(
          `Календарь "${legacyCalendar.title}" преобразован.\n\nСобытий для переноса не найдено.`,
        );
        await loadCalendars();
        return;
      }

      // Переносим события (обновляем поле calendar)
      const { updateEvent } = await import("../api/calendarsApi.js");
      let migratedCount = 0;
      let failedCount = 0;

      for (const event of events) {
        try {
          await updateEvent(event.id, { calendar: newCalendar.id });
          migratedCount++;
        } catch (err) {
          console.error(
            `[CalendarManager] Failed to migrate event ${event.id}:`,
            err,
          );
          failedCount++;
        }
      }

      console.log(
        `[CalendarManager] Migration complete: ${migratedCount} success, ${failedCount} failed`,
      );

      alert(
        `Календарь "${legacyCalendar.title}" преобразован!\n\nПеренесено событий: ${migratedCount}\nОшибок: ${failedCount}`,
      );

      // Перезагружаем список календарей и события
      await loadCalendars();
      if (typeof window.calendarWidget?.refetchEvents === "function") {
        window.calendarWidget.refetchEvents();
      }
    } catch (error) {
      console.error("[CalendarManager] Conversion failed:", error);
      alert(`Ошибка преобразования:\n${error.message || error}`);
    }
  }

  /**
   * Создать календарь внутри папки
   * @param {string} folderId - ID папки (legacy календаря)
   */
  async function createCalendarInFolder(folderId) {
    // Определяем параметры на основе папки
    let calendarData = {
      title: "",
      description: "",
      color: "#0d6efd",
      visibility: "public",
    };

    if (folderId === "legacy-company") {
      // Глобальный календарь: НЕ указываем owner_user и owner_department
      calendarData.visibility = "public";
      calendarData.title = prompt(
        "Название календаря (глобальный):",
        "Новый календарь",
      );
    } else if (folderId === "legacy-personal") {
      // Личный календарь: указываем owner_user = текущий пользователь
      const currentUserId =
        window.currentUserId || document.body.dataset.userId;
      if (!currentUserId) {
        alert("Не удалось определить текущего пользователя");
        return;
      }
      calendarData.owner_user = parseInt(currentUserId, 10);
      calendarData.visibility = "private";
      calendarData.title = prompt(
        "Название личного календаря:",
        "Мой календарь",
      );
    } else if (folderId.startsWith("legacy-dept-")) {
      // Календарь отдела: указываем owner_department
      const deptId = parseInt(folderId.replace("legacy-dept-", ""), 10);
      calendarData.owner_department = deptId;
      calendarData.visibility = "department";
      calendarData.title = prompt(
        "Название календаря отдела:",
        "Календарь отдела",
      );
      console.log("[CalendarManager] Creating department calendar:", {
        owner_department: deptId,
        visibility: "department",
        title: calendarData.title,
      });
    }

    if (!calendarData.title) {
      return; // Пользователь отменил
    }

    try {
      const { createCalendar } = await import("../api/calendarsApi.js");
      console.log(
        "[CalendarManager] Creating calendar with data:",
        calendarData,
      );
      const newCalendar = await createCalendar(calendarData);

      console.log("[CalendarManager] Calendar created in folder:", newCalendar);
      alert(`Календарь "${newCalendar.title}" создан!`);

      await loadCalendars();
    } catch (error) {
      console.error("[CalendarManager] Failed to create calendar:", error);
      alert(`Ошибка создания календаря:\n${error.message || error}`);
    }
  }

  /**
   * Получить иконку для типа календаря
   * @param {Object} calendar
   * @returns {string} HTML иконки
   */
  function getCalendarIcon(calendar) {
    if (calendar.is_personal) {
      return '<i class="bi-person-fill"></i>';
    } else if (calendar.is_department) {
      return '<i class="bi-building"></i>';
    } else if (calendar.is_global) {
      return '<i class="bi-globe"></i>';
    }
    return '<i class="bi-calendar3"></i>';
  }

  /**
   * Получить бейдж владельца
   * @param {Object} calendar
   * @returns {string} HTML бейджа
   */
  function getOwnerBadge(calendar) {
    if (calendar.is_personal && calendar.owner_user_name) {
      return `<span class="badge bg-secondary-subtle text-secondary-emphasis rounded-pill ms-auto">${calendar.owner_user_name}</span>`;
    } else if (calendar.is_department && calendar.owner_department_name) {
      return `<span class="badge bg-info-subtle text-info-emphasis rounded-pill ms-auto">${calendar.owner_department_name}</span>`;
    } else if (calendar.is_global) {
      return `<span class="badge bg-primary-subtle text-primary-emphasis rounded-pill ms-auto">Общий</span>`;
    }
    return "";
  }

  /**
   * Рендер списка календарей
   */
  function render() {
    if (calendars.length === 0) {
      container.innerHTML = `
        <div class="text-muted text-center py-3">
          <i class="bi-calendar3 fs-4 d-block mb-2"></i>
          <small>Нет доступных календарей</small>
        </div>
      `;
      return;
    }

    // Разделяем календари на legacy (папки) и настраиваемые (календари)
    const legacyFolders = calendars.filter((cal) =>
      String(cal.id).startsWith("legacy-"),
    );
    const customCalendars = calendars.filter(
      (cal) => !String(cal.id).startsWith("legacy-"),
    );

    /**
     * Генерация HTML для папки (legacy календарь)
     */
    const renderFolder = (folder) => {
      const isVisible = visibleCalendarIds.has(folder.id);
      const folderId = folder.id;

      // Определяем дочерние календари для этой папки
      let childCalendars = [];

      if (folderId === "legacy-company") {
        // Под папкой "Компания" - глобальные календари (без owner)
        childCalendars = customCalendars.filter(
          (cal) =>
            cal.is_global && !cal.owner_user_id && !cal.owner_department_id,
        );
        console.log(
          `[CalendarManager] Folder "${folderId}": ${childCalendars.length} global calendars`,
          customCalendars.map((c) => ({
            id: c.id,
            title: c.title,
            is_global: c.is_global,
            owner_user_id: c.owner_user_id,
            owner_department_id: c.owner_department_id,
          })),
        );
      } else if (folderId === "legacy-personal") {
        // Под папкой "Личный" - личные календари текущего пользователя
        childCalendars = customCalendars.filter((cal) => cal.is_personal);
        console.log(
          `[CalendarManager] Folder "${folderId}": ${childCalendars.length} personal calendars`,
          customCalendars.map((c) => ({
            id: c.id,
            title: c.title,
            is_personal: c.is_personal,
            owner_user_id: c.owner_user_id,
          })),
        );
      } else if (folderId.startsWith("legacy-dept-")) {
        // Под папкой отдела - календари этого отдела
        const deptId = parseInt(folderId.replace("legacy-dept-", ""), 10);

        console.log(
          `[CalendarManager] Filtering for dept ${deptId}:`,
          customCalendars.map((c) => ({
            id: c.id,
            title: c.title,
            is_department: c.is_department,
            owner_department_id: c.owner_department_id,
            matches: c.owner_department_id === deptId,
            comparison: `${c.owner_department_id} === ${deptId}`,
          })),
        );

        childCalendars = customCalendars.filter(
          (cal) => cal.owner_department_id === deptId,
        );
        console.log(
          `[CalendarManager] Folder "${folderId}": ${childCalendars.length} department calendars for dept ${deptId}`,
          customCalendars.map((c) => ({
            id: c.id,
            title: c.title,
            is_department: c.is_department,
            owner_department_id: c.owner_department_id,
          })),
        );
      }

      const childrenHtml = childCalendars
        .map((cal) => renderChildCalendar(cal))
        .join("");

      // Получаем количество событий из кеша
      const eventCount = eventCounts.get(folderId) || 0;

      return `
        <div class="calendar-folder" data-folder-id="${folderId}">
          <div class="calendar-folder-header">
            <div class="form-check">
              <input
                class="form-check-input calendar-visibility-toggle"
                type="checkbox"
                id="cal_${folderId}"
                ${isVisible ? "checked" : ""}
                data-calendar-id="${folderId}"
              >
              <label class="form-check-label d-flex align-items-center gap-2 w-100" for="cal_${folderId}">
                <i class="bi-folder2-open text-warning fs-5"></i>
                <span class="calendar-title fw-semibold flex-grow-1">${folder.title}</span>
                <span class="badge bg-info-subtle text-info rounded-pill" title="Событий в папке">${eventCount}</span>
              </label>
            </div>
            <div class="calendar-folder-actions">
              <button
                class="btn btn-sm btn-outline-success calendar-create-child-btn"
                data-folder-id="${folderId}"
                title="Создать календарь в папке"
              >
                <i class="bi-plus-lg"></i>
              </button>
            </div>
          </div>
          ${
            childrenHtml
              ? `<div class="calendar-folder-children">${childrenHtml}</div>`
              : `<div class="calendar-folder-empty text-muted small ps-5">Нет календарей в папке</div>`
          }
        </div>
      `;
    };

    /**
     * Генерация HTML для календаря внутри папки
     */
    const renderChildCalendar = (calendar) => {
      const isVisible = visibleCalendarIds.has(calendar.id);
      const canEdit = calendar.user_can_edit;
      const isSubscribed = calendar.is_subscribed;
      const eventCount = eventCounts.get(calendar.id) || 0;

      return `
        <div class="calendar-list-item calendar-list-item--child" data-calendar-id="${calendar.id}">
          <div class="form-check">
            <input
              class="form-check-input calendar-visibility-toggle"
              type="checkbox"
              id="cal_${calendar.id}"
              ${isVisible ? "checked" : ""}
              data-calendar-id="${calendar.id}"
            >
            <label class="form-check-label d-flex align-items-center gap-2 w-100" for="cal_${calendar.id}">
              <span class="calendar-color-indicator" style="background-color: ${calendar.color}"></span>
              <i class="bi-calendar3 text-muted"></i>
              <span class="calendar-title flex-grow-1">${calendar.title}</span>
              <span class="badge bg-secondary-subtle text-secondary rounded-pill" title="Событий">${eventCount}</span>
            </label>
          </div>

          <div class="calendar-list-item-actions">
            ${
              canEdit
                ? `
              <button
                class="btn btn-sm btn-outline-secondary calendar-edit-btn"
                data-calendar-id="${calendar.id}"
                title="Редактировать"
              >
                <i class="bi-pencil"></i>
              </button>
            `
                : ""
            }

            ${
              !isSubscribed
                ? `
              <button
                class="btn btn-sm btn-outline-primary calendar-subscribe-btn"
                data-calendar-id="${calendar.id}"
                title="Подписаться"
              >
                <i class="bi-plus-lg"></i>
              </button>
            `
                : `
              <button
                class="btn btn-sm btn-outline-danger calendar-unsubscribe-btn"
                data-calendar-id="${calendar.id}"
                title="Отписаться"
              >
                <i class="bi-dash-lg"></i>
              </button>
            `
            }
          </div>
        </div>
      `;
    };

    // Собираем HTML: каждая legacy папка + её дочерние календари
    const html = legacyFolders.map(renderFolder).join("");

    container.innerHTML = html;
    attachEventListeners();
  }

  /**
   * Прикрепить обработчики событий
   */
  function attachEventListeners() {
    // Переключение видимости
    container
      .querySelectorAll(".calendar-visibility-toggle")
      .forEach((checkbox) => {
        checkbox.addEventListener("change", (e) => {
          // НЕ парсим ID - он может быть строкой (legacy) или числом (новые календари)
          const calendarId = e.target.dataset.calendarId;
          // Конвертируем в число ТОЛЬКО если это число
          const id = /^\d+$/.test(calendarId)
            ? parseInt(calendarId, 10)
            : calendarId;
          toggleCalendarVisibility(id);
        });
      });

    // Создание календаря в папке
    container.querySelectorAll(".calendar-create-child-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const folderId = e.currentTarget.dataset.folderId;
        createCalendarInFolder(folderId);
      });
    });

    // Преобразование legacy календаря в настраиваемый
    container.querySelectorAll(".calendar-convert-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const calendarId = e.currentTarget.dataset.calendarId;
        convertLegacyToCalendar(calendarId);
      });
    });

    // Подписка (только для новых календарей с числовым ID)
    container.querySelectorAll(".calendar-subscribe-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const calendarId = parseInt(e.currentTarget.dataset.calendarId, 10);
        if (!isNaN(calendarId)) {
          subscribe(calendarId);
        }
      });
    });

    // Отписка (только для новых календарей с числовым ID)
    container.querySelectorAll(".calendar-unsubscribe-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const calendarId = parseInt(e.currentTarget.dataset.calendarId, 10);
        if (!isNaN(calendarId)) {
          unsubscribe(calendarId);
        }
      });
    });

    // Редактирование (делегируем наверх)
    container.querySelectorAll(".calendar-edit-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const calendarId = parseInt(e.currentTarget.dataset.calendarId, 10);
        const calendar = calendars.find((c) => c.id === calendarId);
        if (calendar) {
          // Dispatch custom event для открытия модального окна
          document.dispatchEvent(
            new CustomEvent("calendar:edit", { detail: calendar }),
          );
        }
      });
    });
  }

  /**
   * Обновить список календарей
   */
  async function refresh() {
    invalidateCalendarsCache();
    invalidateCalendarEventsCache(); // Инвалидируем кеш событий после перемещения
    await loadCalendars();
  }

  /**
   * Получить ID видимых календарей
   * @returns {Array<number>}
   */
  function getVisibleCalendarIds() {
    return Array.from(visibleCalendarIds);
  }

  /**
   * Установить видимость календарей
   * @param {Array<number>} calendarIds
   */
  function setVisibleCalendars(calendarIds) {
    visibleCalendarIds = new Set(calendarIds);
    render();
    onCalendarsChange(calendars, Array.from(visibleCalendarIds));
  }

  // Инициализация
  loadCalendars();

  // Инициализация drag & drop
  dragDropInstance = initCalendarEventDragDrop({
    onEventMoved: () => {
      refresh();
      onCalendarsChange(calendars, Array.from(visibleCalendarIds));
    },
  });

  // Public API
  return {
    refresh,
    getVisibleCalendarIds,
    setVisibleCalendars,
    loadCalendars,
  };
}

/**
 * @fileoverview Calendar Widget Integration - связывает calendarManager с calendarWidget
 * @module components/calendarWidgetIntegration
 */

import { initCalendarManager } from "./calendarManager.js";
import { initCalendarManageModal } from "./calendarManageModal.js";
import { getCalendarEvents } from "../api/calendarApi.js";

// Глобальное хранилище интеграции
let globalIntegration = null;

/**
 * Расширенная инициализация виджета календаря с поддержкой множественных календарей
 * @param {Object} calendarWidgetInstance - Экземпляр calendarWidget
 * @param {Object} options - Опции
 * @returns {Object} Расширенный API
 */
export function integrateCalendarManager(calendarWidgetInstance, options = {}) {
  if (!calendarWidgetInstance) {
    console.warn("[CalendarIntegration] calendarWidget instance not provided");
    return null;
  }

  let visibleCalendarIds = [];
  let calendars = [];

  /**
   * Загрузить события с учётом выбранных календарей
   * @param {Date} start - Начало периода
   * @param {Date} end - Конец периода
   * @returns {Promise<Array>} События
   */
  async function fetchEventsForVisibleCalendars(start, end) {
    const startStr = formatDate(start);
    const endStr = formatDate(end);

    console.log(
      "[CalendarIntegration] Fetching events for visible calendars:",
      {
        visibleCount: visibleCalendarIds.length,
        totalCalendars: calendars.length,
        range: `${startStr} - ${endStr}`,
      },
    );

    // Если ни один календарь не выбран, показываем пустой результат
    if (visibleCalendarIds.length === 0) {
      console.log("[CalendarIntegration] No calendars selected, showing empty");
      return [];
    }

    // Разделяем legacy и новые календари
    const legacyIds = [...visibleCalendarIds].filter(
      (id) => typeof id === "string" && id.startsWith("legacy-"),
    );
    const newIds = [...visibleCalendarIds].filter(
      (id) => typeof id === "number",
    );

    console.log("[CalendarIntegration] Processing calendars:", {
      legacyIds,
      newIds,
    });

    let allEvents = [];

    // Получаем ID текущего пользователя из meta тега
    const userMeta = document.querySelector('meta[name="user-id"]');
    const currentEmployeeId = userMeta ? parseInt(userMeta.content, 10) : null;

    // Загружаем события для legacy календарей
    for (const legacyId of legacyIds) {
      try {
        let events = [];
        const calendar = calendars.find((c) => c.id === legacyId);

        if (legacyId === "legacy-company") {
          // Компания: все события без фильтров
          console.log("[CalendarIntegration] Loading company events (all)");
          events = await getCalendarEvents({ start: startStr, end: endStr });
        } else if (legacyId === "legacy-personal") {
          // Личный: события текущего сотрудника
          if (!currentEmployeeId) {
            console.warn("[CalendarIntegration] Cannot load personal events: currentEmployeeId not found");
            continue;
          }
          console.log(
            `[CalendarIntegration] Loading personal events for employee ${currentEmployeeId}`,
          );
          events = await getCalendarEvents({
            start: startStr,
            end: endStr,
            employee_id: currentEmployeeId,
          });
        } else if (legacyId.startsWith("legacy-dept-")) {
          // Отдел: события конкретного отдела
          const deptId = parseInt(legacyId.replace("legacy-dept-", ""), 10);
          console.log(
            `[CalendarIntegration] Loading department events for dept ${deptId}`,
          );
          events = await getCalendarEvents({
            start: startStr,
            end: endStr,
            department_id: deptId,
          });
        }

        // Добавляем информацию о legacy календаре (БЕЗ изменения цвета события)
        allEvents.push(
          ...(events || []).map((event) => ({
            ...event,
            __calendar: calendar,
          })),
        );

        console.log(
          `[CalendarIntegration] Loaded ${events?.length || 0} events for legacy calendar ${legacyId}`,
        );
      } catch (error) {
        console.error(
          `[CalendarIntegration] Error loading legacy calendar ${legacyId}:`,
          error,
        );
      }
    }

    // Загружаем события для новых календарей
    const newEventChunks = await Promise.all(
      newIds.map(async (calendarId) => {
        try {
          const events = await getCalendarEvents({
            start: startStr,
            end: endStr,
            calendar_id: calendarId,
          });

          console.log(
            `[CalendarIntegration] Loaded ${events?.length || 0} events for new calendar ${calendarId}`,
          );

          // Добавляем информацию о календаре (БЕЗ изменения цвета события)
          const calendar = calendars.find((c) => c.id === calendarId);
          return (events || []).map((event) => ({
            ...event,
            __calendar: calendar,
          }));
        } catch (error) {
          console.error(
            `[CalendarIntegration] Failed to load events for calendar ${calendarId}:`,
            error,
          );
          return [];
        }
      }),
    );

    // Объединяем события из новых календарей
    allEvents.push(...newEventChunks.flat());

    console.log(
      `[CalendarIntegration] Total events loaded: ${allEvents.length}`,
    );

    // Дедупликация по ID
    const seen = new Set();
    const uniqueEvents = allEvents.filter((event) => {
      const id = event.id || event.pk;
      if (!id || seen.has(id)) return false;
      seen.add(id);
      return true;
    });

    console.log(
      `[CalendarIntegration] Unique events after dedup: ${uniqueEvents.length}`,
    );
    return uniqueEvents;
  }

  /**
   * Форматировать дату в YYYY-MM-DD
   * @param {Date} date
   * @returns {string}
   */
  function formatDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  /**
   * Обработчик переключения видимости календаря
   * @param {number} calendarId
   * @param {boolean} isVisible
   */
  function handleCalendarToggle(calendarId, isVisible) {
    console.log(
      `[CalendarIntegration] Calendar ${calendarId} visibility: ${isVisible}`,
    );

    // Обновляем список видимых календарей
    if (isVisible) {
      if (!visibleCalendarIds.includes(calendarId)) {
        visibleCalendarIds.push(calendarId);
      }
    } else {
      visibleCalendarIds = visibleCalendarIds.filter((id) => id !== calendarId);
    }

    // Перезагружаем события
    if (calendarWidgetInstance.refetchEvents) {
      calendarWidgetInstance.refetchEvents();
    }
  }

  /**
   * Обработчик изменения списка календарей
   * @param {Array} newCalendars
   * @param {Array} newVisibleIds
   */
  function handleCalendarsChange(newCalendars, newVisibleIds) {
    console.log(`[CalendarIntegration] Calendars updated:`, {
      total: newCalendars.length,
      visible: newVisibleIds.length,
    });

    calendars = newCalendars;
    visibleCalendarIds = newVisibleIds;

    // Перезагружаем события
    if (calendarWidgetInstance.refetchEvents) {
      calendarWidgetInstance.refetchEvents();
    }
  }

  /**
   * Обработчик успешного сохранения календаря
   */
  function handleModalSuccess() {
    console.log("[CalendarIntegration] Calendar saved, refreshing list");

    // Обновляем список календарей
    if (calendarManagerInstance) {
      calendarManagerInstance.refresh();
    }
  }

  // Инициализация менеджера календарей
  const calendarManagerInstance = initCalendarManager({
    containerId: "calendarListContainer",
    onCalendarToggle: handleCalendarToggle,
    onCalendarsChange: handleCalendarsChange,
  });

  // Инициализация модального окна управления
  const manageModalInstance = initCalendarManageModal({
    onSuccess: handleModalSuccess,
  });

  // Привязываем кнопку создания календаря к модальному окну
  const createCalendarBtn = document.querySelector(
    '[data-action="create-calendar"]',
  );
  if (createCalendarBtn && manageModalInstance) {
    createCalendarBtn.addEventListener("click", () => {
      manageModalInstance.openForCreate();
    });
  }

  // Обрабатываем событие редактирования календаря из списка
  if (manageModalInstance) {
    document.addEventListener("calendar:edit", (e) => {
      const calendar = e.detail;
      console.log("[CalendarIntegration] Edit calendar requested:", calendar);
      manageModalInstance.openForEdit(calendar.id);
    });
  }

  // Создаём объект интеграции
  const integration = {
    /**
     * Получить события для видимых календарей
     */
    fetchEventsForVisibleCalendars,

    /**
     * Получить ID видимых календарей
     */
    getVisibleCalendarIds: () => [...visibleCalendarIds],

    /**
     * Получить все календари
     */
    getCalendars: () => [...calendars],

    /**
     * Установить видимые календари
     */
    setVisibleCalendars: (ids) => {
      if (calendarManagerInstance) {
        calendarManagerInstance.setVisibleCalendars(ids);
      }
    },

    /**
     * Обновить список календарей
     */
    refresh: () => {
      if (calendarManagerInstance) {
        return calendarManagerInstance.refresh();
      }
    },

    /**
     * Получить экземпляры компонентов
     */
    instances: {
      manager: calendarManagerInstance,
      modal: manageModalInstance,
      widget: calendarWidgetInstance,
    },
  };

  // Сохраняем глобально для доступа из других модулей
  globalIntegration = integration;

  return integration;
}

/**
 * Получить глобальный экземпляр интеграции
 * @returns {Object|null}
 */
export function getCalendarIntegration() {
  return globalIntegration;
}

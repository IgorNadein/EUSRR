/**
 * @fileoverview Calendar Widget Integration - связывает calendarManager с calendarWidget
 * @module components/calendarWidgetIntegration
 */

import { initCalendarManager } from "./calendarManager.js";
import { initCalendarManageModal } from "./calendarManageModal.js";
import { getCalendarEvents } from "../api/calendarApi.js";
import { formatDate } from "../utils/dateUtils.js";
import { resolveCalendarParams } from "../utils/calendarTypeResolver.js";

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

    let allEvents = [];

    // Загружаем события для каждого выбранного календаря
    for (const calendarId of visibleCalendarIds) {
      try {
        const calendar = calendars.find((c) => c.id === calendarId);
        
        // Используем утилиту для определения параметров запроса
        const params = resolveCalendarParams(calendarId, {
          start: startStr,
          end: endStr,
        });

        console.log(
          `[CalendarIntegration] Loading events for calendar ${calendarId}:`,
          params
        );

        const events = await getCalendarEvents(params);

        // Добавляем информацию о календаре к событиям
        allEvents.push(
          ...(events || []).map((event) => ({
            ...event,
            __calendar: calendar,
          }))
        );

        console.log(
          `[CalendarIntegration] Loaded ${events?.length || 0} events for calendar ${calendarId}`
        );
      } catch (error) {
        console.error(
          `[CalendarIntegration] Error loading calendar ${calendarId}:`,
          error
        );
      }
    }

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

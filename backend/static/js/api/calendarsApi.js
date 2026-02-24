/**
 * @fileoverview Calendars API - работа с календарями (CRUD + подписки)
 * @module api/calendarsApi
 */

import { dataManager } from "../managers/dataManager.js";
import { authHeaders, getCsrfToken } from "../utils/authUtils.js";
import { API_URLS, API_DEFAULTS } from "../constants/apiUrls.js";

/**
 * Получить список доступных календарей текущего пользователя
 * @param {number} [ttl] - Time to live кеша в мс
 * @returns {Promise<Array>} Массив календарей
 */
export async function getMyCalendars(ttl = API_DEFAULTS.TTL.CALENDARS) {
  const key = "calendars:my";

  return dataManager.fetch(
    key,
    async () => {
      // ИСПРАВЛЕНО: используем специальный endpoint my-calendars
      const url = new URL(API_URLS.CALENDARS_MY, window.location.origin);

      const response = await fetch(url.toString(), {
        headers: authHeaders(false),
      });

      if (response.status === 401) {
        console.warn("[CalendarsAPI] 401 Unauthorized");
        return [];
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // my-calendars возвращает массив напрямую, не в data.results
      const data = await response.json();
      return Array.isArray(data) ? data : data.results || [];
    },
    ttl,
  );
}

/**
 * Получить календарь по ID
 * @param {number} calendarId - ID календаря
 * @param {number} [ttl] - Time to live кеша в мс
 * @returns {Promise<Object>} Календарь
 */
export async function getCalendar(
  calendarId,
  ttl = API_DEFAULTS.TTL.CALENDARS,
) {
  const key = `calendars:${calendarId}`;

  return dataManager.fetch(
    key,
    async () => {
      const url = new URL(
        API_URLS.CALENDAR_DETAIL(calendarId),
        window.location.origin,
      );

      const response = await fetch(url.toString(), {
        headers: authHeaders(false),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return response.json();
    },
    ttl,
  );
}

/**
 * Создать новый календарь
 * @param {Object} calendarData - Данные календаря
 * @param {string} calendarData.title - Название
 * @param {string} [calendarData.description] - Описание
 * @param {string} [calendarData.color] - Цвет (#RRGGBB)
 * @param {string} [calendarData.icon] - Иконка
 * @param {string} [calendarData.visibility] - Видимость (public/private/department/custom)
 * @param {number} [calendarData.owner_user] - ID владельца-пользователя
 * @param {number} [calendarData.owner_department] - ID владельца-отдела
 * @returns {Promise<Object>} Созданный календарь
 */
export async function createCalendar(calendarData) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(API_URLS.CALENDARS, window.location.origin);

  const response = await fetch(url.toString(), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(calendarData),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Инвалидируем кеш списка календарей
  dataManager.invalidate("calendars:my");

  return response.json();
}

/**
 * Обновить календарь
 * @param {number} calendarId - ID календаря
 * @param {Object} updates - Обновления
 * @returns {Promise<Object>} Обновленный календарь
 */
export async function updateCalendar(calendarId, updates) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(
    API_URLS.CALENDAR_DETAIL(calendarId),
    window.location.origin,
  );

  const response = await fetch(url.toString(), {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Инвалидируем кеш
  dataManager.invalidate(`calendars:${calendarId}`);
  dataManager.invalidate("calendars:my");

  return response.json();
}

/**
 * Удалить календарь
 * @param {number} calendarId - ID календаря
 * @returns {Promise<void>}
 */
export async function deleteCalendar(calendarId) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(
    API_URLS.CALENDAR_DETAIL(calendarId),
    window.location.origin,
  );

  const response = await fetch(url.toString(), {
    method: "DELETE",
    headers: authHeaders(false),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Инвалидируем кеш
  dataManager.invalidate(`calendars:${calendarId}`);
  dataManager.invalidate("calendars:my");
}

// ──────────────────────────────────────────────────────────────
// ПРИМЕЧАНИЕ: Функции subscriptions, invite удалены
// Django-scheduler не имеет концепции "подписок"
// Видимость календарей управляется через localStorage
// ──────────────────────────────────────────────────────────────

// ──────────────────────────────────────────────────────────────
// Events API
// ──────────────────────────────────────────────────────────────

/**
 * Получить список событий
 * @param {Object} params - Параметры фильтрации
 * @param {string} [params.start] - Дата начала (YYYY-MM-DD)
 * @param {string} [params.end] - Дата окончания (YYYY-MM-DD)
 * @param {number} [params.department_id] - ID отдела
 * @param {string|number} [params.employee_id] - ID сотрудника или "me"
 * @param {number} [params.calendar] - ID календаря
 * @param {string} [params.scope] - Область ("company", "department", "personal")
 * @returns {Promise<Array>} Массив событий
 */
export async function getEvents(params = {}) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(API_URLS.EVENTS, window.location.origin);

  // Добавляем параметры
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.append(key, value);
    }
  });

  const response = await fetch(url.toString(), {
    headers: authHeaders(false),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const data = await response.json();
  return data.results || data;
}

/**
 * Получить событие по ID
 * @param {number} eventId - ID события
 * @returns {Promise<Object>} Событие
 */
export async function getEvent(eventId) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(API_URLS.EVENT_DETAIL(eventId), window.location.origin);

  const response = await fetch(url.toString(), {
    headers: authHeaders(false),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Создать событие
 * @param {Object} eventData - Данные события
 * @returns {Promise<Object>} Созданное событие
 */
export async function createEvent(eventData) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(API_URLS.EVENTS, window.location.origin);

  const response = await fetch(url.toString(), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(eventData),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Инвалидируем кеш событий
  invalidateEventsCache();

  return response.json();
}

/**
 * Обновить событие
 * @param {number} eventId - ID события
 * @param {Object} updates - Обновляемые поля
 * @returns {Promise<Object>} Обновленное событие
 */
export async function updateEvent(eventId, updates) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(API_URLS.EVENT_DETAIL(eventId), window.location.origin);

  const response = await fetch(url.toString(), {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Инвалидируем кеш событий
  invalidateEventsCache();

  return response.json();
}

/**
 * Удалить событие
 * @param {number} eventId - ID события
 * @returns {Promise<void>}
 */
export async function deleteEvent(eventId) {
  // ИСПРАВЛЕНО: используем константу вместо хардкода
  const url = new URL(API_URLS.EVENT_DETAIL(eventId), window.location.origin);

  const response = await fetch(url.toString(), {
    method: "DELETE",
    headers: authHeaders(),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Инвалидируем кеш событий
  invalidateEventsCache();
}

/**
 * Инвалидировать кеш событий
 */
export function invalidateEventsCache() {
  dataManager.invalidatePattern(/^events:/);
}

/**
 * Инвалидировать весь кеш календарей
 */
export function invalidateCalendarsCache() {
  dataManager.invalidatePattern(/^calendars:/);
}

/**
 * Инвалидировать кеш событий календарей
 */
export function invalidateCalendarEventsCache() {
  dataManager.invalidatePattern(/^calendar:events:/);
}

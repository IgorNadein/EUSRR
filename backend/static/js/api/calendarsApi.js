/**
 * @fileoverview Calendars API - работа с календарями (CRUD + подписки)
 * @module api/calendarsApi
 */

import { dataManager } from "../managers/dataManager.js";

/**
 * Получить токен авторизации
 * @returns {string}
 * @private
 */
function getAccessToken() {
  const meta = document.querySelector('meta[name="api-access"]');
  const token = meta?.getAttribute("content")?.trim();
  if (token) return token;

  try {
    return localStorage.getItem("api.access") || "";
  } catch {
    return "";
  }
}

/**
 * Получить CSRF токен
 * @returns {string}
 * @private
 */
function getCsrfToken() {
  return (
    document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
    document.querySelector('meta[name="csrf-token"]')?.content ||
    getCookie("csrftoken") ||
    ""
  );
}

/**
 * Получить cookie по имени
 * @param {string} name
 * @returns {string}
 * @private
 */
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

/**
 * Создать заголовки с авторизацией
 * @param {boolean} [includeContentType=true] - Добавить Content-Type
 * @returns {Object}
 * @private
 */
function authHeaders(includeContentType = true) {
  const token = getAccessToken();
  const headers = {
    Accept: "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "X-CSRFToken": getCsrfToken(),
  };

  if (includeContentType) {
    headers["Content-Type"] = "application/json";
  }

  return headers;
}

/**
 * Получить список доступных календарей текущего пользователя
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Array>} Массив календарей
 */
export async function getMyCalendars(ttl = 60000) {
  const key = "calendars:my";

  return dataManager.fetch(
    key,
    async () => {
      const url = new URL(
        "/api/v1/calendar/calendars/",
        window.location.origin,
      );

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

      const data = await response.json();
      return data.results || [];
    },
    ttl,
  );
}

/**
 * Получить календарь по ID
 * @param {number} calendarId - ID календаря
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Object>} Календарь
 */
export async function getCalendar(calendarId, ttl = 60000) {
  const key = `calendars:${calendarId}`;

  return dataManager.fetch(
    key,
    async () => {
      const url = new URL(
        `/api/v1/calendar/calendars/${calendarId}/`,
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
  const url = new URL("/api/v1/calendar/calendars/", window.location.origin);

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
  const url = new URL(
    `/api/v1/calendar/calendars/${calendarId}/`,
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
  const url = new URL(
    `/api/v1/calendar/calendars/${calendarId}/`,
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

/**
 * Подписаться на календарь
 * @param {number} calendarId - ID календаря
 * @param {Object} [options] - Опции подписки
 * @param {boolean} [options.can_edit] - Право редактирования
 * @param {boolean} [options.can_manage] - Право управления
 * @returns {Promise<Object>} Данные подписки
 */
export async function subscribeToCalendar(calendarId, options = {}) {
  const url = new URL(
    `/api/v1/calendar/calendars/${calendarId}/subscribe/`,
    window.location.origin,
  );

  const response = await fetch(url.toString(), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(options),
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
  dataManager.invalidate("subscriptions:my");

  return response.json();
}

/**
 * Отписаться от календаря
 * @param {number} calendarId - ID календаря
 * @returns {Promise<void>}
 */
export async function unsubscribeFromCalendar(calendarId) {
  const url = new URL(
    `/api/v1/calendar/calendars/${calendarId}/unsubscribe/`,
    window.location.origin,
  );

  const response = await fetch(url.toString(), {
    method: "POST",
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
  dataManager.invalidate("subscriptions:my");
}

/**
 * Получить мои подписки на календари
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Array>} Массив подписок
 */
export async function getMySubscriptions(ttl = 60000) {
  const key = "subscriptions:my";

  return dataManager.fetch(
    key,
    async () => {
      const url = new URL(
        "/api/v1/calendar/subscriptions/",
        window.location.origin,
      );

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

      const data = await response.json();
      return data.results || [];
    },
    ttl,
  );
}

/**
 * Инвалидировать весь кеш календарей
 */
export function invalidateCalendarsCache() {
  dataManager.invalidatePattern(/^calendars:/);
  dataManager.invalidatePattern(/^subscriptions:/);
}

/**
 * @fileoverview API URL constants - константы URL API эндпоинтов
 * @module constants/apiUrls
 */

/**
 * Базовые URL API эндпоинтов
 * @enum {string}
 */
export const API_URLS = {
  // Calendar Events API
  EVENTS: '/api/v1/calendar/events/',
  EVENT_DETAIL: (id) => `/api/v1/calendar/events/${id}/`,

  // Calendars API
  CALENDARS: '/api/v1/calendar/calendars/',
  CALENDAR_DETAIL: (id) => `/api/v1/calendar/calendars/${id}/`,
  CALENDAR_SUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/subscribe/`,
  CALENDAR_UNSUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/unsubscribe/`,

  // Departments API
  MY_DEPARTMENTS: '/api/v1/departments/my-departments/',
  DEPARTMENT_DETAIL: (id) => `/api/v1/departments/${id}/`,

  // Employees API
  EMPLOYEES: '/api/v1/employees/',
  EMPLOYEE_DETAIL: (id) => `/api/v1/employees/${id}/`,
};

/**
 * Дефолтные параметры для API запросов
 * @enum {*}
 */
export const API_DEFAULTS = {
  // Time-to-live для кеша (в миллисекундах)
  TTL: {
    EVENTS: 30000,        // 30 секунд
    EVENT_DETAIL: 60000,  // 1 минута
    CALENDARS: 60000,     // 1 минута
    DEPARTMENTS: 300000,  // 5 минут
  },

  // Таймауты для запросов
  TIMEOUT: {
    DEFAULT: 10000,       // 10 секунд
    UPLOAD: 30000,        // 30 секунд
  },
};

/**
 * Получить полный URL для API эндпоинта
 * @param {string} path - Путь к эндпоинту
 * @param {string} [baseUrl] - Базовый URL (по умолчанию window.location.origin)
 * @returns {string} Полный URL
 */
export function getApiUrl(path, baseUrl = window.location.origin) {
  return new URL(path, baseUrl).toString();
}

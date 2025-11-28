/**
 * @fileoverview Calendar API - обертка над API календаря с кешированием
 * @module api/calendarApi
 */

import { dataManager } from '../managers/dataManager.js';

/**
 * Получить токен авторизации
 * @returns {string}
 * @private
 */
function getAccessToken() {
  const meta = document.querySelector('meta[name="api-access"]');
  const token = meta?.getAttribute('content')?.trim();
  if (token) return token;
  
  try {
    return localStorage.getItem('api.access') || '';
  } catch {
    return '';
  }
}

/**
 * Создать заголовки с авторизацией
 * @returns {Object}
 * @private
 */
function authHeaders() {
  const token = getAccessToken();
  return {
    'Accept': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
}

/**
 * Получить события календаря
 * @param {Object} params - Параметры запроса
 * @param {string} params.start - Дата начала (YYYY-MM-DD)
 * @param {string} params.end - Дата конца (YYYY-MM-DD)
 * @param {number} [params.department_id] - ID отдела (опционально)
 * @param {number} [ttl=30000] - Time to live кеша в мс
 * @returns {Promise<Array>} Массив событий
 */
export async function getCalendarEvents(params, ttl = 30000) {
  // Создаем уникальный ключ для кеша
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  
  const key = `calendar:events:${JSON.stringify(sortedParams)}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = new URL('/api/v1/calendar/events/', window.location.origin);
      Object.keys(params).forEach(k => {
        if (params[k] != null) {
          url.searchParams.set(k, String(params[k]));
        }
      });
      
      const response = await fetch(url.toString(), {
        headers: authHeaders()
      });
      
      if (response.status === 401) {
        console.warn('[CalendarAPI] 401 Unauthorized');
        return [];
      }
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Поддержка разных форматов ответа
      return Array.isArray(data) 
        ? data 
        : data.results || data.items || data.events || [];
    },
    ttl
  );
}

/**
 * Получить событие по ID
 * @param {number|string} eventId - ID события
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Object>} Событие
 */
export async function getCalendarEvent(eventId, ttl = 60000) {
  const key = `calendar:event:${eventId}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = `/api/v1/calendar/events/${eventId}/`;
      const response = await fetch(url, {
        headers: authHeaders()
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return response.json();
    },
    ttl
  );
}

/**
 * Инвалидировать кеш событий календаря
 * @param {Object} [params] - Параметры для инвалидации (если не указаны, инвалидируется весь кеш)
 */
export function invalidateCalendarEvents(params = null) {
  if (params) {
    const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
      acc[key] = params[key];
      return acc;
    }, {});
    const key = `calendar:events:${JSON.stringify(sortedParams)}`;
    dataManager.invalidate(key);
  } else {
    // Инвалидируем все события календаря
    dataManager.invalidatePattern(/^calendar:events:/);
  }
}

/**
 * Инвалидировать кеш конкретного события
 * @param {number|string} eventId - ID события
 */
export function invalidateCalendarEvent(eventId) {
  dataManager.invalidate(`calendar:event:${eventId}`);
}

/**
 * Пре-загрузить события в кеш (например, из SSR данных)
 * @param {Object} params - Параметры запроса
 * @param {Array} events - Данные событий
 */
export function preloadCalendarEvents(params, events) {
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  const key = `calendar:events:${JSON.stringify(sortedParams)}`;
  dataManager.preload(key, events);
}

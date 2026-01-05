/**
 * @fileoverview Notifications API - обертка над API уведомлений с кешированием
 * @module api/notificationsApi
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
 * Получить уведомления
 * @param {Object} params - Параметры запроса
 * @param {number} [params.page=1] - Номер страницы
 * @param {number} [params.page_size=5] - Размер страницы
 * @param {boolean} [params.unread_only=false] - Только непрочитанные
 * @param {number} [ttl=10000] - Time to live кеша в мс (10 сек по умолчанию)
 * @returns {Promise<Object>} Объект с уведомлениями
 */
export async function getNotifications(params = {}, ttl = 10000) {
  const defaultParams = {
    page: 1,
    page_size: 5,
    unread_only: false,
    ...params
  };
  
  // Создаем уникальный ключ для кеша
  const sortedParams = Object.keys(defaultParams).sort().reduce((acc, key) => {
    acc[key] = defaultParams[key];
    return acc;
  }, {});
  
  const key = `notifications:list:${JSON.stringify(sortedParams)}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = new URL('/api/v1/notifications/', window.location.origin);
      Object.keys(defaultParams).forEach(k => {
        if (defaultParams[k] != null) {
          url.searchParams.set(k, String(defaultParams[k]));
        }
      });
      
      const response = await fetch(url.toString(), {
        headers: authHeaders()
      });
      
      if (response.status === 401) {
        console.warn('[NotificationsAPI] 401 Unauthorized');
        return { notifications: [], total: 0 };
      }
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return response.json();
    },
    ttl
  );
}

/**
 * Получить количество непрочитанных уведомлений
 * @param {number} [ttl=5000] - Time to live кеша в мс (5 сек)
 * @returns {Promise<number>} Количество непрочитанных
 */
export async function getUnreadCount(ttl = 5000) {
  const key = 'notifications:unread-count';
  
  return dataManager.fetch(
    key,
    async () => {
      const data = await getNotifications({ unread_only: true, page_size: 1 }, 0);
      return data.total || 0;
    },
    ttl
  );
}

/**
 * Отметить уведомление как прочитанное
 * @param {number} notificationId - ID уведомления
 * @returns {Promise<void>}
 */
export async function markAsRead(notificationId) {
  const url = `/api/v1/notifications/${notificationId}/read/`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json'
    }
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  // Инвалидируем кеш после изменения
  invalidateNotifications();
  
  return response.json();
}

/**
 * Отметить все уведомления как прочитанные
 * @returns {Promise<void>}
 */
export async function markAllAsRead() {
  const url = '/api/v1/notifications/read-all/';
  const response = await fetch(url, {
    method: 'POST',
    headers: authHeaders()
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  // Инвалидируем кеш после изменения
  invalidateNotifications();
  
  return response.json();
}

/**
 * Инвалидировать кеш уведомлений
 */
export function invalidateNotifications() {
  dataManager.invalidatePattern(/^notifications:/);
}

/**
 * Пре-загрузить уведомления в кеш
 * @param {Object} params - Параметры запроса
 * @param {Object} data - Данные уведомлений
 */
export function preloadNotifications(params, data) {
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  const key = `notifications:list:${JSON.stringify(sortedParams)}`;
  dataManager.preload(key, data);
}

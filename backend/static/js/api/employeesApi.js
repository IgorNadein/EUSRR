/**
 * @fileoverview Employees API - обертка над API сотрудников с кешированием
 * @module api/employeesApi
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
 * Получить список сотрудников
 * @param {Object} params - Параметры запроса
 * @param {boolean} [params.active=true] - Только активные
 * @param {string} [params.created_at__gte] - Созданы после даты
 * @param {string} [params.ordering] - Сортировка
 * @param {number} [params.page_size] - Размер страницы
 * @param {number} [ttl=60000] - Time to live кеша в мс (60 сек)
 * @returns {Promise<Object>} Объект с сотрудниками
 */
export async function getEmployees(params = {}, ttl = 60000) {
  // Создаем уникальный ключ для кеша
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  
  const key = `employees:list:${JSON.stringify(sortedParams)}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = new URL('/api/v1/employees/', window.location.origin);
      Object.keys(params).forEach(k => {
        if (params[k] != null) {
          url.searchParams.set(k, String(params[k]));
        }
      });
      
      const response = await fetch(url.toString(), {
        headers: authHeaders()
      });
      
      if (response.status === 401) {
        console.warn('[EmployeesAPI] 401 Unauthorized');
        return { results: [], count: 0 };
      }
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Поддержка разных форматов ответа
      return Array.isArray(data) 
        ? { results: data, count: data.length } 
        : data;
    },
    ttl
  );
}

/**
 * Получить новых сотрудников
 * @param {number} [days=14] - За сколько дней
 * @param {number} [limit=10] - Лимит
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Array>} Массив сотрудников
 */
export async function getNewEmployees(days = 14, limit = 10, ttl = 60000) {
  const since = new Date();
  since.setDate(since.getDate() - days);
  
  const params = {
    active: 'true',
    created_at__gte: since.toISOString(),
    ordering: '-created_at',
    page_size: limit
  };
  
  const data = await getEmployees(params, ttl);
  return data.results || [];
}

/**
 * Получить сотрудника по ID
 * @param {number|string} employeeId - ID сотрудника
 * @param {number} [ttl=300000] - Time to live кеша в мс (5 минут)
 * @returns {Promise<Object>} Сотрудник
 */
export async function getEmployee(employeeId, ttl = 300000) {
  const key = `employees:${employeeId}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = `/api/v1/employees/${employeeId}/`;
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
 * Инвалидировать кеш сотрудников
 */
export function invalidateEmployees() {
  dataManager.invalidatePattern(/^employees:/);
}

/**
 * Инвалидировать кеш конкретного сотрудника
 * @param {number|string} employeeId - ID сотрудника
 */
export function invalidateEmployee(employeeId) {
  dataManager.invalidate(`employees:${employeeId}`);
}

/**
 * Пре-загрузить сотрудников в кеш
 * @param {Object} params - Параметры запроса
 * @param {Object} data - Данные сотрудников
 */
export function preloadEmployees(params, data) {
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  const key = `employees:list:${JSON.stringify(sortedParams)}`;
  dataManager.preload(key, data);
}

/**
 * @fileoverview Departments API - обертка над API отделов с кешированием
 * @module api/departmentsApi
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
 * Получить отделы текущего пользователя
 * @param {number} [ttl=60000] - Time to live кеша в мс (60 секунд по умолчанию)
 * @returns {Promise<Array>} Массив отделов
 */
export async function getMyDepartments(ttl = 60000) {
  const key = 'departments:my';
  
  return dataManager.fetch(
    key,
    async () => {
      const url = '/api/v1/departments/my-departments/';
      const response = await fetch(url, {
        headers: authHeaders()
      });
      
      if (response.status === 401) {
        console.warn('[DepartmentsAPI] 401 Unauthorized');
        return [];
      }
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Поддержка разных форматов ответа
      return Array.isArray(data) 
        ? data 
        : data.results || data.items || data.departments || [];
    },
    ttl
  );
}

/**
 * Получить все отделы
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Array>} Массив отделов
 */
export async function getAllDepartments(ttl = 60000) {
  const key = 'departments:all';
  
  return dataManager.fetch(
    key,
    async () => {
      const url = '/api/v1/departments/';
      const response = await fetch(url, {
        headers: authHeaders()
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      return Array.isArray(data) 
        ? data 
        : data.results || data.items || data.departments || [];
    },
    ttl
  );
}

/**
 * Получить отдел по ID
 * @param {number|string} departmentId - ID отдела
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Object>} Отдел
 */
export async function getDepartment(departmentId, ttl = 60000) {
  const key = `departments:${departmentId}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = `/api/v1/departments/${departmentId}/`;
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
 * Инвалидировать кеш отделов
 */
export function invalidateDepartments() {
  dataManager.invalidatePattern(/^departments:/);
}

/**
 * Инвалидировать кеш моих отделов
 */
export function invalidateMyDepartments() {
  dataManager.invalidate('departments:my');
}

/**
 * Пре-загрузить отделы в кеш
 * @param {Array} departments - Данные отделов
 */
export function preloadMyDepartments(departments) {
  dataManager.preload('departments:my', departments);
}

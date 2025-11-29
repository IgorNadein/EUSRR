/**
 * @fileoverview Posts API - обертка над API постов ленты с кешированием
 * @module api/postsApi
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
 * Получить посты ленты
 * @param {Object} params - Параметры запроса
 * @param {string} [params.type='company'] - Тип постов (company/personal)
 * @param {number} [params.page=1] - Номер страницы
 * @param {number} [ttl=30000] - Time to live кеша в мс (30 сек)
 * @returns {Promise<Object>} Объект с постами
 */
export async function getPosts(params = {}, ttl = 30000) {
  const defaultParams = {
    type: 'company',
    page: 1,
    ...params
  };
  
  // Создаем уникальный ключ для кеша
  const sortedParams = Object.keys(defaultParams).sort().reduce((acc, key) => {
    acc[key] = defaultParams[key];
    return acc;
  }, {});
  
  const key = `posts:list:${JSON.stringify(sortedParams)}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = new URL('/api/v1/posts/', window.location.origin);
      Object.keys(defaultParams).forEach(k => {
        if (defaultParams[k] != null) {
          url.searchParams.set(k, String(defaultParams[k]));
        }
      });
      
      const response = await fetch(url.toString(), {
        headers: authHeaders()
      });
      
      if (response.status === 401) {
        console.warn('[PostsAPI] 401 Unauthorized');
        return { results: [], count: 0, next: null, previous: null };
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
 * Получить пост по ID
 * @param {number|string} postId - ID поста
 * @param {number} [ttl=60000] - Time to live кеша в мс
 * @returns {Promise<Object>} Пост
 */
export async function getPost(postId, ttl = 60000) {
  const key = `posts:${postId}`;
  
  return dataManager.fetch(
    key,
    async () => {
      const url = `/api/v1/posts/${postId}/`;
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
 * Инвалидировать кеш постов
 * @param {Object} [params] - Параметры для инвалидации (если не указаны, инвалидируется весь кеш)
 */
export function invalidatePosts(params = null) {
  if (params) {
    const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
      acc[key] = params[key];
      return acc;
    }, {});
    const key = `posts:list:${JSON.stringify(sortedParams)}`;
    dataManager.invalidate(key);
  } else {
    // Инвалидируем все посты
    dataManager.invalidatePattern(/^posts:/);
  }
}

/**
 * Инвалидировать кеш конкретного поста
 * @param {number|string} postId - ID поста
 */
export function invalidatePost(postId) {
  dataManager.invalidate(`posts:${postId}`);
}

/**
 * Пре-загрузить посты в кеш
 * @param {Object} params - Параметры запроса
 * @param {Object} data - Данные постов
 */
export function preloadPosts(params, data) {
  const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
    acc[key] = params[key];
    return acc;
  }, {});
  const key = `posts:list:${JSON.stringify(sortedParams)}`;
  dataManager.preload(key, data);
}

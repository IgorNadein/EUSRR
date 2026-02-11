/**
 * @fileoverview Authentication utilities - работа с токенами и авторизацией
 * @module utils/authUtils
 */

/**
 * Получить токен доступа из meta-тега или localStorage
 * @returns {string} Токен доступа или пустая строка
 */
export function getAccessToken() {
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
 * Получить CSRF токен из различных источников
 * @returns {string} CSRF токен или пустая строка
 */
export function getCsrfToken() {
  return (
    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    document.querySelector('meta[name="csrf-token"]')?.content ||
    getCookie('csrftoken') ||
    ''
  );
}

/**
 * Получить значение cookie по имени
 * @param {string} name - Имя cookie
 * @returns {string} Значение cookie или пустая строка
 */
export function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue || '';
}

/**
 * Создать заголовки для API запросов с авторизацией
 * @param {boolean} [includeContentType=true] - Добавлять ли Content-Type
 * @returns {Object} Объект с заголовками
 */
export function authHeaders(includeContentType = true) {
  const token = getAccessToken();
  const headers = {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const csrfToken = getCsrfToken();
  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken;
  }

  if (includeContentType) {
    headers['Content-Type'] = 'application/json';
  }

  return headers;
}

/**
 * Проверить наличие валидного токена авторизации
 * @returns {boolean} True если токен есть
 */
export function hasValidToken() {
  const token = getAccessToken();
  return Boolean(token && token.length > 0);
}

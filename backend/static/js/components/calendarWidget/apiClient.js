/**
 * apiClient.js
 * Клиент для работы с API календаря
 * @module calendarWidget/apiClient
 */

import { authHeaders as getAuthHeaders } from "../../utils/authUtils.js";

/**
 * Универсальный fetch с обработкой JSON
 * @param {string} url - URL запроса
 * @param {Object} opts - Опции fetch
 * @returns {Promise<Array|Object>} - Данные или массив
 */
export async function fetchJSON(url, opts = {}) {
  const headers = {
    Accept: "application/json",
    ...getAuthHeaders(),
    ...(opts.headers || {}),
  };
  const r = await fetch(url, { headers, ...opts });
  if (r.status === 401) {
    console.warn("401 от API — нужен валидный access токен");
    return [];
  }
  if (!r.ok) {
    let text = await r.text();
    try {
      text = JSON.parse(text);
    } catch {}
    throw { status: r.status, data: text };
  }
  const data = await r.json();
  return Array.isArray(data)
    ? data
    : data.results || data.items || data.events || [];
}

/**
 * GET запрос к API
 * @param {string} url - URL запроса
 * @returns {Promise<Object>} - JSON данные
 * @throws {Error} - Ошибка с status и data
 */
export async function apiGet(url) {
  const r = await fetch(url, {
    headers: { Accept: "application/json", ...getAuthHeaders() },
  });
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    const err = new Error("GET failed");
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data;
}

/**
 * DELETE запрос к API
 * @param {string} url - URL запроса
 * @returns {Promise<void>}
 * @throws {Error} - Ошибка с status и data
 */
export async function apiDelete(url) {
  const r = await fetch(url, {
    method: "DELETE",
    headers: { ...getAuthHeaders() },
  });
  if (!r.ok) {
    const data = await r.json().catch(() => null);
    const err = new Error("DELETE failed");
    err.status = r.status;
    err.data = data;
    throw err;
  }
}

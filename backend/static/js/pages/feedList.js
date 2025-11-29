/**
 * @module pages/feedList
 * @description Инициализация страницы ленты новостей
 */

import { initFeedCrudHandler } from '../components/feedCrudHandler.js';

/**
 * Инициализирует страницу списка новостей
 * @param {Object} config - Конфигурация страницы
 * @param {string} config.postsApiUrl - URL API для постов
 * @param {string} config.commentsApiUrl - URL API для комментариев
 */
export function initFeedListPage(config) {
  const {
    postsApiUrl,
    commentsApiUrl
  } = config;

  // Получаем токен доступа
  const accessMeta = document.querySelector('meta[name="api-access"]');
  const ACCESS = accessMeta ? accessMeta.content : '';
  const headers = ACCESS ? { 'Authorization': 'Bearer ' + ACCESS } : {};

  // Инициализация CRUD операций для постов и комментариев
  initFeedCrudHandler({
    postsApiUrl,
    commentsApiUrl,
    headers
  });
}

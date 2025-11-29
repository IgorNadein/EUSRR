/**
 * @module pages/postDetail
 * @description Инициализация страницы детального просмотра поста
 */

import { initFeedCrudHandler } from '../components/feedCrudHandler.js';

/**
 * Инициализирует страницу детального просмотра поста
 * @param {Object} config - Конфигурация страницы
 * @param {string} config.postsApiUrl - URL API для постов
 * @param {string} config.commentsApiUrl - URL API для комментариев
 */
export function initPostDetailPage(config) {
  const {
    postsApiUrl,
    commentsApiUrl
  } = config;

  // Получаем токен доступа
  const accessMeta = document.querySelector('meta[name="api-access"]');
  const ACCESS = accessMeta ? accessMeta.content : '';
  const headers = ACCESS ? { 'Authorization': 'Bearer ' + ACCESS } : {};

  // Инициализация CRUD операций
  initFeedCrudHandler({
    postsApiUrl,
    commentsApiUrl,
    headers
  });
}

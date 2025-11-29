/**
 * @module pages/postForm
 * @description Инициализация страницы создания/редактирования поста
 */

import { initFeedCrudHandler } from '../components/feedCrudHandler.js';

/**
 * Инициализирует страницу формы поста
 * @param {Object} config - Конфигурация страницы
 * @param {string} config.postsApiUrl - URL API для постов
 * @param {string} config.commentsApiUrl - URL API для комментариев
 */
export function initPostFormPage(config) {
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

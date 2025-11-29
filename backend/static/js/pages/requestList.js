/**
 * @module pages/requestList
 * @description Инициализация страницы списка заявлений
 */

import { initRequestModalHandler } from '../components/requestModalHandler.js';
import { initRequestCommentsHandler } from '../components/requestCommentsHandler.js';
import { initRequestCrudHandler } from '../components/requestCrudHandler.js';

/**
 * Инициализирует страницу списка заявлений
 * @param {Object} config - Конфигурация страницы
 * @param {string} config.apiListUrl - URL API для списка заявлений
 * @param {string} config.apiDetailBase - Базовый URL для операций с конкретным заявлением
 * @param {string} config.commentsUrlTemplate - Шаблон URL для получения комментариев
 * @param {string} config.addCommentUrlTemplate - Шаблон URL для добавления комментария
 * @param {boolean} [config.autoShowComments=false] - Автоматически показать комментарии
 */
export function initRequestListPage(config) {
  const {
    apiListUrl,
    apiDetailBase,
    commentsUrlTemplate,
    addCommentUrlTemplate,
    autoShowComments = false
  } = config;

  // Получаем токен доступа
  const accessMeta = document.querySelector('meta[name="api-access"]');
  const ACCESS = accessMeta ? accessMeta.content : '';
  const headers = ACCESS ? { 'Authorization': 'Bearer ' + ACCESS } : {};

  // Инициализация обработчиков модальных окон
  initRequestModalHandler({
    autoShowComments
  });

  // Инициализация обработчика комментариев
  initRequestCommentsHandler({
    commentsUrlTemplate,
    addCommentUrlTemplate,
    autoloadCounts: true
  });

  // Инициализация CRUD операций для заявлений
  initRequestCrudHandler({
    apiListUrl,
    apiDetailBase,
    headers
  });
}

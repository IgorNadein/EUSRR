/**
 * @module pages/requestList
 * @description Инициализация страницы списка заявлений
 */

import { initRequestModalHandler } from '../components/requestModalHandler.js';
import { initRequestCommentsHandler } from '../components/requestCommentsHandler.js';
import { initRequestCrudHandler } from '../components/requestCrudHandler.js';
import { initRequestListHandler } from '../components/requestListHandler.js';

/**
 * Инициализирует страницу списка заявлений
 * @param {Object} config - Конфигурация страницы
 * @param {string} config.apiListUrl - URL API для списка заявлений
 * @param {string} config.apiDetailBase - Базовый URL для операций с конкретным заявлением
 * @param {string} config.commentsUrlTemplate - Шаблон URL для получения комментариев
 * @param {string} config.addCommentUrlTemplate - Шаблон URL для добавления комментария
 * @param {boolean} [config.autoShowComments=false] - Автоматически показать комментарии
 * @param {boolean} [config.useAjaxList=false] - Использовать AJAX для загрузки списка
 */
export function initRequestListPage(config) {
  const {
    apiListUrl,
    apiDetailBase,
    commentsUrlTemplate,
    addCommentUrlTemplate,
    autoShowComments = false,
    useAjaxList = false
  } = config;

  // Получаем токен доступа
  const accessMeta = document.querySelector('meta[name="api-access"]');
  const ACCESS = accessMeta ? accessMeta.content : '';
  
  // Функция для получения CSRF токена из cookie
  function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  
  const headers = {
    'X-CSRFToken': getCsrfToken()
  };
  
  if (ACCESS) {
    headers['Authorization'] = 'Bearer ' + ACCESS;
  }

  // Если включен AJAX режим - инициализируем обработчик списка
  if (useAjaxList) {
    const userId = parseInt(document.body.dataset.userId || '0', 10);
    const canProcess = document.body.dataset.canProcess === 'true';
    
    console.log('Request list AJAX mode:', {
      apiListUrl,
      userId,
      canProcess
    });
    
    // Инициализация списка заявлений (AJAX загрузка с бесконечной прокруткой)
    const requestListHandler = initRequestListHandler({
      apiListUrl,
      detailUrlTemplate: '/requests/{id}/',
      userId,
      canProcess,
      headers
    });
    
    // Обработка переключения фильтров через URL параметры
    const urlParams = new URLSearchParams(window.location.search);
    const currentView = urlParams.get('view') || '';
    const currentType = urlParams.get('type') || '';
    const currentStatus = urlParams.get('status') || '';
    
    if (currentView && requestListHandler.setView) {
      requestListHandler.setView(currentView);
    }
    if (currentType && requestListHandler.setType) {
      requestListHandler.setType(currentType);
    }
    if (currentStatus && requestListHandler.setStatus) {
      requestListHandler.setStatus(currentStatus);
    }
  }

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

  // Слушаем события обновления заявлений (approve/reject)
  document.addEventListener('request:updated', function(event) {
    console.log('Request updated:', event.detail);
    // Перезагружаем страницу для обновления списка
    // TODO: в будущем можно заменить на AJAX обновление конкретной карточки
    setTimeout(() => window.location.reload(), 500);
  });
}

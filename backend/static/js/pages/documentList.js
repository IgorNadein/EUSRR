/**
 * @module pages/documentList
 * @description Инициализация страницы списка документов
 */

import { RecipientPicker } from '../components/recipientPickerHandler.js';
import { initDocumentCrud } from '../components/documentCrudHandler.js';
import { initDocumentAcks } from '../components/documentAcksHandler.js';
import { initDocumentListHandler } from '../components/documentListHandler.js';

/**
 * Инициализирует страницу списка документов
 * @param {Object} config - Конфигурация страницы
 * @param {string} config.apiListUrl - URL API для списка документов
 * @param {string} config.apiDetailBase - Базовый URL для операций с конкретным документом
 * @param {string} config.employeesApi - URL API для списка сотрудников
 * @param {string} config.departmentsApi - URL API для списка отделов
 * @param {number} [config.pageSize=100] - Размер страницы для модалки ознакомлений
 */
export function initDocumentListPage(config) {
  const {
    apiListUrl,
    apiDetailBase,
    employeesApi,
    departmentsApi,
    pageSize = 100
  } = config;

  // Получаем токен доступа
  const accessMeta = document.querySelector('meta[name="api-access"]');
  const ACCESS = accessMeta ? accessMeta.content : '';
  const headers = ACCESS ? { 'Authorization': 'Bearer ' + ACCESS } : {};
  
  // Получаем ID текущего пользователя
  const userId = parseInt(document.body.dataset.userId || '0', 10);
  const canManage = document.body.dataset.canManageDocuments === 'true';
  
  // Получаем текущий scope из URL
  const urlParams = new URLSearchParams(window.location.search);
  const currentScope = urlParams.get('scope') || 'mine';

  console.log('Document page initialization:', {
    apiListUrl,
    apiDetailBase,
    employeesApi,
    departmentsApi,
    hasAuth: !!ACCESS,
    userId,
    canManage,
    currentScope
  });
  
  // Инициализация списка документов (AJAX загрузка с бесконечной прокруткой)
  const documentListHandler = initDocumentListHandler({
    apiListUrl,
    acknowledgeUrlTemplate: '/documents/ack/{id}/',
    userId,
    canManage,
    headers
  });
  
  // Устанавливаем начальный scope
  if (currentScope && documentListHandler.setScope) {
    documentListHandler.setScope(currentScope);
  }

  // Инициализация RecipientPicker для формы создания
  const createPicker = new RecipientPicker(
    document.getElementById('createRecipients'),
    { headers, apiUrl: employeesApi }
  );

  // Инициализация RecipientPicker для формы редактирования
  const editPicker = new RecipientPicker(
    document.getElementById('editRecipients'),
    { headers, apiUrl: employeesApi }
  );

  // Инициализация CRUD операций для документов
  initDocumentCrud({
    apiListUrl,
    apiDetailBase,
    headers,
    createPicker,
    editPicker,
    departmentsApi
  });

  // Инициализация модалки ознакомлений
  initDocumentAcks({
    apiDetailBase,
    headers,
    pageSize
  });
}

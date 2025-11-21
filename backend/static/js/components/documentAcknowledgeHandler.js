/**
 * @module documentAcknowledgeHandler
 * @description Обработчик автоматического ознакомления с документами.
 * При клике на неознакомленный документ автоматически отправляет POST запрос
 * на /api/v1/documents/{id}/acknowledge/ и обновляет UI.
 * 
 * Использование:
 * import { initDocumentAcknowledge } from './documentAcknowledgeHandler.js';
 * 
 * initDocumentAcknowledge({
 *   apiDetailBase: '/api/v1/documents/',
 *   headers: { 'Authorization': 'Bearer TOKEN' }
 * });
 */

/**
 * Инициализирует обработчик автоматического ознакомления с документами.
 * @param {Object} options - Опции инициализации
 * @param {string} options.apiDetailBase - Базовый URL для API документов
 * @param {Object} [options.headers={}] - HTTP заголовки для запросов
 * @returns {Object} API с методом destroy
 */
export function initDocumentAcknowledge(options) {
  const {
    apiDetailBase,
    headers = {}
  } = options;

  const listElement = document.getElementById('docList');

  if (!listElement) {
    console.warn('initDocumentAcknowledge: элемент #docList не найден');
    return { destroy: () => {} };
  }

  /**
   * Отправляет ознакомление на сервер.
   * @param {number} docId - ID документа
   * @returns {Promise<boolean>} - true если успешно
   */
  async function acknowledgeDocument(docId) {
    try {
      const response = await fetch(`${apiDetailBase}${docId}/acknowledge/`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok || response.status === 201) {
        return true;
      } else {
        console.error('Не удалось отметить ознакомление:', response.status);
        return false;
      }
    } catch (error) {
      console.error('Ошибка при отправке ознакомления:', error);
      return false;
    }
  }

  /**
   * Обновляет UI документа после ознакомления.
   * @param {HTMLElement} docRow - Элемент строки документа
   */
  function updateDocumentUI(docRow) {
    // Убираем класс неознакомленного
    docRow.classList.remove('doc-unacked');
    
    // Обновляем data-атрибут
    docRow.dataset.isAcked = '1';
    
    // Добавляем бейдж "Ознакомлен" если его еще нет
    const actions = docRow.querySelector('.doc-actions');
    if (actions && !actions.querySelector('.badge-acked')) {
      const badge = document.createElement('span');
      badge.className = 'badge-acked';
      badge.textContent = '✓ Ознакомлен';
      actions.insertBefore(badge, actions.firstChild);
    }
  }

  /**
   * Обработчик клика по документу.
   */
  async function handleDocumentClick(e) {
    // Проверяем, что клик был по ссылке на документ
    const link = e.target.closest('.doc-link');
    if (!link) return;

    const docId = link.dataset.docId;
    if (!docId) return;

    // Находим строку документа
    const docRow = link.closest('.doc-row');
    if (!docRow) return;

    // Проверяем, не ознакомлен ли уже
    const isAcked = docRow.dataset.isAcked === '1';
    if (isAcked) return; // Уже ознакомлен, ничего не делаем

    // Отправляем ознакомление асинхронно (не блокируем открытие файла)
    acknowledgeDocument(docId).then(success => {
      if (success) {
        updateDocumentUI(docRow);
      }
    });
  }

  // Установка обработчика
  listElement.addEventListener('click', handleDocumentClick);

  /**
   * Функция для удаления обработчика.
   */
  function destroy() {
    listElement.removeEventListener('click', handleDocumentClick);
  }

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initDocumentAcknowledge = initDocumentAcknowledge;
}

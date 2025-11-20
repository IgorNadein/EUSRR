/**
 * @fileoverview Request Modal Handler - обработка модальных окон заявок
 * Автозаполнение модалов из data-атрибутов, управление состоянием
 * @module components/requestModalHandler
 */

/**
 * Привязывает модальное окно к кнопке с автозаполнением одного поля (ID)
 * 
 * @param {string} modalId - ID модального окна
 * @param {string} inputId - ID input поля для заполнения
 * 
 * @example
 * bindModalIdOnly('reqApproveModal', 'approveId');
 */
export function bindModalIdOnly(modalId, inputId) {
  const modal = document.getElementById(modalId);
  
  modal?.addEventListener('show.bs.modal', (e) => {
    const btn = e.relatedTarget;
    const id = btn?.getAttribute('data-id') || '';
    const input = modal.querySelector('#' + inputId);
    
    if (input) {
      input.value = id;
    }
  });
}

/**
 * Привязывает модальное окно редактирования с автозаполнением всех полей
 * 
 * @param {string} modalId - ID модального окна
 * @param {Object} fieldMapping - Маппинг data-атрибутов на ID полей формы
 * 
 * @example
 * bindModalEditForm('reqEditModal', {
 *   id: 'editId',
 *   title: 'editTitle',
 *   type: 'editType',
 *   date_from: 'editDateFrom',
 *   date_to: 'editDateTo',
 *   comment: 'editComment',
 *   status: 'editIsDraft' // checkbox
 * });
 */
export function bindModalEditForm(modalId, fieldMapping) {
  const modal = document.getElementById(modalId);
  
  modal?.addEventListener('show.bs.modal', (e) => {
    const btn = e.relatedTarget;
    if (!btn) return;
    
    const getData = (name) => btn.getAttribute('data-' + name) || '';
    
    Object.entries(fieldMapping).forEach(([dataAttr, inputId]) => {
      const input = document.getElementById(inputId);
      if (!input) return;
      
      const value = getData(dataAttr);
      
      // Обработка checkbox
      if (input.type === 'checkbox') {
        input.checked = value === 'draft' || value === 'true' || value === '1';
      } else {
        input.value = value;
      }
    });
  });
}

/**
 * Инициализирует обработчики модальных окон для заявок
 * 
 * @param {Object} [options] - Опции инициализации
 * @param {boolean} [options.autoShowComments] - Автоматически показать модал комментариев
 * @returns {Object} API обработчика
 */
export function initRequestModalHandler(options = {}) {
  const {
    autoShowComments = false
  } = options;
  
  // Привязка простых модалов (только ID)
  bindModalIdOnly('reqApproveModal', 'approveId');
  bindModalIdOnly('reqRejectModal', 'rejectId');
  bindModalIdOnly('reqCancelModal', 'cancelId');
  bindModalIdOnly('reqDeleteModal', 'deleteId');
  bindModalIdOnly('reqCommentModal', 'commentId');
  
  // Привязка модала редактирования
  bindModalEditForm('reqEditModal', {
    id: 'editId',
    title: 'editTitle',
    type: 'editType',
    date_from: 'editDateFrom',
    date_to: 'editDateTo',
    comment: 'editComment',
    status: 'editIsDraft'
  });
  
  // Автоматический показ модала комментариев (если запрошено)
  if (autoShowComments) {
    document.addEventListener('DOMContentLoaded', () => {
      const modal = document.getElementById('reqCommentsModal');
      if (modal && window.bootstrap) {
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
      }
    });
  }
  
  return {
    bindModalIdOnly,
    bindModalEditForm
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initRequestModalHandler = initRequestModalHandler;
}

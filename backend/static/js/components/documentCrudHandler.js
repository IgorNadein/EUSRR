/**
 * @module documentCrudHandler
 * @description Обработчик CRUD операций для документов с поддержкой RecipientPicker.
 * Управляет созданием, редактированием и удалением документов через API.
 * 
 * Использование:
 * import { initDocumentCrud } from './documentCrudHandler.js';
 * import { RecipientPicker } from './recipientPickerHandler.js';
 * 
 * initDocumentCrud({
 *   apiListUrl: '/api/v1/documents/',
 *   apiDetailBase: '/api/v1/documents/',
 *   headers: { 'Authorization': 'Bearer TOKEN' },
 *   createPicker: recipientPickerInstance,
 *   editPicker: recipientPickerInstance
 * });
 */

/**
 * Переключает видимость блока получателей в зависимости от чекбокса "Отправить всем".
 * @param {HTMLInputElement} checkbox - Чекбокс "sent_to_all"
 * @param {HTMLElement} block - Блок с виджетом получателей
 */
function toggleRecipientsBlock(checkbox, block) {
  block.hidden = checkbox.checked; // Скрыть, если "всем"
}

/**
 * Добавляет ID получателей в FormData.
 * @param {FormData} formData - Объект FormData
 * @param {Array<number>} ids - Массив ID получателей
 */
function appendRecipientIds(formData, ids) {
  // API ожидает повторяемые recipient_ids
  for (const id of ids) {
    formData.append('recipient_ids', String(id));
  }
}

/**
 * Инициализирует обработчики CRUD операций для документов.
 * @param {Object} options - Опции инициализации
 * @param {string} options.apiListUrl - URL API для списка документов
 * @param {string} options.apiDetailBase - Базовый URL для операций с конкретным документом
 * @param {Object} [options.headers={}] - HTTP заголовки для запросов
 * @param {Object} options.createPicker - Экземпляр RecipientPicker для формы создания
 * @param {Object} options.editPicker - Экземпляр RecipientPicker для формы редактирования
 * @returns {Object} API с методом destroy
 */
export function initDocumentCrud(options) {
  const {
    apiListUrl,
    apiDetailBase,
    headers = {},
    createPicker,
    editPicker
  } = options;

  // Элементы формы создания
  const createForm = document.getElementById('docCreateForm');
  const createAllCheckbox = document.getElementById('createSentToAll');
  const createBlock = document.getElementById('createRecipientsBlock');

  // Элементы формы редактирования
  const editModal = document.getElementById('docEditModal');
  const editForm = document.getElementById('docEditForm');
  const editAllCheckbox = document.getElementById('editSentToAll');
  const editBlock = document.getElementById('editRecipientsBlock');

  // Список документов
  const listElement = document.getElementById('docList');

  if (!createForm || !editForm || !listElement) {
    console.warn('initDocumentCrud: обязательные элементы не найдены');
    return { destroy: () => {} };
  }

  // Инициализация переключения блоков получателей
  if (createAllCheckbox && createBlock) {
    toggleRecipientsBlock(createAllCheckbox, createBlock);
    createAllCheckbox.addEventListener('change', () => {
      toggleRecipientsBlock(createAllCheckbox, createBlock);
    });
  }

  if (editAllCheckbox && editBlock) {
    toggleRecipientsBlock(editAllCheckbox, editBlock);
    editAllCheckbox.addEventListener('change', () => {
      toggleRecipientsBlock(editAllCheckbox, editBlock);
    });
  }

  /**
   * Обработчик создания документа.
   */
  async function handleCreate(e) {
    e.preventDefault();
    
    const formData = new FormData(createForm);
    formData.set('sent_to_all', createAllCheckbox.checked ? 'true' : 'false');

    if (!createAllCheckbox.checked) {
      const ids = createPicker.getIds();
      if (ids.length === 0) {
        alert('Выберите получателей или включите «Отправить всем».');
        return;
      }
      appendRecipientIds(formData, ids);
    } else {
      formData.delete('recipient_ids');
    }

    try {
      const response = await fetch(apiListUrl, {
        method: 'POST',
        headers: headers,
        body: formData
      });

      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      await response.json();
      window.location.reload();
    } catch (error) {
      alert('Не удалось создать документ: ' + error.message);
    }
  }

  /**
   * Открывает модальное окно редактирования документа.
   * @param {HTMLElement} button - Кнопка с data-атрибутами документа
   */
  async function openEditModal(button) {
    const docId = button.getAttribute('data-doc-id');
    
    editForm.elements.id.value = docId;
    editForm.elements.title.value = button.getAttribute('data-doc-title') || '';
    editForm.elements.description.value = button.getAttribute('data-doc-description') || '';
    
    const sentToAll = button.getAttribute('data-doc-sent_to_all') === '1';
    editAllCheckbox.checked = sentToAll;
    toggleRecipientsBlock(editAllCheckbox, editBlock);

    // Загружаем текущих получателей документа
    try {
      const response = await fetch(apiDetailBase + docId + '/', { headers });
      
      if (response.ok) {
        const data = await response.json();
        const recipients = (data && data.recipients) ? data.recipients.map(r => ({
          id: r.id,
          display_name: r.display_name || r.full_name || r.email || ('#' + r.id),
          email: r.email || ''
        })) : [];
        editPicker.setSelected(recipients);
      } else {
        editPicker.setSelected([]);
      }
    } catch (error) {
      console.error('Ошибка загрузки получателей:', error);
      editPicker.setSelected([]);
    }

    bootstrap.Modal.getOrCreateInstance(editModal).show();
  }

  /**
   * Обработчик редактирования документа.
   */
  async function handleEdit(e) {
    e.preventDefault();
    
    const docId = editForm.elements.id.value;
    const formData = new FormData(editForm);
    formData.set('sent_to_all', editAllCheckbox.checked ? 'true' : 'false');

    if (!editAllCheckbox.checked) {
      const ids = editPicker.getIds();
      if (ids.length === 0) {
        alert('Выберите получателей или включите «Отправить всем».');
        return;
      }
      appendRecipientIds(formData, ids);
    } else {
      formData.delete('recipient_ids');
    }

    // Если файл не выбран — не отправляем ключ
    if (!(editForm.elements.file && editForm.elements.file.files.length)) {
      formData.delete('file');
    }

    try {
      const response = await fetch(apiDetailBase + docId + '/', {
        method: 'PATCH',
        headers: headers,
        body: formData
      });

      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      await response.json();
      window.location.reload();
    } catch (error) {
      alert('Не удалось сохранить: ' + error.message);
    }
  }

  /**
   * Удаляет документ после подтверждения.
   * @param {HTMLElement} button - Кнопка с data-doc-id
   */
  async function handleDelete(button) {
    if (!confirm('Удалить документ?')) return;

    const docId = button.getAttribute('data-doc-id');

    try {
      const response = await fetch(apiDetailBase + docId + '/', {
        method: 'DELETE',
        headers: headers
      });

      if (response.status === 204 || response.ok) {
        window.location.reload();
      } else {
        throw new Error('HTTP ' + response.status);
      }
    } catch (error) {
      alert('Не удалось удалить документ: ' + error.message);
    }
  }

  /**
   * Делегированный обработчик кликов по списку документов.
   */
  function handleListClick(e) {
    const button = e.target.closest('button[data-action]');
    if (!button) return;

    const action = button.getAttribute('data-action');
    
    if (action === 'edit') {
      openEditModal(button);
    } else if (action === 'delete') {
      handleDelete(button);
    }
  }

  // Установка обработчиков
  createForm.addEventListener('submit', handleCreate);
  editForm.addEventListener('submit', handleEdit);
  listElement.addEventListener('click', handleListClick);

  /**
   * Функция для удаления всех обработчиков.
   */
  function destroy() {
    createForm.removeEventListener('submit', handleCreate);
    editForm.removeEventListener('submit', handleEdit);
    listElement.removeEventListener('click', handleListClick);
  }

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initDocumentCrud = initDocumentCrud;
}

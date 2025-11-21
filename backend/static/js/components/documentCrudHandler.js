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
 * Переключает видимость блоков получателей в зависимости от чекбокса "Отправить всем".
 * @param {HTMLInputElement} checkbox - Чекбокс "sent_to_all"
 * @param {HTMLElement} deptBlock - Блок с виджетом отделов
 * @param {HTMLElement} recipBlock - Блок с виджетом получателей
 */
function toggleRecipientsBlocks(checkbox, deptBlock, recipBlock) {
  const hidden = checkbox.checked;
  if (deptBlock) deptBlock.hidden = hidden;
  if (recipBlock) recipBlock.hidden = hidden;
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
 * Добавляет ID отделов в FormData.
 * @param {FormData} formData - Объект FormData
 * @param {Array<number>} ids - Массив ID отделов
 */
function appendDepartmentIds(formData, ids) {
  // API ожидает повторяемые department_ids
  for (const id of ids) {
    formData.append('department_ids', String(id));
  }
}

/**
 * Загружает список отделов из API и заполняет select элементы.
 * @param {string} departmentsApi - URL API для получения списка отделов
 * @param {Object} headers - HTTP заголовки для запросов
 * @param {HTMLSelectElement} createSelect - Select для формы создания
 * @param {HTMLSelectElement} editSelect - Select для формы редактирования
 */
async function loadDepartments(departmentsApi, headers, createSelect, editSelect) {
  if (!departmentsApi || (!createSelect && !editSelect)) {
    console.warn('loadDepartments: отсутствует URL API или select элементы');
    return;
  }

  try {
    const response = await fetch(departmentsApi, { headers });
    if (!response.ok) {
      throw new Error('HTTP ' + response.status);
    }

    const data = await response.json();
    const departments = data.results || data || [];

    // Заполняем оба select'а
    [createSelect, editSelect].forEach(select => {
      if (!select) return;
      
      select.innerHTML = '';
      departments.forEach(dept => {
        const option = document.createElement('option');
        option.value = dept.id;
        option.textContent = dept.name;
        select.appendChild(option);
      });
    });

    console.log(`Загружено отделов: ${departments.length}`);
  } catch (error) {
    console.error('Ошибка загрузки отделов:', error);
    // Показываем сообщение в select'ах
    [createSelect, editSelect].forEach(select => {
      if (!select) return;
      select.innerHTML = '<option disabled>Ошибка загрузки отделов</option>';
    });
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
 * @param {string} [options.departmentsApi] - URL API для получения списка отделов
 * @returns {Object} API с методом destroy
 */
export function initDocumentCrud(options) {
  const {
    apiListUrl,
    apiDetailBase,
    headers = {},
    createPicker,
    editPicker,
    departmentsApi
  } = options;

  // Элементы формы создания
  const createForm = document.getElementById('docCreateForm');
  const createAllCheckbox = document.getElementById('createSentToAll');
  const createDeptBlock = document.getElementById('createDepartmentsBlock');
  const createRecipBlock = document.getElementById('createRecipientsBlock');
  const createDeptSelect = document.getElementById('createDepartments');

  // Элементы формы редактирования
  const editModal = document.getElementById('docEditModal');
  const editForm = document.getElementById('docEditForm');
  const editAllCheckbox = document.getElementById('editSentToAll');
  const editDeptBlock = document.getElementById('editDepartmentsBlock');
  const editRecipBlock = document.getElementById('editRecipientsBlock');
  const editDeptSelect = document.getElementById('editDepartments');

  // Список документов
  const listElement = document.getElementById('docList');

  if (!createForm || !editForm || !listElement) {
    console.warn('initDocumentCrud: обязательные элементы не найдены');
    return { destroy: () => {} };
  }

  // Загружаем список отделов
  if (departmentsApi) {
    loadDepartments(departmentsApi, headers, createDeptSelect, editDeptSelect);
  }

  // Инициализация переключения блоков получателей
  if (createAllCheckbox) {
    toggleRecipientsBlocks(createAllCheckbox, createDeptBlock, createRecipBlock);
    createAllCheckbox.addEventListener('change', () => {
      toggleRecipientsBlocks(createAllCheckbox, createDeptBlock, createRecipBlock);
    });
  }

  if (editAllCheckbox) {
    toggleRecipientsBlocks(editAllCheckbox, editDeptBlock, editRecipBlock);
    editAllCheckbox.addEventListener('change', () => {
      toggleRecipientsBlocks(editAllCheckbox, editDeptBlock, editRecipBlock);
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
      // Собираем выбранные ID отделов
      const deptIds = createDeptSelect 
        ? Array.from(createDeptSelect.selectedOptions).map(opt => opt.value)
        : [];
      
      // Собираем выбранные ID получателей
      const recipientIds = createPicker.getIds();
      
      if (deptIds.length === 0 && recipientIds.length === 0) {
        alert('Выберите отделы, получателей или включите «Отправить всем».');
        return;
      }
      
      // Добавляем отделы
      if (deptIds.length > 0) {
        appendDepartmentIds(formData, deptIds);
      }
      
      // Добавляем получателей
      if (recipientIds.length > 0) {
        appendRecipientIds(formData, recipientIds);
      }
    } else {
      formData.delete('recipient_ids');
      formData.delete('department_ids');
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
    toggleRecipientsBlocks(editAllCheckbox, editDeptBlock, editRecipBlock);

    // Загружаем текущие данные документа (получатели и отделы)
    try {
      const response = await fetch(apiDetailBase + docId + '/', { headers });
      
      if (response.ok) {
        const data = await response.json();
        
        // Заполняем получателей
        const recipients = (data && data.recipients) ? data.recipients.map(r => ({
          id: r.id,
          display_name: r.display_name || r.full_name || r.email || ('#' + r.id),
          email: r.email || ''
        })) : [];
        editPicker.setSelected(recipients);
        
        // Заполняем отделы
        if (editDeptSelect && data.departments) {
          const deptIds = data.departments.map(d => String(d.id));
          Array.from(editDeptSelect.options).forEach(option => {
            option.selected = deptIds.includes(option.value);
          });
        }
      } else {
        editPicker.setSelected([]);
        if (editDeptSelect) {
          Array.from(editDeptSelect.options).forEach(opt => opt.selected = false);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки данных документа:', error);
      editPicker.setSelected([]);
      if (editDeptSelect) {
        Array.from(editDeptSelect.options).forEach(opt => opt.selected = false);
      }
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
      // Собираем выбранные ID отделов
      const deptIds = editDeptSelect 
        ? Array.from(editDeptSelect.selectedOptions).map(opt => opt.value)
        : [];
      
      // Собираем выбранные ID получателей
      const recipientIds = editPicker.getIds();
      
      if (deptIds.length === 0 && recipientIds.length === 0) {
        alert('Выберите отделы, получателей или включите «Отправить всем».');
        return;
      }
      
      // Добавляем отделы
      if (deptIds.length > 0) {
        appendDepartmentIds(formData, deptIds);
      }
      
      // Добавляем получателей
      if (recipientIds.length > 0) {
        appendRecipientIds(formData, recipientIds);
      }
    } else {
      formData.delete('recipient_ids');
      formData.delete('department_ids');
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

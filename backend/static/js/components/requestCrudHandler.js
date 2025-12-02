/**
 * @module requestCrudHandler
 * @description Обработчик CRUD операций для заявлений через API
 */

import { RecipientPicker } from './recipientPicker.js';

/**
 * Инициализирует обработчики CRUD операций для заявлений
 * @param {Object} options - Опции инициализации
 * @param {string} options.apiListUrl - URL API для списка заявлений
 * @param {string} options.apiDetailBase - Базовый URL для операций с конкретным заявлением
 * @param {Object} [options.headers={}] - HTTP заголовки для запросов
 * @returns {Object} API с методом destroy
 */
export function initRequestCrudHandler(options) {
  const {
    apiListUrl,
    apiDetailBase,
    headers = {}
  } = options;

  // Формы
  const createForm = document.getElementById('reqCreateForm');
  const editForm = document.getElementById('reqEditForm');
  const deleteForm = document.getElementById('reqDeleteForm');
  const approveForm = document.getElementById('reqApproveForm');
  const rejectForm = document.getElementById('reqRejectForm');
  const cancelForm = document.getElementById('reqCancelForm');
  const commentForm = document.getElementById('reqCommentForm');

  if (!createForm) {
    console.warn('initRequestCrudHandler: required forms not found');
    return { destroy: () => {} };
  }

  // Инициализация RecipientPicker для создания
  let createRecipientPicker = null;
  const createPickerContainer = document.getElementById('createRecipientPicker');
  if (createPickerContainer) {
    createRecipientPicker = new RecipientPicker(createPickerContainer, {
      apiUsersUrl: '/api/v1/employees/',
      apiDepartmentsUrl: '/api/v1/departments/'
    });
  }

  // Инициализация RecipientPicker для редактирования
  let editRecipientPicker = null;
  const editPickerContainer = document.getElementById('editRecipientPicker');
  if (editPickerContainer) {
    editRecipientPicker = new RecipientPicker(editPickerContainer, {
      apiUsersUrl: '/api/v1/employees/',
      apiDepartmentsUrl: '/api/v1/departments/'
    });
  }

  /**
   * Обработчик создания заявления
   */
  async function handleCreate(e) {
    e.preventDefault();
    
    const saveAs = e.submitter?.value || 'submit'; // 'draft' or 'submit'
    const formData = new FormData(createForm);
    
    // Добавляем данные получателей из RecipientPicker
    if (createRecipientPicker) {
      const recipients = createRecipientPicker.getValues();
      
      // Добавляем department_ids
      if (recipients.department_ids && recipients.department_ids.length > 0) {
        recipients.department_ids.forEach(id => {
          formData.append('department_ids', id);
        });
      }
      
      // Добавляем recipient_ids
      if (recipients.recipient_ids && recipients.recipient_ids.length > 0) {
        recipients.recipient_ids.forEach(id => {
          formData.append('recipient_ids', id);
        });
      }
      
      // Добавляем cc_user_ids
      if (recipients.cc_user_ids && recipients.cc_user_ids.length > 0) {
        recipients.cc_user_ids.forEach(id => {
          formData.append('cc_user_ids', id);
        });
      }
      
      // Добавляем sent_to_all_department
      if (recipients.sent_to_all_department) {
        formData.set('sent_to_all_department', 'true');
      }
    }
    
    // Удаляем пустые поля для черновика
    if (saveAs === 'draft') {
      for (const [key, value] of Array.from(formData.entries())) {
        if (!value || value === '') {
          formData.delete(key);
        }
      }
    }

    try {
      const url = saveAs === 'draft' ? `${apiListUrl}?save_as=draft` : apiListUrl;
      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: formData
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'HTTP ' + response.status);
      }

      await response.json();
      
      // Показываем сообщение и перезагружаем
      const message = saveAs === 'draft' ? 'Черновик сохранён.' : 'Заявление отправлено на рассмотрение.';
      alert(message); // TODO: заменить на toast-уведомление
      
      // Очищаем форму и picker
      createForm.reset();
      if (createRecipientPicker) {
        createRecipientPicker.reset();
      }
      
      window.location.reload();
    } catch (error) {
      alert('Не удалось создать заявление: ' + error.message);
    }
  }

  /**
   * Обработчик редактирования заявления
   */
  async function handleEdit(e) {
    e.preventDefault();
    
    const reqId = editForm.elements.id.value;
    const saveAs = e.submitter?.value || 'submit';
    const formData = new FormData(editForm);
    
    // Добавляем данные получателей из RecipientPicker
    if (editRecipientPicker) {
      const recipients = editRecipientPicker.getValues();
      
      // Добавляем department_ids
      if (recipients.department_ids && recipients.department_ids.length > 0) {
        recipients.department_ids.forEach(id => {
          formData.append('department_ids', id);
        });
      }
      
      // Добавляем recipient_ids
      if (recipients.recipient_ids && recipients.recipient_ids.length > 0) {
        recipients.recipient_ids.forEach(id => {
          formData.append('recipient_ids', id);
        });
      }
      
      // Добавляем cc_user_ids
      if (recipients.cc_user_ids && recipients.cc_user_ids.length > 0) {
        recipients.cc_user_ids.forEach(id => {
          formData.append('cc_user_ids', id);
        });
      }
      
      // Добавляем sent_to_all_department
      if (recipients.sent_to_all_department) {
        formData.set('sent_to_all_department', 'true');
      }
    }
    
    // Удаляем пустые поля
    for (const [key, value] of Array.from(formData.entries())) {
      if (!value || value === '') {
        formData.delete(key);
      }
    }

    try {
      let url = `${apiDetailBase}${reqId}/`;
      if (saveAs === 'draft' || saveAs === 'submit') {
        url += `?save_as=${saveAs}`;
      }

      const response = await fetch(url, {
        method: 'PATCH',
        headers: headers,
        body: formData
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'HTTP ' + response.status);
      }

      await response.json();
      alert('Заявление обновлено.');
      window.location.reload();
    } catch (error) {
      alert('Не удалось обновить заявление: ' + error.message);
    }
  }

  /**
   * Обработчик удаления заявления
   */
  async function handleDelete(e) {
    e.preventDefault();
    
    const reqId = deleteForm.elements.id.value;
    
    if (!confirm('Вы уверены, что хотите удалить это заявление?')) {
      return;
    }

    try {
      const response = await fetch(`${apiDetailBase}${reqId}/`, {
        method: 'DELETE',
        headers: headers
      });

      if (!response.ok && response.status !== 204) {
        const error = await response.json();
        throw new Error(error.detail || 'HTTP ' + response.status);
      }

      alert('Заявление удалено.');
      window.location.reload();
    } catch (error) {
      alert('Не удалось удалить заявление: ' + error.message);
    }
  }

  /**
   * Обработчик одобрения заявления
   */
  async function handleApprove(e) {
    e.preventDefault();
    
    const reqId = approveForm.elements.id.value;

    try {
      const response = await fetch(`${apiDetailBase}${reqId}/approve/`, {
        method: 'POST',
        headers: headers
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'HTTP ' + response.status);
      }

      await response.json();
      alert('Заявление одобрено.');
      window.location.reload();
    } catch (error) {
      alert('Не удалось одобрить заявление: ' + error.message);
    }
  }

  /**
   * Обработчик отклонения заявления
   */
  async function handleReject(e) {
    e.preventDefault();
    
    const reqId = rejectForm.elements.id.value;

    try {
      const response = await fetch(`${apiDetailBase}${reqId}/reject/`, {
        method: 'POST',
        headers: headers
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'HTTP ' + response.status);
      }

      await response.json();
      alert('Заявление отклонено.');
      window.location.reload();
    } catch (error) {
      alert('Не удалось отклонить заявление: ' + error.message);
    }
  }

  /**
   * Обработчик отмены заявления (пользователем)
   */
  async function handleCancel(e) {
    e.preventDefault();
    
    const reqId = cancelForm.elements.id.value;

    if (!confirm('Вы уверены, что хотите отменить это заявление?')) {
      return;
    }

    try {
      const response = await fetch(`${apiDetailBase}${reqId}/cancel/`, {
        method: 'POST',
        headers: headers
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'HTTP ' + response.status);
      }

      await response.json();
      alert('Заявление отменено.');
      window.location.reload();
    } catch (error) {
      alert('Не удалось отменить заявление: ' + error.message);
    }
  }

  /**
   * Обработчик добавления комментария
   */
  async function handleComment(e) {
    e.preventDefault();
    
    const reqId = commentForm.elements.id.value;
    const text = (commentForm.elements.text.value || '').trim();

    if (!text) {
      alert('Комментарий не может быть пустым.');
      return;
    }

    try {
      const response = await fetch(`${apiDetailBase}${reqId}/comments/`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text })
      });

      if (!response.ok && response.status !== 201) {
        const error = await response.json();
        throw new Error(error.detail || 'HTTP ' + response.status);
      }

      await response.json();
      alert('Комментарий добавлен.');
      window.location.reload();
    } catch (error) {
      alert('Не удалось добавить комментарий: ' + error.message);
    }
  }

  // Установка обработчиков
  createForm?.addEventListener('submit', handleCreate);
  editForm?.addEventListener('submit', handleEdit);
  deleteForm?.addEventListener('submit', handleDelete);
  approveForm?.addEventListener('submit', handleApprove);
  rejectForm?.addEventListener('submit', handleReject);
  cancelForm?.addEventListener('submit', handleCancel);
  commentForm?.addEventListener('submit', handleComment);

  /**
   * Функция для удаления всех обработчиков
   */
  function destroy() {
    createForm?.removeEventListener('submit', handleCreate);
    editForm?.removeEventListener('submit', handleEdit);
    deleteForm?.removeEventListener('submit', handleDelete);
    approveForm?.removeEventListener('submit', handleApprove);
    rejectForm?.removeEventListener('submit', handleReject);
    cancelForm?.removeEventListener('submit', handleCancel);
    commentForm?.removeEventListener('submit', handleComment);
    
    // Очистка RecipientPicker
    if (createRecipientPicker) {
      createRecipientPicker.destroy();
    }
    if (editRecipientPicker) {
      editRecipientPicker.destroy();
    }
  }

  console.log('Request CRUD handler initialized');

  return { 
    destroy,
    createRecipientPicker,
    editRecipientPicker
  };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initRequestCrudHandler = initRequestCrudHandler;
}

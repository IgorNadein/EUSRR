/**
 * @module avatarPreviewHandler
 * @description Обработчик превью изображения (аватара) с управлением object URL.
 * Показывает выбранное изображение до загрузки на сервер, автоматически освобождает память.
 * 
 * Пример HTML:
 * <div class="preview-container">
 *   <img id="avatarPreview" class="d-none">
 *   <i id="avatarPlaceholder" class="bi bi-person-circle"></i>
 * </div>
 * <input type="file" name="avatar" accept="image/*">
 * 
 * Использование:
 * import { initAvatarPreview } from './avatarPreviewHandler.js';
 * initAvatarPreview({
 *   fileInputSelector: 'input[type="file"][name="avatar"]',
 *   previewImageId: 'avatarPreview',
 *   placeholderId: 'avatarPlaceholder'
 * });
 */

/**
 * Инициализирует обработчик превью аватара с автоматическим управлением памятью.
 * @param {Object} options - Опции инициализации
 * @param {string} options.fileInputSelector - CSS-селектор для input[type="file"]
 * @param {string} options.previewImageId - ID элемента <img> для превью
 * @param {string} options.placeholderId - ID элемента-плейсхолдера (иконка)
 * @returns {Object} API с методами destroy, showPreview, hidePreview
 */
export function initAvatarPreview(options) {
  const {
    fileInputSelector,
    previewImageId,
    placeholderId
  } = options;

  const fileInput = document.querySelector(fileInputSelector);
  const preview = document.getElementById(previewImageId);
  const placeholder = document.getElementById(placeholderId);
  const formEl = fileInput ? fileInput.closest('form') : null;

  if (!fileInput || !preview) {
    console.warn('initAvatarPreview: обязательные элементы не найдены');
    return { destroy: () => {}, showPreview: () => {}, hidePreview: () => {} };
  }

  let objectURL = null;

  /**
   * Показывает превью изображения, скрывает плейсхолдер.
   * @param {string} url - URL изображения (blob URL или обычный URL)
   */
  function showPreview(url) {
    if (placeholder) {
      placeholder.classList.add('d-none');
    }
    preview.src = url;
    preview.classList.remove('d-none');
  }

  /**
   * Скрывает превью изображения, показывает плейсхолдер.
   */
  function hidePreview() {
    preview.removeAttribute('src');
    preview.classList.add('d-none');
    if (placeholder) {
      placeholder.classList.remove('d-none');
    }
  }

  /**
   * Безопасно освобождает object URL.
   */
  function revokeObjectURLSafe() {
    try {
      if (objectURL) {
        URL.revokeObjectURL(objectURL);
      }
    } catch (e) {
      console.warn('Не удалось освободить objectURL:', e);
    }
    objectURL = null;
  }

  /**
   * Обработчик изменения файла в input.
   */
  function handleFileChange() {
    revokeObjectURLSafe();
    const file = fileInput.files && fileInput.files[0];
    
    if (file) {
      objectURL = URL.createObjectURL(file);
      showPreview(objectURL);
    } else {
      hidePreview();
    }
  }

  /**
   * Обработчик сброса формы.
   */
  function handleFormReset() {
    revokeObjectURLSafe();
    // Небольшая задержка, чтобы браузер успел очистить value у input[type=file]
    setTimeout(hidePreview, 0);
  }

  /**
   * Обработчик ухода со страницы (освобождение памяти).
   */
  function handleBeforeUnload() {
    revokeObjectURLSafe();
  }

  // Установка обработчиков
  fileInput.addEventListener('change', handleFileChange);
  
  if (formEl) {
    formEl.addEventListener('reset', handleFormReset);
  }
  
  window.addEventListener('beforeunload', handleBeforeUnload);

  /**
   * Функция для удаления всех обработчиков и освобождения памяти.
   */
  function destroy() {
    revokeObjectURLSafe();
    fileInput.removeEventListener('change', handleFileChange);
    
    if (formEl) {
      formEl.removeEventListener('reset', handleFormReset);
    }
    
    window.removeEventListener('beforeunload', handleBeforeUnload);
  }

  return {
    destroy,
    showPreview,
    hidePreview
  };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initAvatarPreview = initAvatarPreview;
}

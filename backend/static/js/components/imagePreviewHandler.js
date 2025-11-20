/**
 * @module imagePreviewHandler
 * @description Универсальный обработчик превью изображений для input[type="file"].
 * Показывает выбранное изображение до загрузки, автоматически управляет памятью.
 * 
 * Пример HTML:
 * <input type="file" id="imageInput" accept="image/*">
 * <img id="imagePreview" class="d-none">
 * 
 * Использование:
 * import { initImagePreview } from './imagePreviewHandler.js';
 * initImagePreview({
 *   inputId: 'imageInput',
 *   previewId: 'imagePreview'
 * });
 */

/**
 * Инициализирует превью изображения для input[type="file"].
 * @param {Object} options - Опции инициализации
 * @param {string} options.inputId - ID элемента input[type="file"]
 * @param {string} options.previewId - ID элемента <img> для превью
 * @param {string} [options.currentPreviewId] - ID текущего превью (для режима редактирования)
 * @param {string} [options.hiddenClass='d-none'] - Класс для скрытия элементов
 * @returns {Object} API с методами destroy, show, hide, clear
 */
export function initImagePreview(options) {
  const {
    inputId,
    previewId,
    currentPreviewId,
    hiddenClass = 'd-none'
  } = options;

  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  const currentPreview = currentPreviewId ? document.getElementById(currentPreviewId) : null;

  if (!input || !preview) {
    console.warn('initImagePreview: обязательные элементы не найдены');
    return { destroy: () => {}, show: () => {}, hide: () => {}, clear: () => {} };
  }

  let objectURL = null;

  /**
   * Показывает новое превью, скрывает текущее.
   * @param {string} url - URL изображения (blob URL)
   */
  function showNewPreview(url) {
    // Скрываем текущее превью (если есть)
    if (currentPreview) {
      currentPreview.classList.add(hiddenClass);
    }

    // Показываем новое превью
    preview.src = url;
    preview.classList.remove(hiddenClass);
  }

  /**
   * Скрывает новое превью, показывает текущее (если есть).
   */
  function hideNewPreview() {
    preview.src = '';
    preview.classList.add(hiddenClass);

    // Восстанавливаем текущее превью (если было)
    if (currentPreview) {
      currentPreview.classList.remove(hiddenClass);
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
   * Очищает выбор файла и превью.
   */
  function clear() {
    revokeObjectURLSafe();
    input.value = '';
    hideNewPreview();
  }

  /**
   * Обработчик изменения файла.
   */
  function handleChange() {
    revokeObjectURLSafe();
    
    const file = input.files && input.files[0];
    
    if (file) {
      objectURL = URL.createObjectURL(file);
      showNewPreview(objectURL);
    } else {
      hideNewPreview();
    }
  }

  /**
   * Обработчик ухода со страницы.
   */
  function handleBeforeUnload() {
    revokeObjectURLSafe();
  }

  // Устанавливаем обработчики
  input.addEventListener('change', handleChange);
  window.addEventListener('beforeunload', handleBeforeUnload);

  /**
   * Функция для удаления обработчиков и освобождения памяти.
   */
  function destroy() {
    revokeObjectURLSafe();
    input.removeEventListener('change', handleChange);
    window.removeEventListener('beforeunload', handleBeforeUnload);
  }

  return {
    destroy,
    show: showNewPreview,
    hide: hideNewPreview,
    clear
  };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initImagePreview = initImagePreview;
}

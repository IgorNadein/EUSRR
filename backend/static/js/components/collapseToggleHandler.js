/**
 * @module collapseToggleHandler
 * @description Обработчик для Bootstrap Collapse с переключением текста/состояния.
 * Управляет показом/скрытием контента с синхронизацией UI (кнопки, тексты).
 * 
 * HTML структура:
 * <div id="excerpt">Краткий текст...</div>
 * <div id="full" class="collapse" data-excerpt="#excerpt" data-btn="#moreBtn">
 *   Полный текст...
 * </div>
 * <button id="moreBtn" data-bs-toggle="collapse" data-bs-target="#full">
 *   <span class="txt-more">Подробнее</span>
 *   <span class="txt-less">Скрыть</span>
 * </button>
 * 
 * Использование:
 * import { initCollapseToggle } from './collapseToggleHandler.js';
 * initCollapseToggle();
 */

/**
 * Инициализирует обработчик переключения collapse.
 * @returns {Object} API с методом destroy
 */
export function initCollapseToggle() {
  /**
   * Обработчик события show.bs.collapse.
   * Скрывает краткий текст и обновляет кнопку.
   * @param {Event} event - Bootstrap collapse событие
   */
  function handleShow(event) {
    const target = event.target;
    const excerptSelector = target.dataset.excerpt;
    const btnSelector = target.dataset.btn;

    // Скрываем краткий текст
    if (excerptSelector) {
      const excerptEl = document.querySelector(excerptSelector);
      excerptEl?.classList.add('d-none');
    }

    // Обновляем кнопку
    if (btnSelector) {
      const btn = document.querySelector(btnSelector);
      if (btn) {
        btn.querySelector('.txt-more')?.classList.add('d-none');
        btn.querySelector('.txt-less')?.classList.remove('d-none');
        btn.setAttribute('aria-expanded', 'true');
      }
    }
  }

  /**
   * Обработчик события hide.bs.collapse.
   * Показывает краткий текст и обновляет кнопку.
   * @param {Event} event - Bootstrap collapse событие
   */
  function handleHide(event) {
    const target = event.target;
    const excerptSelector = target.dataset.excerpt;
    const btnSelector = target.dataset.btn;

    // Показываем краткий текст
    if (excerptSelector) {
      const excerptEl = document.querySelector(excerptSelector);
      excerptEl?.classList.remove('d-none');
    }

    // Обновляем кнопку
    if (btnSelector) {
      const btn = document.querySelector(btnSelector);
      if (btn) {
        btn.querySelector('.txt-more')?.classList.remove('d-none');
        btn.querySelector('.txt-less')?.classList.add('d-none');
        btn.setAttribute('aria-expanded', 'false');
      }
    }
  }

  // Установка обработчиков на document (делегирование)
  document.addEventListener('show.bs.collapse', handleShow);
  document.addEventListener('hide.bs.collapse', handleHide);

  /**
   * Удаление обработчиков.
   */
  function destroy() {
    document.removeEventListener('show.bs.collapse', handleShow);
    document.removeEventListener('hide.bs.collapse', handleHide);
  }

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initCollapseToggle = initCollapseToggle;
}

/**
 * @module tooltipInitializer
 * @description Инициализирует Bootstrap Tooltip для элементов с data-tooltip="1".
 * Автоматически находит и активирует все тултипы на странице после загрузки DOM.
 * 
 * HTML:
 * <button data-tooltip="1" title="Подсказка">Кнопка</button>
 * 
 * Использование:
 * import { initTooltips } from './tooltipInitializer.js';
 * initTooltips();
 */

/**
 * Инициализирует Bootstrap Tooltip для всех элементов с data-tooltip="1".
 * @returns {Object} API с методом destroy
 */
export function initTooltips() {
  if (!window.bootstrap || !window.bootstrap.Tooltip) {
    console.warn('initTooltips: Bootstrap Tooltip не найден');
    return { destroy: () => {} };
  }

  const tooltipInstances = [];
  const elements = document.querySelectorAll('[data-tooltip="1"]');

  elements.forEach(el => {
    try {
      const tooltip = new bootstrap.Tooltip(el);
      tooltipInstances.push(tooltip);
    } catch (error) {
      console.warn('initTooltips: ошибка инициализации tooltip', el, error);
    }
  });

  /**
   * Удаление всех tooltip instances.
   */
  function destroy() {
    tooltipInstances.forEach(tooltip => {
      try {
        tooltip.dispose();
      } catch (error) {
        console.warn('initTooltips: ошибка dispose tooltip', error);
      }
    });
    tooltipInstances.length = 0;
  }

  return { destroy };
}

/**
 * Автоматическая инициализация после загрузки DOM.
 */
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTooltips);
  } else {
    initTooltips();
  }
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initTooltips = initTooltips;
}

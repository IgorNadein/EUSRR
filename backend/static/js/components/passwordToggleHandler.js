/**
 * @module passwordToggleHandler
 * @description Обработчик переключения видимости полей пароля (показать/скрыть).
 * Работает с иконками Bootstrap Icons (bi-eye / bi-eye-slash).
 * 
 * Пример HTML:
 * <div class="position-relative">
 *   <input type="password" id="password1">
 *   <span class="password-toggle" data-target="#password1">
 *     <i class="bi bi-eye-slash"></i>
 *   </span>
 * </div>
 * 
 * Использование:
 * import { initPasswordToggle } from './passwordToggleHandler.js';
 * initPasswordToggle();
 */

/**
 * Переключает тип поля ввода между 'password' и 'text' и меняет иконку.
 * @param {HTMLElement} toggleElement - Элемент с классом .password-toggle
 */
function togglePasswordVisibility(toggleElement) {
  const targetSelector = toggleElement.getAttribute('data-target');
  if (!targetSelector) return;

  const input = document.querySelector(targetSelector);
  if (!input) return;

  // Переключаем тип поля
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';

  // Переключаем иконку
  const icon = toggleElement.querySelector('i');
  if (icon) {
    icon.classList.toggle('bi-eye', isPassword);
    icon.classList.toggle('bi-eye-slash', !isPassword);
  }
}

/**
 * Инициализирует обработчики для всех элементов с классом .password-toggle.
 * @param {Object} options - Опции инициализации
 * @param {string} [options.selector='.password-toggle'] - CSS-селектор для элементов переключения
 * @returns {Function} destroy - Функция для удаления обработчиков
 */
export function initPasswordToggle(options = {}) {
  const { selector = '.password-toggle' } = options;

  /**
   * Обработчик клика по иконке переключения пароля
   * @param {Event} e - Событие клика
   */
  const handleClick = (e) => {
    const toggleElement = e.target.closest(selector);
    if (!toggleElement) return;

    togglePasswordVisibility(toggleElement);
  };

  // Используем делегирование событий
  document.addEventListener('click', handleClick);

  /**
   * Функция для удаления обработчиков
   */
  const destroy = () => {
    document.removeEventListener('click', handleClick);
  };

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initPasswordToggle = initPasswordToggle;
}

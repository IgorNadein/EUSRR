/**
 * @module themeToggleHandler
 * @description Обработчик переключения темы оформления (светлая/тёмная/авто).
 * Сохраняет выбор в localStorage, синхронизируется с системными настройками в режиме "авто".
 * 
 * Пример HTML:
 * <button class="js-theme-btn" data-mode="auto">
 *   <i class="bi bi-circle-half"></i>
 *   <span class="mode-label">Авто</span>
 * </button>
 * 
 * Использование:
 * import { initThemeToggle } from './themeToggleHandler.js';
 * initThemeToggle();
 */

const THEME_MODES = ['light', 'auto', 'dark'];
const THEME_ICONS = {
  light: 'bi-sun-fill',
  auto: 'bi-circle-half',
  dark: 'bi-moon-stars'
};
const THEME_LABELS = {
  light: 'Светлая',
  auto: 'Авто',
  dark: 'Темная'
};

/**
 * Получает сохранённый режим темы из localStorage.
 * @returns {string} Режим темы ('light', 'auto', 'dark')
 */
function getSavedMode() {
  try {
    return localStorage.getItem('theme') || 'auto';
  } catch (e) {
    return 'auto';
  }
}

/**
 * Сохраняет режим темы в localStorage.
 * @param {string} mode - Режим темы
 */
function setSavedMode(mode) {
  try {
    localStorage.setItem('theme', mode);
  } catch (e) {
    console.warn('Не удалось сохранить тему:', e);
  }
}

/**
 * Определяет эффективную тему (светлая или тёмная) на основе режима.
 * @param {string} mode - Режим темы ('light', 'auto', 'dark')
 * @param {MediaQueryList} mediaQuery - Media query для определения системной темы
 * @returns {string} 'light' или 'dark'
 */
function getEffectiveTheme(mode, mediaQuery) {
  if (mode === 'auto') {
    return mediaQuery.matches ? 'dark' : 'light';
  }
  return mode;
}

/**
 * Получает следующий режим в цикле light → auto → dark → light.
 * @param {string} currentMode - Текущий режим
 * @returns {string} Следующий режим
 */
function getNextMode(currentMode) {
  const currentIndex = THEME_MODES.indexOf(currentMode);
  const validIndex = currentIndex >= 0 ? currentIndex : 0;
  const nextIndex = (validIndex + 1) % THEME_MODES.length;
  return THEME_MODES[nextIndex];
}

/**
 * Инициализирует переключатель темы оформления.
 * @param {Object} options - Опции инициализации
 * @param {string} [options.buttonSelector='.js-theme-btn'] - CSS-селектор кнопок переключения
 * @param {string} [options.storageKey='theme'] - Ключ для localStorage
 * @returns {Object} API с методами setMode, getMode, destroy
 */
export function initThemeToggle(options = {}) {
  const {
    buttonSelector = '.js-theme-btn',
    storageKey = 'theme'
  } = options;

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const root = document.documentElement;

  /**
   * Обновляет внешний вид кнопок переключателя темы.
   * @param {string} mode - Текущий режим темы
   */
  function updateButtons(mode) {
    document.querySelectorAll(buttonSelector).forEach(button => {
      const icon = button.querySelector('.bi');
      const label = button.querySelector('.mode-label');

      // Обновляем иконку
      if (icon) {
        icon.className = 'bi ' + (THEME_ICONS[mode] || THEME_ICONS.auto);
      }

      // Обновляем текст
      if (label) {
        label.textContent = THEME_LABELS[mode] || THEME_LABELS.auto;
      }

      // Обновляем data-атрибуты и accessibility
      button.dataset.mode = mode;
      const labelText = THEME_LABELS[mode] || THEME_LABELS.auto;
      button.title = `Тема: ${labelText}. Нажмите, чтобы переключить`;
      button.setAttribute('aria-label', `Тема: ${labelText}. Нажмите, чтобы переключить`);
    });
  }

  /**
   * Применяет режим темы к документу.
   * @param {string} mode - Режим темы
   * @param {boolean} persist - Сохранять ли выбор в localStorage
   */
  function applyMode(mode, persist = true) {
    const effectiveTheme = getEffectiveTheme(mode, mediaQuery);
    root.setAttribute('data-bs-theme', effectiveTheme);

    if (persist) {
      setSavedMode(mode);
    }

    updateButtons(mode);
  }

  /**
   * Обработчик клика по кнопке переключения темы.
   * @param {Event} event - Событие клика
   */
  function handleButtonClick(event) {
    const button = event.target.closest(buttonSelector);
    if (!button) return;

    event.preventDefault();

    const currentMode = button.dataset.mode || getSavedMode();
    const nextMode = getNextMode(currentMode);
    applyMode(nextMode, true);
  }

  /**
   * Обработчик изменения системной темы.
   * Обновляет тему только если выбран режим "авто".
   */
  function handleMediaQueryChange() {
    if (getSavedMode() === 'auto') {
      applyMode('auto', false);
    }
  }

  /**
   * Обработчик DOMContentLoaded для начальной установки темы.
   */
  function handleDOMContentLoaded() {
    const savedMode = getSavedMode();
    applyMode(savedMode, false);
  }

  // Установка обработчиков
  document.addEventListener('DOMContentLoaded', handleDOMContentLoaded);
  document.body.addEventListener('click', handleButtonClick);
  mediaQuery.addEventListener('change', handleMediaQueryChange);

  // Немедленная установка темы (если DOM уже загружен)
  if (document.readyState !== 'loading') {
    handleDOMContentLoaded();
  }

  /**
   * Функция для удаления всех обработчиков.
   */
  function destroy() {
    document.removeEventListener('DOMContentLoaded', handleDOMContentLoaded);
    document.body.removeEventListener('click', handleButtonClick);
    mediaQuery.removeEventListener('change', handleMediaQueryChange);
  }

  return {
    /**
     * Программно устанавливает режим темы.
     * @param {string} mode - Режим темы ('light', 'auto', 'dark')
     */
    setMode: (mode) => {
      if (THEME_MODES.includes(mode)) {
        applyMode(mode, true);
      }
    },

    /**
     * Получает текущий режим темы.
     * @returns {string} Текущий режим
     */
    getMode: getSavedMode,

    destroy
  };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initThemeToggle = initThemeToggle;
}

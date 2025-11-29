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
   * Обновляет тему для всех emoji picker на странице.
   * @param {string} theme - 'light' или 'dark'
   */
  function updateEmojiPickerTheme(theme) {
    const isDark = theme === 'dark';
    
    // Получаем все emoji picker элементы
    const pickers = document.querySelectorAll('emoji-picker');
    
    pickers.forEach(picker => {
      // Устанавливаем CSS-переменные для emoji-picker-element
      if (isDark) {
        // Темная тема
        picker.style.setProperty('--background', '#212529');
        picker.style.setProperty('--rgb-background', '33, 37, 41');
        picker.style.setProperty('--color', '#dee2e6');
        picker.style.setProperty('--rgb-color', '222, 226, 230');
        picker.style.setProperty('--secondary-color', '#adb5bd');
        picker.style.setProperty('--rgb-accent', '13, 110, 253');
        picker.style.setProperty('--border-color', 'rgba(255, 255, 255, 0.1)');
        picker.style.setProperty('--input-border-color', 'rgba(255, 255, 255, 0.15)');
        picker.style.setProperty('--input-background', '#343a40');
        picker.style.setProperty('--hover-background', '#343a40');
      } else {
        // Светлая тема
        picker.style.setProperty('--background', '#ffffff');
        picker.style.setProperty('--rgb-background', '255, 255, 255');
        picker.style.setProperty('--color', '#212529');
        picker.style.setProperty('--rgb-color', '33, 37, 41');
        picker.style.setProperty('--secondary-color', '#6c757d');
        picker.style.setProperty('--rgb-accent', '13, 110, 253');
        picker.style.setProperty('--border-color', 'rgba(0, 0, 0, 0.08)');
        picker.style.setProperty('--input-border-color', 'rgba(0, 0, 0, 0.1)');
        picker.style.setProperty('--input-background', '#f8f9fa');
        picker.style.setProperty('--hover-background', '#f8f9fa');
      }
      
      // Инжектим стили скроллбара в Shadow DOM
      if (picker.shadowRoot) {
        // Проверяем, не добавлены ли уже стили
        let styleEl = picker.shadowRoot.querySelector('#custom-scrollbar-styles');
        if (!styleEl) {
          styleEl = document.createElement('style');
          styleEl.id = 'custom-scrollbar-styles';
          picker.shadowRoot.appendChild(styleEl);
        }
        
        // Устанавливаем стили скроллбара в зависимости от темы
        const scrollbarColor = isDark ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)';
        const scrollbarBg = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
        
        styleEl.textContent = `
          .tabpanel {
            scrollbar-width: thin;
            scrollbar-color: ${scrollbarColor} ${scrollbarBg};
          }
          .tabpanel::-webkit-scrollbar {
            width: 8px;
          }
          .tabpanel::-webkit-scrollbar-track {
            background: ${scrollbarBg};
          }
          .tabpanel::-webkit-scrollbar-thumb {
            background: ${scrollbarColor};
            border-radius: 4px;
          }
          .tabpanel::-webkit-scrollbar-thumb:hover {
            background: ${isDark ? 'rgba(255, 255, 255, 0.4)' : 'rgba(0, 0, 0, 0.4)'};
          }
        `;
      }
    });
  }

  /**
   * Создаёт наблюдатель за добавлением новых emoji picker на страницу.
   */
  function setupEmojiPickerObserver() {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) { // Element node
            // Проверяем сам элемент
            if (node.tagName === 'EMOJI-PICKER') {
              const currentTheme = getEffectiveTheme(getSavedMode(), mediaQuery);
              updateEmojiPickerTheme(currentTheme);
            }
            // Проверяем дочерние элементы
            const emojiPickers = node.querySelectorAll?.('emoji-picker');
            if (emojiPickers?.length > 0) {
              const currentTheme = getEffectiveTheme(getSavedMode(), mediaQuery);
              updateEmojiPickerTheme(currentTheme);
            }
          }
        });
      });
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    return observer;
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
    
    // Обновляем тему для emoji picker
    updateEmojiPickerTheme(effectiveTheme);
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
    
    // Инициализируем наблюдатель за новыми emoji picker
    setupEmojiPickerObserver();
  }

  // Установка обработчиков
  document.addEventListener('DOMContentLoaded', handleDOMContentLoaded);
  document.body.addEventListener('click', handleButtonClick);
  mediaQuery.addEventListener('change', handleMediaQueryChange);

  // Немедленная установка темы (если DOM уже загружен)
  if (document.readyState !== 'loading') {
    handleDOMContentLoaded();
  }

  // Создаём переменную для хранения observer
  let emojiObserver = null;
  
  /**
   * Функция для удаления всех обработчиков.
   */
  function destroy() {
    document.removeEventListener('DOMContentLoaded', handleDOMContentLoaded);
    document.body.removeEventListener('click', handleButtonClick);
    mediaQuery.removeEventListener('change', handleMediaQueryChange);
    
    // Отключаем наблюдатель
    if (emojiObserver) {
      emojiObserver.disconnect();
    }
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

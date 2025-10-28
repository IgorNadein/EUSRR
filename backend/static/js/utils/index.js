/**
 * JavaScript Utilities Index
 * 
 * Этот файл служит единой точкой входа для всех JS утилит.
 * Экспортирует все утилиты для удобного импорта.
 * 
 * Использование в шаблонах:
 * <script type="module">
 *   import { esc, norm, debounce } from '{% static "js/utils/index.js" %}';
 * </script>
 * 
 * Или импорт конкретной утилиты:
 * import { esc } from '{% static "js/utils/stringUtils.js" %}';
 */

// Утилиты работы со строками
export { 
  esc, 
  norm, 
  escAttr, 
  truncate, 
  getInitials 
} from './stringUtils.js';

// Утилиты для работы со временем
export { 
  debounce, 
  throttle, 
  delay, 
  poll, 
  once 
} from './timing.js';

// Утилиты прокрутки
export { 
  smoothScrollTo, 
  scrollToTop, 
  scrollToBottom,
  isElementInViewport,
  getScrollPosition,
  onScrollThreshold
} from './scroll.js';

// Версия утилит
export const UTILS_VERSION = '1.0.0';

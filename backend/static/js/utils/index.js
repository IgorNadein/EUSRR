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

// Утилиты работы со строками (будут созданы в Фазе 2)
// export { esc, norm } from './stringUtils.js';

// Утилиты для работы со временем (будут созданы в Фазе 2)
// export { debounce, throttle } from './timing.js';

// Утилиты прокрутки (будут созданы в Фазе 2)
// export { smoothScrollTo } from './scroll.js';

// Placeholder export для валидности модуля
export const UTILS_VERSION = '1.0.0';

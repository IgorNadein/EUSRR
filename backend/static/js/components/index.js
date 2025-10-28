/**
 * JavaScript Components Index
 * 
 * Этот файл служит единой точкой входа для всех JS компонентов.
 * Экспортирует все компоненты для удобного импорта.
 * 
 * Использование в шаблонах:
 * <script type="module">
 *   import { EmployeeForm, CalendarWidget } from '{% static "js/components/index.js" %}';
 * </script>
 */

// Компоненты фильтрации
export { 
  ListFilter, 
  createDataAttrMatcher, 
  createSelectorMatcher 
} from './listFilter.js';

// Компоненты форм (будут созданы в Фазе 4)
// export { EmployeeForm } from './employeeForm.js';

// Компоненты календаря (будут созданы в Фазе 4)
// export { CalendarWidget } from './calendarWidget.js';

// Компоненты отображения (будут созданы в Фазе 4)
// export { TeamWheel } from './teamWheel.js';

// Версия компонентов
export const COMPONENTS_VERSION = '1.0.0';

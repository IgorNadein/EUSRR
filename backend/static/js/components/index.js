/**
 * JavaScript Components Index
 * 
 * Этот файл служит единой точкой входа для всех JS компонентов.
 * Экспортирует все компоненты для удобного импорта.
 * 
 * Использование в шаблонах:
 * <script type="module">
 *   import { initEmployeeForm, initCalendarWidget } from '{% static "js/components/index.js" %}';
 * </script>
 */

// Компоненты фильтрации
export { 
  ListFilter, 
  createDataAttrMatcher, 
  createSelectorMatcher 
} from './listFilter.js';

// Компоненты календаря
export { initCalendarWidget } from './calendarWidget.js';

// Компоненты отображения
export { initTeamWheel } from './teamWheel.js';

// Компоненты управления формой сотрудника
export { initEmployeeForm } from './employeeFormHandler.js';
export { initPositionManager } from './positionManager.js';
export { initPositionGroupPicker, initPositionEditGroupPicker } from './groupPickers.js';
export { initEmployeeGroupsManager } from './employeeGroupsManager.js';

// Версия компонентов
export const COMPONENTS_VERSION = '1.2.0';

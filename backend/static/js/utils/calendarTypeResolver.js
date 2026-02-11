/**
 * @fileoverview Calendar type resolver - определение типа календаря и параметров запросов
 * @module utils/calendarTypeResolver
 */

import {
  CALENDAR_TYPES,
  isLegacyCalendar,
  getLegacyCalendarType,
  extractDepartmentId,
} from '../constants/calendarTypes.js';

/**
 * Получить ID текущего пользователя из meta-тега
 * @returns {number|null} ID пользователя или null
 * @private
 */
function getCurrentEmployeeId() {
  const userMeta = document.querySelector('meta[name="user-id"]');
  return userMeta ? parseInt(userMeta.content, 10) : null;
}

/**
 * Определить параметры для загрузки событий на основе ID календаря
 * @param {string|number} calendarId - ID календаря (legacy или новый)
 * @param {Object} baseParams - Базовые параметры (start, end)
 * @returns {Object} Параметры для API запроса
 */
export function resolveCalendarParams(calendarId, baseParams = {}) {
  const params = { ...baseParams };

  // Legacy календари
  if (isLegacyCalendar(calendarId)) {
    const type = getLegacyCalendarType(calendarId);

    switch (type) {
      case CALENDAR_TYPES.COMPANY:
        // Компания: без дополнительных параметров (все события)
        break;

      case CALENDAR_TYPES.PERSONAL:
        // Личный: фильтр по employee_id
        const employeeId = getCurrentEmployeeId();
        if (employeeId) {
          params.employee_id = employeeId;
        }
        break;

      case CALENDAR_TYPES.DEPARTMENT:
        // Отдел: фильтр по department_id
        const deptId = extractDepartmentId(calendarId);
        if (deptId) {
          params.department_id = deptId;
        }
        break;
    }
  } else if (typeof calendarId === 'number') {
    // Новый календарь: используем calendar_id
    params.calendar_id = calendarId;
  }

  return params;
}

/**
 * Определить payload для создания/обновления события в календаре
 * @param {string|number} calendarId - ID календаря
 * @param {Object} eventData - Данные события
 * @returns {Object} Payload для API запроса
 */
export function resolveEventPayload(calendarId, eventData) {
  const payload = { ...eventData };

  // Очищаем все специфичные поля календаря
  delete payload.employee_id;
  delete payload.department_id;
  delete payload.calendar_id;

  // Legacy календари
  if (isLegacyCalendar(calendarId)) {
    const type = getLegacyCalendarType(calendarId);

    switch (type) {
      case CALENDAR_TYPES.COMPANY:
        // Компания: без дополнительных полей
        break;

      case CALENDAR_TYPES.PERSONAL:
        // Личный: добавляем employee_id
        const employeeId = getCurrentEmployeeId();
        if (employeeId) {
          payload.employee_id = employeeId;
        }
        break;

      case CALENDAR_TYPES.DEPARTMENT:
        // Отдел: добавляем department_id
        const deptId = extractDepartmentId(calendarId);
        if (deptId) {
          payload.department_id = deptId;
        }
        break;
    }
  } else if (typeof calendarId === 'number') {
    // Новый календарь: добавляем calendar_id
    payload.calendar_id = calendarId;
  }

  return payload;
}

/**
 * Получить человекочитаемое имя типа календаря
 * @param {string|number} calendarId - ID календаря
 * @param {Array} [calendars] - Список календарей для поиска
 * @returns {string} Название типа
 */
export function getCalendarTypeName(calendarId, calendars = []) {
  if (isLegacyCalendar(calendarId)) {
    const type = getLegacyCalendarType(calendarId);
    switch (type) {
      case CALENDAR_TYPES.COMPANY:
        return 'Компания';
      case CALENDAR_TYPES.PERSONAL:
        return 'Личный календарь';
      case CALENDAR_TYPES.DEPARTMENT:
        return 'Календарь отдела';
      default:
        return 'Календарь';
    }
  }

  // Ищем в списке календарей
  const calendar = calendars.find((c) => c.id === calendarId);
  return calendar?.title || 'Календарь';
}

/**
 * Проверить может ли пользователь редактировать календарь
 * @param {string|number} calendarId - ID календаря
 * @param {Array} [calendars] - Список календарей
 * @returns {boolean} True если может редактировать
 */
export function canEditCalendar(calendarId, calendars = []) {
  if (calendarId === CALENDAR_TYPES.LEGACY_COMPANY) {
    // Компания: определяется правами на backend
    return false; // По умолчанию нет
  }

  if (calendarId === CALENDAR_TYPES.LEGACY_PERSONAL) {
    // Личный: всегда может редактировать
    return true;
  }

  if (typeof calendarId === 'string' && calendarId.startsWith(CALENDAR_TYPES.LEGACY_DEPT_PREFIX)) {
    // Отдел: определяется правами на backend
    return false; // По умолчанию нет
  }

  // Новый календарь: проверяем в списке
  const calendar = calendars.find((c) => c.id === calendarId);
  return calendar?.user_can_edit || false;
}

/**
 * Валидация ID календаря
 * @param {string|number} calendarId - ID календаря
 * @returns {boolean} True если ID валиден
 */
export function isValidCalendarId(calendarId) {
  if (!calendarId) return false;

  // Legacy календари
  if (typeof calendarId === 'string') {
    return (
      calendarId === CALENDAR_TYPES.LEGACY_COMPANY ||
      calendarId === CALENDAR_TYPES.LEGACY_PERSONAL ||
      calendarId.startsWith(CALENDAR_TYPES.LEGACY_DEPT_PREFIX)
    );
  }

  // Новые календари (числовой ID)
  return typeof calendarId === 'number' && calendarId > 0;
}

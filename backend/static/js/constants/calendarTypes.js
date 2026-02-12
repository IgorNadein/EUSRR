/**
 * @fileoverview Calendar type constants - константы типов календарей
 * @module constants/calendarTypes
 */

/**
 * Типы календарей в системе
 * @enum {string}
 */
export const CALENDAR_TYPES = {
  // Legacy типы (старая система)
  LEGACY_COMPANY: "legacy-company",
  LEGACY_PERSONAL: "legacy-personal",
  LEGACY_DEPT_PREFIX: "legacy-dept-",

  // Новые типы (Calendar model)
  COMPANY: "company",
  PERSONAL: "personal",
  DEPARTMENT: "department",
  PUBLIC: "public",
  PRIVATE: "private",
  CUSTOM: "custom",
};

/**
 * Цвета календарей по умолчанию
 * @enum {string}
 */
export const CALENDAR_COLORS = {
  COMPANY: "#dc3545", // красный
  PERSONAL: "#0d6efd", // синий
  DEPARTMENT: "#198754", // зелёный
  PUBLIC: "#6c757d", // серый
  DEFAULT: "#0d6efd", // синий (по умолчанию)
};

/**
 * Проверить является ли ID legacy календарём
 * @param {string|number} id - ID календаря
 * @returns {boolean} True если это legacy календарь
 */
export function isLegacyCalendar(id) {
  if (typeof id !== "string") return false;
  return (
    id === CALENDAR_TYPES.LEGACY_COMPANY ||
    id === CALENDAR_TYPES.LEGACY_PERSONAL ||
    id.startsWith(CALENDAR_TYPES.LEGACY_DEPT_PREFIX)
  );
}

/**
 * Получить тип legacy календаря по ID
 * @param {string} id - Legacy ID календаря
 * @returns {string|null} Тип календаря или null
 */
export function getLegacyCalendarType(id) {
  if (id === CALENDAR_TYPES.LEGACY_COMPANY) return CALENDAR_TYPES.COMPANY;
  if (id === CALENDAR_TYPES.LEGACY_PERSONAL) return CALENDAR_TYPES.PERSONAL;
  if (id.startsWith(CALENDAR_TYPES.LEGACY_DEPT_PREFIX))
    return CALENDAR_TYPES.DEPARTMENT;
  return null;
}

/**
 * Извлечь ID отдела из legacy ID
 * @param {string} legacyId - Legacy ID отдела
 * @returns {number|null} ID отдела или null
 */
export function extractDepartmentId(legacyId) {
  if (!legacyId.startsWith(CALENDAR_TYPES.LEGACY_DEPT_PREFIX)) return null;
  const id = parseInt(
    legacyId.replace(CALENDAR_TYPES.LEGACY_DEPT_PREFIX, ""),
    10,
  );
  return isNaN(id) ? null : id;
}

/**
 * Создать legacy ID для отдела
 * @param {number} departmentId - ID отдела
 * @returns {string} Legacy ID
 */
export function createLegacyDeptId(departmentId) {
  return `${CALENDAR_TYPES.LEGACY_DEPT_PREFIX}${departmentId}`;
}

/**
 * @fileoverview Date utilities - работа с датами и временем
 * @module utils/dateUtils
 */

/**
 * Дополнить число нулём до двух символов
 * @param {number} n - Число
 * @returns {string} Строка с ведущим нулём
 * @private
 */
function pad(n) {
  return String(n).padStart(2, "0");
}

/**
 * Форматировать дату в формат YYYY-MM-DD
 * @param {Date} date - Объект Date
 * @returns {string} Дата в формате YYYY-MM-DD
 */
export function formatDate(date) {
  const y = date.getFullYear();
  const m = pad(date.getMonth() + 1);
  const d = pad(date.getDate());
  return `${y}-${m}-${d}`;
}

/**
 * Форматировать дату в локальный формат YYYY-MM-DD (без UTC)
 * @param {Date} date - Объект Date
 * @returns {string} Дата в формате YYYY-MM-DD
 */
export function ymdLocal(date) {
  const y = date.getFullYear();
  const m = pad(date.getMonth() + 1);
  const d = pad(date.getDate());
  return `${y}-${m}-${d}`;
}

/**
 * Форматировать дату для отображения пользователю
 * @param {Date|string} date - Дата
 * @returns {string} Дата в формате ДД.ММ.ГГГГ
 */
export function fmtDate(date) {
  const d = typeof date === "string" ? new Date(date) : date;
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/**
 * Форматировать время для отображения пользователю
 * @param {Date|string} date - Дата/время
 * @returns {string} Время в формате ЧЧ:ММ
 */
export function fmtTime(date) {
  const d = typeof date === "string" ? new Date(date) : date;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Форматировать период события для отображения
 * @param {Object} event - Объект события
 * @param {string} event.start_date - Дата начала
 * @param {string} event.end_date - Дата окончания
 * @param {string} [event.start_time] - Время начала
 * @param {string} [event.end_time] - Время окончания
 * @param {boolean} [event.all_day] - Флаг целодневного события
 * @returns {string} Форматированная строка периода
 */
export function formatEventPeriod(event) {
  const start = fmtDate(event.start_date);
  const end = fmtDate(event.end_date);

  if (event.all_day) {
    return start === end ? start : `${start} — ${end}`;
  }

  const startTime = event.start_time || "00:00";
  const endTime = event.end_time || "23:59";

  if (start === end) {
    return `${start} ${startTime} — ${endTime}`;
  }

  return `${start} ${startTime} — ${end} ${endTime}`;
}

/**
 * Добавить параметры диапазона дат к URL
 * @param {URL} url - URL объект
 * @param {Date} start - Начало периода
 * @param {Date} end - Конец периода
 * @returns {URL} URL с добавленными параметрами
 */
export function addDateRangeToUrl(url, start, end) {
  url.searchParams.set("start", formatDate(start));
  url.searchParams.set("end", formatDate(end));
  return url;
}

/**
 * Парсить дату из строки в формате YYYY-MM-DD
 * @param {string} dateStr - Строка даты
 * @returns {Date|null} Объект Date или null если невалидная дата
 */
export function parseDate(dateStr) {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  return isNaN(date.getTime()) ? null : date;
}

/**
 * Получить начало дня для даты
 * @param {Date} date - Дата
 * @returns {Date} Дата с временем 00:00:00
 */
export function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

/**
 * Получить конец дня для даты
 * @param {Date} date - Дата
 * @returns {Date} Дата с временем 23:59:59
 */
export function endOfDay(date) {
  const d = new Date(date);
  d.setHours(23, 59, 59, 999);
  return d;
}

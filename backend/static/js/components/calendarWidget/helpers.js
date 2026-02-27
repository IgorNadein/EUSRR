/**
 * helpers.js
 * Вспомогательные утилиты для календаря
 * @module calendarWidget/helpers
 */

import { ymdLocal, fmtDate, fmtTime } from "../../utils/dateUtils.js";
import { API_URLS } from "../../constants/apiUrls.js";

/* ===== Константы ===== */
export const DIGITS_RE = /^\d+$/;
export const dayMs = 86400000;
export const hourMs = 3600000;

/**
 * Извлечь числовой PK отдела из объекта
 * @param {Object} d - Объект отдела
 * @returns {string|null} - Числовой ID или null
 */
export function extractNumericPk(d) {
  const cands = [d?.pk, d?.id, d?.department_id];
  for (const v of cands) {
    const s = String(v ?? "").trim();
    if (s && DIGITS_RE.test(s)) return s;
  }
  return null;
}

/**
 * Построить URL событий с фильтрами по отделу или сотруднику
 * @param {number|null} deptId - ID отдела
 * @param {number|null} employeeId - ID сотрудника
 * @returns {string} - URL с query параметрами
 */
export function eventsUrl(deptId = null, employeeId = null) {
  const u = new URL(API_URLS.EVENTS, location.origin);
  if (employeeId != null) {
    u.searchParams.set("employee_id", String(employeeId));
  } else if (deptId != null) {
    u.searchParams.set("department_id", String(deptId));
  }
  return u.pathname + (u.search ? "?" + u.searchParams.toString() : "");
}

/**
 * Добавить диапазон дат к URL
 * @param {string} url - Базовый URL
 * @param {Date} start - Начальная дата
 * @param {Date} end - Конечная дата
 * @returns {string} - URL с датами
 */
export function addRange(url, start, end) {
  const u = new URL(url, location.origin);
  u.searchParams.set("start", ymdLocal(start));
  u.searchParams.set("end", ymdLocal(end));
  return u.pathname + "?" + u.searchParams.toString();
}

/**
 * Проверка, что строка - это дата без времени (YYYY-MM-DD)
 * @param {*} v - Значение для проверки
 * @returns {boolean}
 */
export const isDateOnly = (v) =>
  typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);

/**
 * Преобразовать любое значение в Date
 * @param {*} v - Значение (string, number, Date)
 * @returns {Date|null}
 */
export const toDate = (v) => {
  if (!v) return null;
  if (v instanceof Date) return v;
  if (typeof v === "number") return new Date(v);
  if (typeof v === "string") {
    const s = v.trim();
    if (isDateOnly(s)) {
      const [y, m, d] = s.split("-").map(Number);
      return new Date(y, m - 1, d);
    }
    const t = Date.parse(s);
    if (!isNaN(t)) return new Date(t);
  }
  return null;
};

/**
 * Выбрать первое непустое значение из объекта по ключам
 * @param {Object} o - Объект
 * @param {string[]} ks - Массив ключей
 * @returns {*} - Первое найденное значение или null
 */
export const pick = (o, ks) => {
  for (const k of ks) if (o && o[k] != null && o[k] !== "") return o[k];
  return null;
};

/**
 * Начало недели (понедельник)
 * @param {Date} d - Дата
 * @returns {Date}
 */
export const startOfWeek = (d) => {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const day = (x.getDay() + 6) % 7;
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
};

/**
 * Конец недели (следующий понедельник)
 * @param {Date} d - Дата
 * @returns {Date}
 */
export const endOfWeek = (d) => {
  const s = startOfWeek(d);
  const e = new Date(s);
  e.setDate(s.getDate() + 7);
  return e;
};

/**
 * Проверка пересечения события с диапазоном дат
 * @param {Object} ev - Событие с полями start, end
 * @param {Date} ws - Начало диапазона
 * @param {Date} we - Конец диапазона
 * @returns {boolean}
 */
export const overlaps = (ev, ws, we) => ev.start < we && ev.end > ws;

/**
 * Обрезать строку до указанной длины
 * @param {string} s - Строка
 * @param {number} n - Максимальная длина (по умолчанию 20)
 * @returns {string}
 */
export const truncate = (s, n = 20) => {
  const t = (s ?? "").toString();
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
};

/**
 * Установить чекбоксы дней недели из маски (битовое число)
 * @param {number} mask - Битовая маска (0-127)
 */
export function setWeekdaysFromMask(mask) {
  try {
    const m = Number(mask) || 0;
    for (let i = 0; i <= 6; i++) {
      const el = document.getElementById("wd" + i);
      if (el) el.checked = !!(m & (1 << i));
    }
  } catch (_) {}
}

/**
 * Форматировать период события для отображения
 * @param {Object} ev - Событие
 * @returns {string} - Форматированная строка даты/времени
 */
export function fmtWhen(ev) {
  if (!ev) return "—";
  const allDay = !!ev.all_day;
  const sd = toDate(ev.start || ev.start_date);
  const ed = ev.end || ev.end_date ? toDate(ev.end || ev.end_date) : null;
  if (allDay) {
    if (ed && fmtDate(sd) !== fmtDate(ed))
      return `${fmtDate(sd)} — ${fmtDate(ed)} (весь день)`;
    return `${fmtDate(sd)} (весь день)`;
  }
  if (ed)
    return `${fmtDate(sd)} ${fmtTime(sd)} — ${fmtDate(ed)} ${fmtTime(ed)}`;
  return `${fmtDate(sd)} ${fmtTime(sd)}`;
}

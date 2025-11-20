/**
 * @fileoverview Chat Message Templates - HTML шаблоны для рендеринга сообщений чата
 * @module components/chatMessageTemplates
 */

import { esc } from '../utils/stringUtils.js';

/**
 * Дополняет число нулём слева
 * @param {number} n - Число
 * @returns {string} Строка с ведущим нулём
 */
const z2 = n => (n < 10 ? '0' : '') + n;

/**
 * Извлекает timestamp из сообщения
 * @param {Object} msg - Объект сообщения
 * @returns {number} Unix timestamp в миллисекундах
 */
export function toTimestamp(msg) {
  if (msg && msg.created_ts != null && !isNaN(Number(msg.created_ts))) {
    return Number(msg.created_ts);
  }
  if (msg && msg.created) {
    const t = Date.parse(msg.created);
    if (!isNaN(t)) return t;
  }
  return Date.now();
}

/**
 * Форматирует timestamp в HH:MM
 * @param {number} ts - Unix timestamp
 * @returns {string} Время в формате HH:MM
 */
export function formatTime(ts) {
  const d = new Date(ts);
  return `${z2(d.getHours())}:${z2(d.getMinutes())}`;
}

/**
 * Форматирует timestamp в DD.MM.YYYY
 * @param {number} ts - Unix timestamp
 * @returns {string} Дата в формате DD.MM.YYYY
 */
export function formatDay(ts) {
  const d = new Date(ts);
  return `${z2(d.getDate())}.${z2(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/**
 * Создаёт HTML для аватара
 * @param {string} url - URL аватара
 * @returns {string} HTML аватара
 */
export function avatarHTML(url) {
  return url
    ? `<span class="mini-ava border"><img src="${url}" alt="" loading="lazy"></span>`
    : `<span class="mini-ava border d-inline-grid"><i class="bi-person"></i></span>`;
}

/**
 * Создаёт HTML для имени пользователя с ссылкой
 * @param {number|string} userId - ID пользователя
 * @param {string} name - Имя пользователя
 * @param {string} url - URL профиля
 * @param {number|string} meId - ID текущего пользователя
 * @param {string} profileUrl - URL профиля текущего пользователя
 * @param {string} detailUrlTemplate - Шаблон URL деталей сотрудника
 * @returns {string} HTML имени с ссылкой
 */
export function nameHTML(userId, name, url, meId, profileUrl, detailUrlTemplate) {
  if (Number(userId) === Number(meId)) {
    return `<a href="${profileUrl}" class="text-decoration-none">Вы</a>`;
  }
  if (url) {
    return `<a href="${url}" class="text-decoration-none fw-semibold">${esc(name || 'Сотрудник')}</a>`;
  }
  const detailUrl = detailUrlTemplate.replace('/0/', `/${userId}/`);
  return `<a href="${detailUrl}" class="text-decoration-none fw-semibold">${esc(name || 'Сотрудник')}</a>`;
}

/**
 * Создаёт разделитель дня
 * @param {string} dateStr - Дата в текстовом формате
 * @returns {HTMLElement} DOM элемент разделителя
 */
export function createDayDivider(dateStr) {
  const div = document.createElement('div');
  div.className = 'day-divider';
  div.innerHTML = `<span>${esc(dateStr)}</span>`;
  return div;
}

/**
 * Создаёт элемент сообщения
 * @param {Object} msg - Объект сообщения
 * @param {number|string} msg.id - ID сообщения
 * @param {number|string} msg.author_id - ID автора
 * @param {string} msg.author_name - Имя автора
 * @param {string} msg.author - Альтернативное имя автора
 * @param {string} msg.author_url - URL профиля автора
 * @param {string} msg.avatar - URL аватара автора
 * @param {string} msg.content - Текст сообщения
 * @param {Object} options - Опции рендеринга
 * @param {number|string} options.meId - ID текущего пользователя
 * @param {string} options.profileUrl - URL профиля текущего пользователя
 * @param {string} options.detailUrlTemplate - Шаблон URL деталей сотрудника
 * @param {Object.<string, string>} options.avatarMap - Карта аватаров
 * @returns {HTMLElement} DOM элемент сообщения
 */
export function createMessageElement(msg, options = {}) {
  const {
    meId,
    profileUrl = '/employees/profile/',
    detailUrlTemplate = '/employees/0/',
    avatarMap = {}
  } = options;

  const mine = Number(msg.author_id) === Number(meId);
  const ts = toTimestamp(msg);

  // Создание обёртки
  const wrap = document.createElement('div');
  wrap.className = `d-flex mb-3 msg ${mine ? 'justify-content-end' : 'justify-content-start'}`;
  
  if (msg.id != null) {
    wrap.setAttribute('data-id', String(msg.id));
  }
  wrap.setAttribute('data-ts', String(ts));
  wrap.setAttribute('data-author-id', String(msg.author_id || ''));

  // Формирование контента
  const who = nameHTML(
    msg.author_id,
    msg.author_name || msg.author,
    msg.author_url,
    meId,
    profileUrl,
    detailUrlTemplate
  );
  const time = formatTime(ts);
  const text = esc(msg.content || '').replace(/\n/g, '<br>');

  const bubble = `
    <div class="d-flex flex-column" style="max-width:80%;">
      <div class="small text-secondary ${mine ? 'text-end' : ''}">
        ${who} · ${time}
      </div>
      <div class="mt-1 bubble ${mine ? 'bubble-me' : 'bubble-other'}">
        ${text}
      </div>
    </div>`;

  // Аватар
  const avaUrl = msg.avatar || avatarMap[msg.author_id] || "";
  const ava = avatarHTML(avaUrl);

  // Финальная сборка
  if (!mine) {
    const link = msg.author_url || detailUrlTemplate.replace('/0/', `/${msg.author_id}/`);
    wrap.innerHTML = `<a class="me-2 text-decoration-none" href="${link}">${ava}</a>${bubble}`;
  } else {
    wrap.innerHTML = `${bubble}<a class="ms-2 text-decoration-none" href="${profileUrl}">${ava}</a>`;
  }

  return wrap;
}

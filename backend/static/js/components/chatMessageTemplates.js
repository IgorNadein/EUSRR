/**
 * @fileoverview Chat Message Templates - HTML шаблоны для рендеринга сообщений чата
 * @module components/chatMessageTemplates
 * 
 * РЕФАКТОРИНГ: Теперь использует MessageRenderer как единый источник правды
 */

import { esc } from '../utils/stringUtils.js';
import { MessageRendererV2 } from '../renderers/messageRendererV2.js';

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
 * Форматирует размер файла
 * @param {number} bytes - Размер в байтах
 * @returns {string} Размер в человекочитаемом формате
 */
export function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
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

  // Используем MessageRenderer для единообразия
  const renderer = new MessageRendererV2({
    meId,
    profileUrl,
    detailUrlTemplate,
    currentUserAvatar: avatarMap[meId] || ''
  });

  // Обогащаем сообщение аватаром из карты
  const enrichedMsg = {
    ...msg,
    avatar: msg.avatar || avatarMap[msg.author_id] || ''
  };

  const mine = Number(msg.author_id) === Number(meId);
  const isPending = Boolean(msg.is_pending);
  
  // Создание обёртки
  const wrap = document.createElement('div');
  wrap.className = `d-flex mb-3 msg ${mine ? 'justify-content-end' : 'justify-content-start'}`;
  if (isPending) {
    wrap.classList.add('message-pending');
  }
  
  if (msg.id != null) {
    wrap.setAttribute('data-id', String(msg.id));
    wrap.setAttribute('data-message-id', String(msg.id));
    const reactionsData = msg.reactions_summary || {};
    wrap.setAttribute('data-reactions', JSON.stringify(reactionsData));
  }
  
  const ts = toTimestamp(msg);
  wrap.setAttribute('data-ts', String(ts));
  wrap.setAttribute('data-author-id', String(msg.author_id || ''));
  wrap.setAttribute('data-is-edited', String(msg.is_edited || false));
  wrap.setAttribute('data-edited-at', String(msg.edited_at || ''));

  // Используем buildMessageInnerHtml из MessageRenderer для единообразного рендеринга
  const htmlContent = renderer.buildMessageInnerHtml(enrichedMsg, mine);
  
  // Добавляем статус отправки для pending сообщений
  if (isPending) {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;
    
    const bubble = tempDiv.querySelector('.bubble');
    if (bubble) {
      const pendingStatus = document.createElement('div');
      pendingStatus.className = 'message-status small text-secondary mt-2';
      pendingStatus.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Отправляем…';
      bubble.appendChild(pendingStatus);
    }
    
    wrap.innerHTML = tempDiv.innerHTML;
  } else {
    wrap.innerHTML = htmlContent;
  }

  return wrap;
}

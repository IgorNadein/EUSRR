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

  const mine = Number(msg.author_id) === Number(meId);
  const isPending = Boolean(msg.is_pending);
  const ts = toTimestamp(msg);

  // Создание обёртки
  const wrap = document.createElement('div');
  wrap.className = `d-flex mb-3 msg ${mine ? 'justify-content-end' : 'justify-content-start'}`;
  if (isPending) {
    wrap.classList.add('message-pending');
  }
  
  if (msg.id != null) {
    wrap.setAttribute('data-id', String(msg.id));
    wrap.setAttribute('data-message-id', String(msg.id));
    // Добавляем реакции если они есть
    const reactionsData = msg.reactions_summary || {};
    wrap.setAttribute('data-reactions', JSON.stringify(reactionsData));
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
  
  // Формирование информации о пересылке
  let forwardedHTML = '';
  if (msg.is_forwarded && msg.forwarded_from) {
    const fwd = msg.forwarded_from;
    const fwdAuthor = esc(fwd.author_name || 'Неизвестный');
    const fwdTime = fwd.created_at ? fwd.created_at : '';
    const fwdChat = fwd.chat_name ? ` из «${esc(fwd.chat_name)}»` : '';
    
    forwardedHTML = `
      <div class="forwarded-indicator small mb-2 d-flex align-items-center">
        <i class="bi-arrow-90deg-right me-2"></i>
        <div>
          <div>Переслано от <strong>${fwdAuthor}</strong>${fwdChat}</div>
          ${fwdTime ? `<div class="small opacity-75">${fwdTime}</div>` : ''}
        </div>
      </div>`;
  }
  
  // Формирование информации об ответе
  let replyHTML = '';
  if (msg.reply_to) {
    const reply = msg.reply_to;
    const replyAuthor = esc(reply.author_name || 'Неизвестный');
    const replyContent = esc(reply.content || '');
    const replyPreview = replyContent.substring(0, 50);
    const replyFull = replyContent.length > 50 ? replyPreview + '...' : replyPreview;
    
    replyHTML = `
      <div class="reply-indicator small mb-2" style="
        padding: 8px 12px;
        background: rgba(0, 0, 0, 0.05);
        border-left: 3px solid #007bff;
        border-radius: 4px;
        cursor: pointer;"
        data-reply-to-id="${reply.id}"
        onclick="event.stopPropagation(); const el = document.querySelector('[data-message-id=&quot;${reply.id}&quot;]'); if (el) el.scrollIntoView({behavior: 'smooth', block: 'center'});">
        <div style="display: flex; align-items: center;">
          <i class="bi-reply me-2"></i>
          <div>
            <div style="font-weight: 600; color: #007bff;">${replyAuthor}</div>
            <div style="opacity: 0.75;">${replyFull}</div>
          </div>
        </div>
      </div>`;
  }
  
  // Формирование вложений
  let attachmentsHTML = '';
  if (msg.has_attachments && msg.attachments && msg.attachments.length > 0) {
    attachmentsHTML = '<div class="message-attachments mt-2">';
    msg.attachments.forEach((att, index) => {
      attachmentsHTML += '<div class="attachment-item mb-2">';
      
      if (att.file_type === 'image') {
        attachmentsHTML += `
          <a href="${att.file_url}" target="_blank">
            <img src="${att.file_url}" 
                 alt="${esc(att.file_name)}"
                 loading="lazy"
                 class="chat-media chat-media--image rounded">
          </a>`;
      } else if (att.file_type === 'audio') {
        attachmentsHTML += `
          <audio controls class="w-100">
            <source src="${att.file_url}" type="${att.mime_type}">
          </audio>
          <div class="small text-secondary">${esc(att.file_name)}</div>`;
      } else if (att.file_type === 'video') {
        attachmentsHTML += `
          <video controls preload="metadata" playsinline class="chat-media chat-media--video">
            <source src="${att.file_url}" type="${att.mime_type || 'video/mp4'}">
            Ваш браузер не поддерживает видео.
          </video>
          <div class="small text-secondary">${esc(att.file_name)}</div>`;
      } else {
        const fileSize = att.file_size ? formatFileSize(att.file_size) : '';
        attachmentsHTML += `
          <a href="${att.file_url}" 
             class="d-flex align-items-center text-decoration-none p-2 rounded"
             download="${esc(att.file_name)}">
            <i class="bi-file-earmark fs-3 me-2"></i>
            <div>
              <div class="fw-semibold">${esc(att.file_name)}</div>
              <div class="small text-secondary">${fileSize}</div>
            </div>
          </a>`;
      }
      
      attachmentsHTML += '</div>';
    });
    attachmentsHTML += '</div>';
  }

  const pendingStatus = isPending
    ? '<div class="message-status small text-secondary mt-2"><span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Отправляем…</div>'
    : '';

  // Рендер голосования
  let pollHTML = '';
  if (msg.poll) {
    const poll = msg.poll;
    pollHTML += `
      <div class="poll-widget mt-2" data-poll-id="${poll.id}">
        <div class="poll-question mb-3">
          <strong>${esc(poll.question)}</strong>
        </div>
        <div class="poll-options">`;
    
    poll.options.forEach(option => {
      pollHTML += `
          <div class="poll-option mb-2" data-option-id="${option.id}">
            <button type="button" class="btn btn-outline-secondary btn-poll-option w-100 text-start" 
                    data-option-id="${option.id}">
              ${esc(option.text)}
            </button>
          </div>`;
    });
    
    pollHTML += `
        </div>
        <div class="poll-footer mt-3 d-flex justify-content-between align-items-center">
          <div class="small text-muted">
            ${poll.total_voters || 0} проголосовало
            ${poll.is_anonymous ? ' • Анонимное' : ''}
            ${poll.is_multiple_choice ? ' • Множественный выбор' : ''}
            ${poll.is_closed ? ' • Закрыто' : ''}
          </div>
        </div>
      </div>`;
  }

  const bubble = `
    <div class="d-flex flex-column" style="max-width:80%;">
      <div class="small text-secondary ${mine ? 'text-end' : ''}">
        ${who} · ${time}
      </div>
      <div class="mt-1 bubble ${mine ? 'bubble-me' : 'bubble-other'}">
        ${replyHTML}
        ${forwardedHTML}
        ${text ? text : ''}
        ${pollHTML}
        ${attachmentsHTML}
        ${pendingStatus}
      </div>
      <div class="message-reactions-wrapper mt-1"></div>
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

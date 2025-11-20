/**
 * @module documentAcksHandler
 * @description Обработчик модального окна ведомости ознакомлений с документом.
 * Показывает списки ознакомившихся и не ознакомившихся сотрудников с порционной загрузкой.
 * 
 * Использование:
 * import { initDocumentAcks } from './documentAcksHandler.js';
 * 
 * initDocumentAcks({
 *   apiDetailBase: '/api/v1/documents/',
 *   headers: { 'Authorization': 'Bearer TOKEN' }
 * });
 */

import { esc } from '../utils/stringUtils.js';

/**
 * Утилита для debounce (ограничение частоты вызовов функции).
 * @param {Function} fn - Функция для вызова
 * @param {number} ms - Задержка в миллисекундах
 * @returns {Function} Обёрнутая функция
 */
function debounce(fn, ms = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/**
 * Инициализирует обработчик модального окна ознакомлений.
 * @param {Object} options - Опции инициализации
 * @param {string} options.apiDetailBase - Базовый URL API документов
 * @param {Object} [options.headers={}] - HTTP заголовки для запросов
 * @param {number} [options.pageSize=100] - Количество элементов на странице
 * @returns {Object} API с методом destroy
 */
export function initDocumentAcks(options) {
  const {
    apiDetailBase,
    headers = {},
    pageSize = 100
  } = options;

  const modalElement = document.getElementById('acksModal');
  const titleElement = document.getElementById('acksDocTitle');
  const totalsElement = document.getElementById('acksTotals');
  const yesElement = document.getElementById('acksYes');
  const noElement = document.getElementById('acksNo');
  const searchElement = document.getElementById('acksSearch');

  if (!modalElement || !yesElement || !noElement || !searchElement) {
    console.warn('initDocumentAcks: обязательные элементы не найдены');
    return { destroy: () => {} };
  }

  // Состояние модалки
  const state = {
    docId: null,
    docTitle: '',
    rawYes: [],
    rawNo: [],
    filter: '',
    pageSize: pageSize,
    shownYes: 0,
    shownNo: 0
  };

  /**
   * Строит HTML элемент для одного сотрудника.
   * @param {Object} user - Объект пользователя
   * @returns {string} HTML строка
   */
  function buildItem(user) {
    const name = esc(user.display_name || user.full_name || user.email || ('#' + user.id));
    const email = user.email ? ` <small class="text-secondary">${esc(user.email)}</small>` : '';
    const when = user.acknowledged_at 
      ? ` <small class="text-secondary">(${esc(user.acknowledged_at)})</small>` 
      : '';
    
    return `<li>${name}${email}${when}</li>`;
  }

  /**
   * Применяет фильтр поиска к списку пользователей.
   * @param {Array} list - Массив пользователей
   * @param {string} term - Поисковый запрос
   * @returns {Array} Отфильтрованный массив
   */
  function applyFilter(list, term) {
    if (!term) return list;
    
    const searchTerm = term.toLowerCase();
    return list.filter(user => {
      const name = (user.display_name || user.full_name || user.email || '').toLowerCase();
      const email = (user.email || '').toLowerCase();
      return name.includes(searchTerm) || email.includes(searchTerm);
    });
  }

  /**
   * Отображает списки ознакомившихся и не ознакомившихся.
   */
  function renderLists() {
    const yesFiltered = applyFilter(state.rawYes, state.filter);
    const noFiltered = applyFilter(state.rawNo, state.filter);

    totalsElement.textContent = 
      `Ознакомились: ${yesFiltered.length} • Не ознакомились: ${noFiltered.length} • Всего: ${yesFiltered.length + noFiltered.length}`;

    // Порционное отображение
    const yesSlice = yesFiltered.slice(0, state.shownYes || state.pageSize);
    const noSlice = noFiltered.slice(0, state.shownNo || state.pageSize);

    // Отображение списка ознакомившихся
    yesElement.innerHTML = yesSlice.length
      ? `<ul class="acks-list">${yesSlice.map(buildItem).join('')}</ul>`
      : '<div class="acks-empty">— никого —</div>';

    // Отображение списка не ознакомившихся
    noElement.innerHTML = noSlice.length
      ? `<ul class="acks-list">${noSlice.map(buildItem).join('')}</ul>`
      : '<div class="acks-empty">— никого —</div>';

    // Кнопки "Показать ещё"
    const needMoreYes = yesSlice.length < yesFiltered.length;
    const needMoreNo = noSlice.length < noFiltered.length;

    if (needMoreYes) {
      const remaining = Math.min(state.pageSize, yesFiltered.length - yesSlice.length);
      const button = document.createElement('button');
      button.className = 'btn btn-sm btn-outline-secondary acks-more';
      button.textContent = `Показать ещё (${remaining})`;
      button.addEventListener('click', () => {
        state.shownYes = yesSlice.length + state.pageSize;
        renderLists();
      });
      yesElement.appendChild(button);
    }

    if (needMoreNo) {
      const remaining = Math.min(state.pageSize, noFiltered.length - noSlice.length);
      const button = document.createElement('button');
      button.className = 'btn btn-sm btn-outline-secondary acks-more';
      button.textContent = `Показать ещё (${remaining})`;
      button.addEventListener('click', () => {
        state.shownNo = noSlice.length + state.pageSize;
        renderLists();
      });
      noElement.appendChild(button);
    }
  }

  /**
   * Загружает данные ознакомлений с API.
   * @param {number} docId - ID документа
   */
  async function fetchAcknowledgements(docId) {
    const url = new URL(apiDetailBase + docId + '/acknowledgements/', window.location.origin);

    try {
      const response = await fetch(url.toString(), { headers });
      
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      const data = await response.json();

      // Поддержка двух форматов:
      // 1) { acknowledged: [...], unacknowledged: [...] }
      // 2) { acknowledged: {results: [...]}, unacknowledged: {results: [...]} }
      const acknowledged = Array.isArray(data.acknowledged) 
        ? data.acknowledged 
        : (data.acknowledged?.results || []);
      
      const unacknowledged = Array.isArray(data.unacknowledged)
        ? data.unacknowledged
        : (data.unacknowledged?.results || []);

      state.rawYes = acknowledged;
      state.rawNo = unacknowledged;
      state.shownYes = state.pageSize;
      state.shownNo = state.pageSize;
      
      renderLists();
    } catch (error) {
      const errorMsg = `Не удалось загрузить: ${esc(error.message)}`;
      yesElement.innerHTML = `<div class="text-danger small">${errorMsg}</div>`;
      noElement.innerHTML = `<div class="text-danger small">${errorMsg}</div>`;
      totalsElement.textContent = '—';
      console.error('fetchAcknowledgements error:', error);
    }
  }

  /**
   * Открывает модальное окно с ознакомлениями.
   * @param {number} docId - ID документа
   * @param {string} title - Название документа
   */
  function openAcknowledgements(docId, title) {
    state.docId = docId;
    state.docTitle = title || '';
    state.filter = '';
    state.shownYes = state.pageSize;
    state.shownNo = state.pageSize;

    if (titleElement) {
      titleElement.textContent = title || '';
    }
    
    searchElement.value = '';
    yesElement.innerHTML = '<div class="text-secondary">Загружается…</div>';
    noElement.innerHTML = '<div class="text-secondary">Загружается…</div>';
    totalsElement.textContent = '—';

    bootstrap.Modal.getOrCreateInstance(modalElement).show();
    fetchAcknowledgements(docId);
  }

  /**
   * Делегированный обработчик кликов по кнопкам "Ознакомления".
   */
  function handleShowAcksClick(e) {
    const button = e.target.closest('button[data-action="show-acks"]');
    if (!button) return;

    const docId = button.getAttribute('data-doc-id');
    const title = button.getAttribute('data-doc-title') || '';
    openAcknowledgements(docId, title);
  }

  /**
   * Обработчик поиска с debounce.
   */
  const handleSearchInput = debounce(() => {
    state.filter = searchElement.value.trim();
    renderLists();
  }, 250);

  // Установка обработчиков
  document.addEventListener('click', handleShowAcksClick);
  searchElement.addEventListener('input', handleSearchInput);

  /**
   * Функция для удаления всех обработчиков.
   */
  function destroy() {
    document.removeEventListener('click', handleShowAcksClick);
    searchElement.removeEventListener('input', handleSearchInput);
  }

  return { destroy };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initDocumentAcks = initDocumentAcks;
}

/**
 * @fileoverview Chat List Filter - фильтрация списка чатов по поисковому запросу и типу
 * Поддержка 3 секций (global, department, private), фильтры по типу, скрытие пустых секций
 * @module components/chatListFilter
 */

import { norm } from '../utils/stringUtils.js';

/**
 * Инициализирует фильтрацию списка чатов
 * @param {Object} options - Опции инициализации
 * @param {string} [options.searchInputId='chatSearch'] - ID поля ввода для поиска
 * @param {string} [options.filterSelector='[data-filter]'] - Селектор кнопок фильтров
 * @param {string} [options.chatRowSelector='.chat-row'] - Селектор элементов чатов
 * @param {Object} [options.sections] - Объект с селекторами секций
 * @returns {Object|null} API фильтра или null если элементы не найдены
 */
export function initChatListFilter(options = {}) {
  const {
    searchInputId = 'chatSearch',
    filterSelector = '[data-filter]',
    chatRowSelector = '.chat-row',
    sections = {
      global: '.chat-section[data-sec="global"]',
      department: '.chat-section[data-sec="department"]',
      private: '.chat-section[data-sec="private"]'
    }
  } = options;

  // Получение элементов
  const search = document.getElementById(searchInputId);
  const labels = document.querySelectorAll(filterSelector);

  if (!search || !labels.length) {
    // Тихо выходим если не на странице чатов
    return null;
  }

  // Получение секций
  const sectionElements = {};
  Object.entries(sections).forEach(([key, selector]) => {
    sectionElements[key] = document.querySelector(selector);
  });

  let activeFilter = 'all';

  /**
   * Применяет текущие фильтры к списку чатов
   */
  function apply() {
    const q = norm(search?.value || '');
    
    // Фильтруем строки чатов
    document.querySelectorAll(chatRowSelector).forEach(el => {
      const type = el.getAttribute('data-type');
      const hay = norm(el.getAttribute('data-haystack'));
      
      const okType = (activeFilter === 'all') || (type === activeFilter);
      const okText = !q || hay.includes(q);
      
      el.style.display = (okType && okText) ? '' : 'none';
    });

    // Управляем видимостью секций
    Object.entries(sectionElements).forEach(([key, wrap]) => {
      if (!wrap) return;
      
      const list = wrap.querySelector('.list-chats');
      const visible = list && list.querySelector(`${chatRowSelector}:not([style*="display: none"])`);
      const note = wrap.querySelector('[data-empty-note]');
      
      wrap.style.display = visible ? '' : 'none';
      if (note) note.style.display = visible ? 'none' : '';
    });
  }

  /**
   * Устанавливает активный фильтр
   * @param {string} filter - Значение фильтра (all, global, department, private)
   */
  function setFilter(filter) {
    activeFilter = filter;
    
    // Обновляем активный класс на кнопках
    labels.forEach(l => {
      const isActive = l.getAttribute('data-filter') === filter;
      l.classList.toggle('active', isActive);
    });
    
    apply();
  }

  /**
   * Обработчик клика по фильтру
   */
  function handleFilterClick(e) {
    const label = e.currentTarget;
    const filter = label.getAttribute('data-filter');
    setFilter(filter);
  }

  /**
   * Обработчик ввода в поле поиска
   */
  function handleSearchInput() {
    apply();
  }

  // Подключаем обработчики
  labels.forEach(l => {
    l.addEventListener('click', handleFilterClick);
  });
  search.addEventListener('input', handleSearchInput);

  // Применяем начальное состояние
  apply();

  // API
  return {
    /**
     * Программная установка фильтра по типу
     * @param {string} filter - Тип фильтра (all, global, department, private)
     */
    setFilter,

    /**
     * Программная установка текста поиска
     * @param {string} query - Поисковый запрос
     */
    setSearch: (query) => {
      search.value = query;
      apply();
    },

    /**
     * Получить текущий активный фильтр
     * @returns {string} Текущий фильтр
     */
    getActiveFilter: () => activeFilter,

    /**
     * Получить текущий поисковый запрос
     * @returns {string} Текст поиска
     */
    getSearchQuery: () => search.value,

    /**
     * Очистка всех фильтров
     */
    clear: () => {
      search.value = '';
      setFilter('all');
    },

    /**
     * Повторно применить текущие фильтры (для обновления после изменений DOM)
     */
    refresh: apply,

    /**
     * Уничтожение обработчиков
     */
    destroy: () => {
      labels.forEach(l => {
        l.removeEventListener('click', handleFilterClick);
      });
      search.removeEventListener('input', handleSearchInput);
    }
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initChatListFilter = initChatListFilter;
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initChatListFilter = initChatListFilter;
}

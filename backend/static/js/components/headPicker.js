/**
 * @fileoverview Head Picker - Autocomplete для выбора руководителя отдела
 * Поддерживает поиск по имени и email, валидацию выбора
 * @module components/headPicker
 */

import { esc, norm } from '../utils/stringUtils.js';

/**
 * Инициализирует компонент выбора руководителя с автодополнением
 * @param {Object} options - Опции инициализации
 * @param {string} [options.selector='[data-head-picker]'] - Селектор контейнера
 * @returns {Object|null} API компонента или null если элемент не найден
 */
export function initHeadPicker(options = {}) {
  const {
    selector = '[data-head-picker]'
  } = options;

  // Защита от повторной инициализации
  if (window.__headPickerWithEmailBound) {
    return null;
  }
  window.__headPickerWithEmailBound = true;

  /**
   * Инициализирует один экземпляр picker
   * @param {HTMLElement} root - Корневой элемент с data-head-picker
   */
  function initPicker(root) {
    const input = root.querySelector('input[type="text"]');
    const hidden = root.querySelector('input[type="hidden"][name="head_id"]');
    const menu = root.querySelector('.dropdown-menu');
    
    if (!input || !hidden || !menu) {
      console.warn('HeadPicker: missing required elements', root);
      return;
    }

    // Парсим данные из data-атрибута
    const choices = (JSON.parse(root.dataset.choices || '[]') || []).map(c => ({
      id: c.id,
      name: c.name || '',
      email: c.email || ''
    }));

    /**
     * Поиск по ID
     */
    function findById(id) {
      return choices.find(c => String(c.id) === String(id));
    }

    /**
     * Точный поиск по имени или email
     */
    function findByExact(text) {
      const t = text.trim();
      const byName = choices.find(c => c.name === t);
      if (byName) return byName;
      const byEmail = choices.find(c => c.email && norm(c.email) === norm(t));
      return byEmail || null;
    }

    // Синхронизация начальных значений
    if (hidden.value && !input.value) {
      const item = findById(hidden.value);
      if (item) input.value = item.name || item.email || '';
    }
    if (input.value && !hidden.value) {
      const m = findByExact(input.value);
      if (m) hidden.value = m.id;
    }

    /**
     * Отображает список выбора
     */
    function listItems(arr) {
      if (!arr.length) {
        menu.innerHTML = '<div class="dropdown-item disabled">Ничего не найдено</div>';
      } else {
        menu.innerHTML = arr.map(c => `
          <button type="button" class="dropdown-item" 
                  data-id="${esc(c.id)}" 
                  data-name="${esc(c.name)}" 
                  data-email="${esc(c.email)}">
            <div class="d-flex flex-column">
              <span>${esc(c.name || c.email || 'Без имени')}</span>
              ${c.email ? `<span class="text-muted small">${esc(c.email)}</span>` : ''}
            </div>
          </button>
        `).join('');
      }
      if (!menu.classList.contains('show')) {
        menu.classList.add('show');
      }
    }

    /**
     * Фильтрует список по запросу
     */
    function filter(q) {
      const s = norm(q);
      const res = s 
        ? choices.filter(c => norm(c.name).includes(s) || norm(c.email).includes(s)).slice(0, 8)
        : choices.slice(0, 8);
      listItems(res);
    }

    /**
     * Скрывает меню
     */
    function hideMenu() {
      menu.classList.remove('show');
    }

    // События input
    input.addEventListener('focus', () => filter(input.value));
    
    input.addEventListener('input', () => {
      hidden.value = '';
      input.classList.remove('is-invalid');
      filter(input.value);
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const first = menu.querySelector('.dropdown-item:not(.disabled)');
        if (menu.classList.contains('show') && first) {
          e.preventDefault();
          first.click();
        }
      } else if (e.key === 'Escape') {
        hideMenu();
      }
    });

    // Выбор элемента из меню
    menu.addEventListener('click', (e) => {
      const btn = e.target.closest('.dropdown-item');
      if (!btn || btn.classList.contains('disabled')) return;

      input.value = btn.dataset.name || btn.dataset.email || '';
      hidden.value = btn.dataset.id || '';
      input.classList.remove('is-invalid');
      hideMenu();
    });

    // Закрытие при клике вне компонента
    document.addEventListener('click', (e) => {
      if (!root.contains(e.target)) hideMenu();
    });

    // Валидация при отправке формы
    const form = root.closest('form');
    form?.addEventListener('submit', (e) => {
      const val = input.value.trim();
      
      // Пустое значение - OK
      if (val === '') {
        hidden.value = '';
        return;
      }
      
      // Если hidden не заполнен, пробуем найти точное совпадение
      if (!hidden.value) {
        const m = findByExact(val);
        if (m) {
          hidden.value = m.id;
          return;
        }
        
        // Не найдено - показываем ошибку
        e.preventDefault();
        input.classList.add('is-invalid');
        filter(val);
        input.focus();
      }
    });
  }

  // Инициализируем все найденные пикеры
  const pickers = document.querySelectorAll(selector);
  pickers.forEach(initPicker);

  return {
    /**
     * Переинициализирует все пикеры (для динамически добавленных элементов)
     */
    refresh: () => {
      window.__headPickerWithEmailBound = false;
      initHeadPicker(options);
    },
    
    /** Количество проинициализированных пикеров */
    count: pickers.length
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initHeadPicker = initHeadPicker;
}

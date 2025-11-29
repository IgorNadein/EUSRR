/**
 * @module recipientPickerHandler
 * @description Виджет для выбора получателей с поиском по API сотрудников.
 * Отображает список сотрудников с чекбоксами, выбранные отображаются как чипы.
 * 
 * Пример HTML:
 * <div class="recipient-picker" data-api-employees="/api/v1/employees/">
 *   <div class="rp-selected" aria-live="polite"></div>
 *   <div class="rp-search">
 *     <input type="search" placeholder="Найти сотрудника">
 *   </div>
 *   <div class="rp-results" role="listbox"></div>
 * </div>
 * 
 * Использование:
 * import { RecipientPicker } from './recipientPickerHandler.js';
 * const picker = new RecipientPicker(element, {
 *   headers: { 'Authorization': 'Bearer TOKEN' },
 *   apiUrl: '/api/v1/employees/'
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
 * Класс для управления выбором получателей.
 */
export class RecipientPicker {
  /**
   * @param {HTMLElement} root - Корневой элемент виджета
   * @param {Object} options - Опции
   * @param {Object} [options.headers={}] - HTTP заголовки для запросов
   * @param {string} options.apiUrl - URL API для получения списка сотрудников
   */
  constructor(root, options) {
    this.root = root;
    this.headers = options.headers || {};
    this.apiUrl = options.apiUrl;
    this.searchQuery = '';
    this.selected = new Map(); // id -> {id, display_name, email}
    this.maxSelections = options.maxSelections || null; // null = без ограничений
    
    // Получаем элементы
    this.elSelected = root.querySelector('.rp-selected');
    this.elSearch = root.querySelector('.rp-search input');
    this.elResults = root.querySelector('.rp-results');
    
    if (!this.elSelected || !this.elSearch || !this.elResults) {
      console.warn('RecipientPicker: обязательные элементы не найдены');
      return;
    }
    
    this._bindEvents();
    this._fetchEmployees();
  }

  /**
   * Привязка обработчиков событий.
   * @private
   */
  _bindEvents() {
    // Поиск с debounce
    this.elSearch.addEventListener('input', debounce(() => {
      this.searchQuery = this.elSearch.value.trim();
      this._fetchEmployees();
    }, 250));

    // Изменение чекбокса в списке
    this.elResults.addEventListener('change', (e) => {
      const checkbox = e.target.closest('input[type=checkbox][data-id]');
      if (!checkbox) return;

      const id = Number(checkbox.dataset.id);
      const payload = JSON.parse(checkbox.dataset.payload || '{}');

      if (checkbox.checked) {
        // Проверка лимита выбора
        if (this.maxSelections && this.selected.size >= this.maxSelections) {
          checkbox.checked = false;
          alert(`Можно выбрать не более ${this.maxSelections} получателей`);
          return;
        }
        this.selected.set(id, payload);
      } else {
        this.selected.delete(id);
      }

      this._renderSelected();
    });

    // Удаление выбранного чипа
    this.elSelected.addEventListener('click', (e) => {
      const button = e.target.closest('button[data-id]');
      if (!button) return;

      const id = Number(button.dataset.id);
      this.selected.delete(id);

      // Снимаем галочку в списке результатов
      const checkbox = this.elResults.querySelector(`input[type=checkbox][data-id="${id}"]`);
      if (checkbox) checkbox.checked = false;

      this._renderSelected();
    });
  }

  /**
   * Загрузка списка сотрудников с API.
   * @private
   */
  async _fetchEmployees() {
    const url = new URL(this.apiUrl, window.location.origin);
    
    if (this.searchQuery) {
      url.searchParams.set('search', this.searchQuery);
    }
    
    url.searchParams.set('ordering', 'last_name,first_name');
    url.searchParams.set('page_size', '20');

    try {
      const response = await fetch(url.toString(), { headers: this.headers });
      
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      const data = await response.json();
      const items = Array.isArray(data) ? data : (data.results || []);
      this._renderResults(items);
    } catch (error) {
      this.elResults.innerHTML = '<div class="rp-empty">Не удалось загрузить сотрудников</div>';
      console.error('RecipientPicker fetch error:', error);
    }
  }

  /**
   * Отображение списка результатов поиска.
   * @private
   * @param {Array} items - Массив объектов сотрудников
   */
  _renderResults(items) {
    if (!items.length) {
      this.elResults.innerHTML = '<div class="rp-empty">Ничего не найдено</div>';
      return;
    }

    this.elResults.innerHTML = items.map(emp => {
      const id = Number(emp.id);
      const name = emp.display_name || emp.full_name || emp.email || ('#' + id);
      const email = emp.email || '';
      const checked = this.selected.has(id) ? 'checked' : '';
      
      const payloadObj = { id, display_name: name, email };
      const payload = esc(JSON.stringify(payloadObj));

      // Аватар или иконка
      const avatar = emp.avatar
        ? `<span class="card-icon"><img src="${esc(emp.avatar)}" class="rp-avatar" alt=""></span>`
        : `<span class="card-icon"><i class="bi-person"></i></span>`;

      return `
        <label class="rp-item">
          ${avatar}
          <div class="flex-grow-1">
            <div>${esc(name)}</div>
            ${email ? `<small>${esc(email)}</small>` : ''}
          </div>
          <input type="checkbox" data-id="${id}" data-payload='${payload}' ${checked} />
        </label>
      `;
    }).join('');
  }

  /**
   * Отображение выбранных получателей как чипов.
   * @private
   */
  _renderSelected() {
    const chips = Array.from(this.selected.values()).map(item => {
      const name = item.display_name || item.email || ('#' + item.id);
      return `
        <span class="rp-chip">
          ${esc(name)}
          <button type="button" title="Убрать" data-id="${item.id}">&times;</button>
        </span>
      `;
    });

    this.elSelected.innerHTML = chips.join('') 
      || '<span class="text-secondary">Никто не выбран</span>';
  }

  /**
   * Установить выбранных получателей массивом объектов.
   * @param {Array<Object>} list - Массив объектов {id, display_name, email}
   */
  setSelected(list) {
    this.selected.clear();
    
    (list || []).forEach(item => {
      if (item && item.id) {
        this.selected.set(Number(item.id), item);
      }
    });

    this._renderSelected();

    // Синхронизируем чекбоксы в текущем списке результатов
    this.elResults.querySelectorAll('input[type=checkbox][data-id]').forEach(checkbox => {
      const id = Number(checkbox.dataset.id);
      checkbox.checked = this.selected.has(id);
    });
  }

  /**
   * Получить массив выбранных ID сотрудников.
   * @returns {Array<number>} Массив ID
   */
  getIds() {
    return Array.from(this.selected.keys());
  }

  /**
   * Получить массив выбранных сотрудников с полными данными.
   * @returns {Array<Object>} Массив объектов {id, display_name, email, ...}
   */
  getSelected() {
    return Array.from(this.selected.values());
  }

  /**
   * Установить максимальное количество выбираемых получателей.
   * @param {number|null} max - Максимум (null = без ограничений)
   */
  setMaxSelections(max) {
    this.maxSelections = max;
    // Если превышен лимит, сбрасываем лишние выборы
    if (max && this.selected.size > max) {
      const toKeep = Array.from(this.selected.entries()).slice(0, max);
      this.selected.clear();
      toKeep.forEach(([id, data]) => this.selected.set(id, data));
      this._renderSelected();
      // Обновляем чекбоксы
      this.elResults.querySelectorAll('input[type=checkbox][data-id]').forEach(checkbox => {
        const id = Number(checkbox.dataset.id);
        checkbox.checked = this.selected.has(id);
      });
    }
  }

  /**
   * Очистить все выборы.
   */
  clear() {
    this.selected.clear();
    this._renderSelected();
    
    this.elResults.querySelectorAll('input[type=checkbox][data-id]').forEach(checkbox => {
      checkbox.checked = false;
    });
  }
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.RecipientPicker = RecipientPicker;
}

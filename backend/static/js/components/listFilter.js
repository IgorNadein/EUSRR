/**
 * ListFilter Component
 * 
 * Универсальный компонент для фильтрации списков с поддержкой поиска
 * Заменяет дублирующиеся функции applyFilter() в различных шаблонах
 * 
 * Использование:
 * import { ListFilter } from '{% static "js/components/listFilter.js" %}';
 * 
 * new ListFilter({
 *   listSelector: '#myList',
 *   itemSelector: '.list-item',
 *   searchInputSelector: '#searchInput',
 *   matchFn: (item, query) => item.textContent.toLowerCase().includes(query)
 * });
 */

import { norm } from '../utils/stringUtils.js';
import { debounce } from '../utils/timing.js';

/**
 * Класс для фильтрации списков
 */
export class ListFilter {
  /**
   * @param {Object} options - Настройки фильтра
   * @param {string} options.listSelector - CSS селектор контейнера списка
   * @param {string} options.itemSelector - CSS селектор элементов списка
   * @param {string} options.searchInputSelector - CSS селектор поля поиска
   * @param {Function} [options.matchFn] - Кастомная функция сопоставления
   * @param {string} [options.clearButtonSelector] - Селектор кнопки очистки
   * @param {string} [options.emptyMessageSelector] - Селектор сообщения "Ничего не найдено"
   * @param {number} [options.debounceMs=300] - Задержка debounce в мс
   * @param {boolean} [options.hideMethod='display'] - Метод скрытия: 'display' или 'class'
   * @param {string} [options.hideClassName='d-none'] - Класс для скрытия (если hideMethod='class')
   * @param {Function} [options.onFilter] - Callback после фильтрации
   */
  constructor(options) {
    this.options = {
      debounceMs: 300,
      hideMethod: 'display',
      hideClassName: 'd-none',
      ...options
    };
    
    // Находим элементы
    this.list = document.querySelector(this.options.listSelector);
    this.searchInput = document.querySelector(this.options.searchInputSelector);
    this.clearButton = this.options.clearButtonSelector 
      ? document.querySelector(this.options.clearButtonSelector)
      : null;
    this.emptyMessage = this.options.emptyMessageSelector
      ? document.querySelector(this.options.emptyMessageSelector)
      : null;
    
    if (!this.list) {
      console.warn(`ListFilter: list not found (${this.options.listSelector})`);
      return;
    }
    
    if (!this.searchInput) {
      console.warn(`ListFilter: search input not found (${this.options.searchInputSelector})`);
      return;
    }
    
    // Используем кастомную функцию сопоставления или дефолтную
    this.matchFn = this.options.matchFn || this.defaultMatch.bind(this);
    
    this.init();
  }
  
  /**
   * Инициализация обработчиков событий
   */
  init() {
    // Debounced фильтрация при вводе
    const debouncedFilter = debounce(() => {
      this.filter(this.searchInput.value);
    }, this.options.debounceMs);
    
    this.searchInput.addEventListener('input', debouncedFilter);
    
    // Кнопка очистки
    if (this.clearButton) {
      this.clearButton.addEventListener('click', () => {
        this.clear();
      });
    }
    
    // Применяем фильтр сразу (если есть значение в поле)
    if (this.searchInput.value) {
      this.filter(this.searchInput.value);
    }
  }
  
  /**
   * Применить фильтр к списку
   * @param {string} query - Поисковый запрос
   */
  filter(query) {
    const items = this.getItems();
    const normalizedQuery = norm(query);
    let visibleCount = 0;
    
    items.forEach(item => {
      const isMatch = this.matchFn(item, normalizedQuery, query);
      this.setItemVisibility(item, isMatch);
      
      if (isMatch) {
        visibleCount++;
      }
    });
    
    // Обновляем сообщение о пустом результате
    this.updateEmptyState(visibleCount);
    
    // Вызываем callback если указан
    if (this.options.onFilter) {
      this.options.onFilter(visibleCount, query);
    }
  }
  
  /**
   * Получить все элементы списка
   * @returns {NodeList} - Список элементов
   */
  getItems() {
    return this.list.querySelectorAll(this.options.itemSelector);
  }
  
  /**
   * Установить видимость элемента
   * @param {HTMLElement} item - Элемент
   * @param {boolean} visible - Видимость
   */
  setItemVisibility(item, visible) {
    if (this.options.hideMethod === 'class') {
      item.classList.toggle(this.options.hideClassName, !visible);
    } else {
      item.style.display = visible ? '' : 'none';
    }
  }
  
  /**
   * Дефолтная функция сопоставления
   * Ищет в текстовом содержимом элемента
   * @param {HTMLElement} item - Элемент списка
   * @param {string} normalizedQuery - Нормализованный запрос
   * @returns {boolean} - Совпадение
   */
  defaultMatch(item, normalizedQuery) {
    if (!normalizedQuery) return true;
    const text = norm(item.textContent);
    return text.includes(normalizedQuery);
  }
  
  /**
   * Обновить состояние сообщения "Ничего не найдено"
   * @param {number} visibleCount - Количество видимых элементов
   */
  updateEmptyState(visibleCount) {
    if (!this.emptyMessage) return;
    
    const isEmpty = visibleCount === 0 && this.searchInput.value.trim() !== '';
    this.emptyMessage.style.display = isEmpty ? '' : 'none';
  }
  
  /**
   * Очистить поле поиска и показать все элементы
   */
  clear() {
    this.searchInput.value = '';
    this.searchInput.focus();
    this.filter('');
  }
  
  /**
   * Обновить список элементов (после динамического добавления/удаления)
   */
  refresh() {
    this.filter(this.searchInput.value);
  }
  
  /**
   * Уничтожить фильтр (удалить обработчики)
   */
  destroy() {
    // Удаляем обработчики событий
    // (В реальном приложении нужно хранить ссылки на функции)
    console.warn('ListFilter.destroy() - not fully implemented');
  }
}

/**
 * Вспомогательная функция для быстрого создания фильтра
 * с сопоставлением по data-атрибутам
 * 
 * @param {Object} options - Настройки
 * @param {string[]} options.dataAttrs - Массив data-атрибутов для поиска
 * @returns {Function} - Функция сопоставления
 * 
 * @example
 * new ListFilter({
 *   listSelector: '#list',
 *   itemSelector: '.item',
 *   searchInputSelector: '#search',
 *   matchFn: createDataAttrMatcher(['name', 'email', 'id'])
 * });
 */
export function createDataAttrMatcher(dataAttrs) {
  return (item, normalizedQuery) => {
    if (!normalizedQuery) return true;
    
    const values = dataAttrs
      .map(attr => item.dataset[attr] || '')
      .join(' ');
    
    return norm(values).includes(normalizedQuery);
  };
}

/**
 * Вспомогательная функция для создания фильтра
 * с сопоставлением по селекторам внутри элемента
 * 
 * @param {string[]} selectors - Массив CSS селекторов
 * @returns {Function} - Функция сопоставления
 * 
 * @example
 * new ListFilter({
 *   listSelector: '#list',
 *   itemSelector: '.item',
 *   searchInputSelector: '#search',
 *   matchFn: createSelectorMatcher(['.name', '.email', '.department'])
 * });
 */
export function createSelectorMatcher(selectors) {
  return (item, normalizedQuery) => {
    if (!normalizedQuery) return true;
    
    const values = selectors
      .map(sel => {
        const el = item.querySelector(sel);
        return el ? el.textContent : '';
      })
      .join(' ');
    
    return norm(values).includes(normalizedQuery);
  };
}

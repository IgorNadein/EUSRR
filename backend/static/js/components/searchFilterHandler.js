/**
 * @module searchFilterHandler
 * @description Универсальный обработчик для iOS-поиска с фильтрацией результатов.
 * Поддерживает:
 * - Текстовый поиск по data-haystack атрибуту
 * - Фильтрацию по типам через радио-кнопки
 * - Кнопку очистки поиска
 * - Подсчет видимых результатов
 * 
 * HTML структура:
 * <input id="searchInput">
 * <button class="ios-search-clear">
 * <div class="section" data-sec="type1">
 *   <div class="result-row" data-type="type1" data-haystack="search text">
 * </div>
 * 
 * Использование:
 * import { initSearchFilter } from './searchFilterHandler.js';
 * initSearchFilter({
 *   inputId: 'globalSearch',
 *   clearSelector: '.ios-search-clear',
 *   filterRadioName: 'srchFilter'
 * });
 */

/**
 * Нормализует строку для поиска (lowercase, trim).
 * @param {*} value - Значение для нормализации
 * @returns {string} Нормализованная строка
 */
function normalize(value) {
  return (value || '').toString().toLowerCase().trim();
}

/**
 * Инициализирует обработчик поиска и фильтрации.
 * @param {Object} options - Опции инициализации
 * @param {string} options.inputId - ID поля поиска
 * @param {string} [options.clearSelector='.ios-search-clear'] - Селектор кнопки очистки
 * @param {string} [options.filterRadioName] - Name радио-кнопок фильтра (если есть)
 * @param {string} [options.sectionSelector='.section'] - Селектор секций результатов
 * @param {string} [options.rowSelector='.result-row, .chat-row, .dept-row'] - Селектор строк результатов
 * @param {Function} [options.onUpdate] - Callback после обновления фильтров (params: {visible, total})
 * @returns {Object} API с методом destroy
 */
export function initSearchFilter(options) {
  const {
    inputId,
    clearSelector = '.ios-search-clear',
    filterRadioName,
    sectionSelector = '.section, .chat-section',
    rowSelector = '.result-row, .chat-row, .dept-row',
    onUpdate
  } = options;

  const input = document.getElementById(inputId);
  const clearBtn = document.querySelector(clearSelector);
  const sections = document.querySelectorAll(sectionSelector);
  
  if (!input) {
    console.warn('initSearchFilter: поле поиска не найдено', inputId);
    return { destroy: () => {} };
  }

  // Радио-кнопки фильтров (опционально)
  const radios = filterRadioName ? document.querySelectorAll(`input[name="${filterRadioName}"]`) : [];
  const filterLabels = filterRadioName ? document.querySelectorAll(`input[name="${filterRadioName}"] + label[data-filter]`) : [];

  /**
   * Применяет текущие фильтры к результатам.
   */
  function applyFilter() {
    const searchText = normalize(input.value);
    
    // Определяем активный фильтр типа
    let activeType = 'all';
    if (filterRadioName) {
      const checkedRadio = document.querySelector(`input[name="${filterRadioName}"]:checked + label[data-filter]`);
      activeType = checkedRadio ? checkedRadio.dataset.filter : 'all';
    }

    let totalVisible = 0;
    let totalRows = 0;

    sections.forEach(section => {
      const sectionType = section.dataset.sec;
      const typeMatches = (activeType === 'all' || activeType === sectionType);
      
      if (!typeMatches) {
        section.style.display = 'none';
        return;
      }

      const rows = section.querySelectorAll(rowSelector);
      let visibleInSection = 0;

      rows.forEach(row => {
        totalRows++;
        const haystack = normalize(row.dataset.haystack || '');
        const textMatches = (searchText === '' || haystack.includes(searchText));

        if (textMatches) {
          row.style.removeProperty('display');
          if (!row.classList.contains('d-flex')) {
            row.classList.add('d-flex');
          }
          visibleInSection++;
          totalVisible++;
        } else {
          row.classList.remove('d-flex');
          row.style.setProperty('display', 'none', 'important');
        }
      });

      // Показываем секцию только если есть видимые строки или пустой поиск
      section.style.display = (searchText === '' || visibleInSection > 0) ? '' : 'none';

      // Обновляем заметку "нет результатов" внутри секции
      const emptyNote = section.querySelector('[data-empty-note]');
      if (emptyNote) {
        emptyNote.style.display = (visibleInSection === 0 && rows.length > 0) ? '' : 'none';
      }
    });

    // Вызываем callback с результатами
    if (onUpdate) {
      onUpdate({ visible: totalVisible, total: totalRows, searchText, activeType });
    }
  }

  /**
   * Обработчик клика по кнопке очистки.
   */
  function handleClearClick() {
    input.value = '';
    input.focus();
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  /**
   * Обработчик смены радио-фильтра (с задержкой для анимации).
   */
  function handleFilterChange() {
    setTimeout(applyFilter, 0);
  }

  // Установка обработчиков
  input.addEventListener('input', applyFilter);
  clearBtn?.addEventListener('click', handleClearClick);
  
  radios.forEach(radio => {
    radio.addEventListener('change', handleFilterChange);
  });
  
  filterLabels.forEach(label => {
    label.addEventListener('click', handleFilterChange);
  });

  // Первичная инициализация
  applyFilter();

  /**
   * Удаление обработчиков.
   */
  function destroy() {
    input.removeEventListener('input', applyFilter);
    clearBtn?.removeEventListener('click', handleClearClick);
    
    radios.forEach(radio => {
      radio.removeEventListener('change', handleFilterChange);
    });
    
    filterLabels.forEach(label => {
      label.removeEventListener('click', handleFilterChange);
    });
  }

  return { destroy, reapply: applyFilter };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initSearchFilter = initSearchFilter;
}

/**
 * @module departmentFilterHandler
 * @description Обработчик фильтрации списка отделов с подсчетом сотрудников.
 * Поддерживает:
 * - Текстовый поиск по названию отдела и руководителю
 * - Подсчет общего количества сотрудников в видимых отделах
 * - Обновление счетчика отделов
 * - Сообщение "нет результатов"
 * 
 * HTML структура:
 * <input id="deptFilter">
 * <div id="deptList">
 *   <div class="dept-row" data-haystack="название рук" data-emp="5">
 * </div>
 * <span id="empTotal">0</span>
 * 
 * Использование:
 * import { initDepartmentFilter } from './departmentFilterHandler.js';
 * initDepartmentFilter({
 *   inputId: 'deptFilter',
 *   listId: 'deptList',
 *   totalEmpId: 'empTotal'
 * });
 */

/**
 * Нормализует строку для поиска.
 * @param {*} value - Значение для нормализации
 * @returns {string} Нормализованная строка
 */
function normalize(value) {
  return (value || '').toLowerCase().trim();
}

/**
 * Показывает строку отдела.
 * @param {HTMLElement} row - Элемент строки
 */
function showRow(row) {
  row.style.removeProperty('display');
  if (!row.classList.contains('d-flex')) {
    row.classList.add('d-flex');
  }
}

/**
 * Скрывает строку отдела.
 * @param {HTMLElement} row - Элемент строки
 */
function hideRow(row) {
  row.classList.remove('d-flex');
  row.style.setProperty('display', 'none', 'important');
}

/**
 * Инициализирует обработчик фильтрации отделов.
 * @param {Object} options - Опции инициализации
 * @param {string} options.inputId - ID поля поиска
 * @param {string} [options.clearSelector='.ios-search-clear'] - Селектор кнопки очистки
 * @param {string} options.listId - ID контейнера списка отделов
 * @param {string} [options.totalEmpId='empTotal'] - ID элемента счетчика сотрудников
 * @param {string} [options.totalDeptSelector='.title ~ .ms-2.small'] - Селектор счетчика отделов
 * @param {string} [options.emptyNoticeId='deptEmptyNotice'] - ID сообщения "нет результатов"
 * @param {string} [options.rowSelector='.dept-row'] - Селектор строк отделов
 * @returns {Object} API с методом destroy
 */
export function initDepartmentFilter(options) {
  const {
    inputId,
    clearSelector = '.ios-search-clear',
    listId,
    totalEmpId = 'empTotal',
    totalDeptSelector = '.title ~ .ms-2.small',
    emptyNoticeId = 'deptEmptyNotice',
    rowSelector = '.dept-row'
  } = options;

  const input = document.getElementById(inputId);
  const clearBtn = document.querySelector(clearSelector);
  const list = document.getElementById(listId);
  const totalEmpEl = document.getElementById(totalEmpId);
  const totalDeptBadge = document.querySelector(totalDeptSelector);

  if (!input || !list) {
    console.warn('initDepartmentFilter: обязательные элементы не найдены');
    return { destroy: () => {} };
  }

  const allRows = Array.from(list.querySelectorAll(rowSelector));

  // Создание сообщения "нет результатов" если отсутствует
  let emptyNotice = document.getElementById(emptyNoticeId);
  if (!emptyNotice) {
    emptyNotice = document.createElement('div');
    emptyNotice.id = emptyNoticeId;
    emptyNotice.className = 'p-3 text-secondary d-none';
    emptyNotice.textContent = 'Ничего не найдено.';
    list.appendChild(emptyNotice);
  }

  /**
   * Применяет фильтр к списку отделов.
   */
  function applyFilter() {
    const query = normalize(input.value);
    let totalEmp = 0;
    let shownCount = 0;

    for (const row of allRows) {
      const haystack = normalize(row.getAttribute('data-haystack'));
      const matches = !query || haystack.includes(query);

      if (matches) {
        showRow(row);
        shownCount++;
        totalEmp += (parseInt(row.getAttribute('data-emp')) || 0);
      } else {
        hideRow(row);
      }
    }

    // Обновление сообщения "нет результатов"
    emptyNotice.classList.toggle('d-none', shownCount > 0);

    // Обновление счетчиков
    if (totalEmpEl) {
      totalEmpEl.textContent = String(totalEmp);
    }
    
    if (totalDeptBadge) {
      totalDeptBadge.textContent = `Всего: ${shownCount}`;
    }
  }

  /**
   * Обработчик клика по кнопке очистки.
   */
  function handleClearClick() {
    input.value = '';
    input.focus();
    applyFilter();
  }

  // Установка обработчиков
  input.addEventListener('input', applyFilter);
  clearBtn?.addEventListener('click', handleClearClick);

  // Первичная инициализация
  applyFilter();

  /**
   * Удаление обработчиков.
   */
  function destroy() {
    input.removeEventListener('input', applyFilter);
    clearBtn?.removeEventListener('click', handleClearClick);
  }

  return { destroy, reapply: applyFilter };
}

// Экспорт для совместимости с неModular кодом
if (typeof window !== 'undefined') {
  window.initDepartmentFilter = initDepartmentFilter;
}

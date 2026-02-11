/**
 * @fileoverview Calendar Manager Component - управление списком календарей
 * @module components/calendarManager
 */

import {
  getMyCalendars,
  subscribeToCalendar,
  unsubscribeFromCalendar,
  invalidateCalendarsCache
} from '../api/calendarsApi.js';

/**
 * Инициализация менеджера календарей
 * @param {Object} options - Параметры
 * @param {string} options.containerId - ID контейнера для списка календарей
 * @param {Function} options.onCalendarToggle - Callback при переключении видимости календаря
 * @param {Function} options.onCalendarsChange - Callback при изменении списка календарей
 * @returns {Object} API менеджера
 */
export function initCalendarManager(options = {}) {
  const {
    containerId = 'calendarListContainer',
    onCalendarToggle = () => {},
    onCalendarsChange = () => {}
  } = options;

  const container = document.getElementById(containerId);
  if (!container) {
    console.warn(`[CalendarManager] Container #${containerId} not found`);
    return null;
  }

  // Состояние
  let calendars = [];
  let visibleCalendarIds = new Set();

  /**
   * Загрузить список календарей
   */
  async function loadCalendars() {
    try {
      calendars = await getMyCalendars();
      
      // По умолчанию все календари видимы
      visibleCalendarIds = new Set(calendars.map(cal => cal.id));
      
      render();
      onCalendarsChange(calendars, Array.from(visibleCalendarIds));
    } catch (error) {
      console.error('[CalendarManager] Failed to load calendars:', error);
      container.innerHTML = `
        <div class="alert alert-danger alert-sm">
          <i class="bi-exclamation-triangle me-2"></i>
          Не удалось загрузить календари
        </div>
      `;
    }
  }

  /**
   * Переключить видимость календаря
   * @param {number} calendarId
   */
  function toggleCalendarVisibility(calendarId) {
    if (visibleCalendarIds.has(calendarId)) {
      visibleCalendarIds.delete(calendarId);
    } else {
      visibleCalendarIds.add(calendarId);
    }
    
    render();
    onCalendarToggle(calendarId, visibleCalendarIds.has(calendarId));
  }

  /**
   * Подписаться на календарь
   * @param {number} calendarId
   */
  async function subscribe(calendarId) {
    try {
      await subscribeToCalendar(calendarId);
      await loadCalendars(); // Перезагрузить список
    } catch (error) {
      console.error('[CalendarManager] Subscribe failed:', error);
      alert('Не удалось подписаться на календарь');
    }
  }

  /**
   * Отписаться от календаря
   * @param {number} calendarId
   */
  async function unsubscribe(calendarId) {
    if (!confirm('Отписаться от этого календаря?')) return;
    
    try {
      await unsubscribeFromCalendar(calendarId);
      await loadCalendars(); // Перезагрузить список
    } catch (error) {
      console.error('[CalendarManager] Unsubscribe failed:', error);
      alert('Не удалось отписаться от календаря');
    }
  }

  /**
   * Получить иконку для типа календаря
   * @param {Object} calendar
   * @returns {string} HTML иконки
   */
  function getCalendarIcon(calendar) {
    if (calendar.is_personal) {
      return '<i class="bi-person-fill"></i>';
    } else if (calendar.is_department) {
      return '<i class="bi-building"></i>';
    } else if (calendar.is_global) {
      return '<i class="bi-globe"></i>';
    }
    return '<i class="bi-calendar3"></i>';
  }

  /**
   * Получить бейдж владельца
   * @param {Object} calendar
   * @returns {string} HTML бейджа
   */
  function getOwnerBadge(calendar) {
    if (calendar.is_personal && calendar.owner_user_name) {
      return `<span class="badge bg-secondary-subtle text-secondary-emphasis rounded-pill ms-auto">${calendar.owner_user_name}</span>`;
    } else if (calendar.is_department && calendar.owner_department_name) {
      return `<span class="badge bg-info-subtle text-info-emphasis rounded-pill ms-auto">${calendar.owner_department_name}</span>`;
    } else if (calendar.is_global) {
      return `<span class="badge bg-primary-subtle text-primary-emphasis rounded-pill ms-auto">Общий</span>`;
    }
    return '';
  }

  /**
   * Рендер списка календарей
   */
  function render() {
    if (calendars.length === 0) {
      container.innerHTML = `
        <div class="text-muted text-center py-3">
          <i class="bi-calendar3 fs-4 d-block mb-2"></i>
          <small>Нет доступных календарей</small>
        </div>
      `;
      return;
    }

    const html = calendars.map(calendar => {
      const isVisible = visibleCalendarIds.has(calendar.id);
      const canEdit = calendar.user_can_edit;
      const isSubscribed = calendar.is_subscribed;
      
      return `
        <div class="calendar-list-item" data-calendar-id="${calendar.id}">
          <div class="form-check">
            <input 
              class="form-check-input calendar-visibility-toggle" 
              type="checkbox" 
              id="cal_${calendar.id}"
              ${isVisible ? 'checked' : ''}
              data-calendar-id="${calendar.id}"
            >
            <label class="form-check-label d-flex align-items-center gap-2 w-100" for="cal_${calendar.id}">
              <span class="calendar-color-indicator" style="background-color: ${calendar.color}"></span>
              <span class="calendar-icon text-muted">${getCalendarIcon(calendar)}</span>
              <span class="calendar-title flex-grow-1">${calendar.title}</span>
              ${getOwnerBadge(calendar)}
            </label>
          </div>
          
          <div class="calendar-list-item-actions">
            ${canEdit ? `
              <button 
                class="btn btn-sm btn-outline-secondary calendar-edit-btn" 
                data-calendar-id="${calendar.id}"
                title="Редактировать"
              >
                <i class="bi-pencil"></i>
              </button>
            ` : ''}
            
            ${!isSubscribed ? `
              <button 
                class="btn btn-sm btn-outline-primary calendar-subscribe-btn" 
                data-calendar-id="${calendar.id}"
                title="Подписаться"
              >
                <i class="bi-plus-lg"></i>
              </button>
            ` : `
              <button 
                class="btn btn-sm btn-outline-danger calendar-unsubscribe-btn" 
                data-calendar-id="${calendar.id}"
                title="Отписаться"
              >
                <i class="bi-dash-lg"></i>
              </button>
            `}
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = html;
    attachEventListeners();
  }

  /**
   * Прикрепить обработчики событий
   */
  function attachEventListeners() {
    // Переключение видимости
    container.querySelectorAll('.calendar-visibility-toggle').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        const calendarId = parseInt(e.target.dataset.calendarId);
        toggleCalendarVisibility(calendarId);
      });
    });

    // Подписка
    container.querySelectorAll('.calendar-subscribe-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const calendarId = parseInt(e.currentTarget.dataset.calendarId);
        subscribe(calendarId);
      });
    });

    // Отписка
    container.querySelectorAll('.calendar-unsubscribe-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const calendarId = parseInt(e.currentTarget.dataset.calendarId);
        unsubscribe(calendarId);
      });
    });

    // Редактирование (делегируем наверх)
    container.querySelectorAll('.calendar-edit-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const calendarId = parseInt(e.currentTarget.dataset.calendarId);
        const calendar = calendars.find(c => c.id === calendarId);
        if (calendar) {
          // Dispatch custom event для открытия модального окна
          document.dispatchEvent(new CustomEvent('calendar:edit', { detail: calendar }));
        }
      });
    });
  }

  /**
   * Обновить список календарей
   */
  async function refresh() {
    invalidateCalendarsCache();
    await loadCalendars();
  }

  /**
   * Получить ID видимых календарей
   * @returns {Array<number>}
   */
  function getVisibleCalendarIds() {
    return Array.from(visibleCalendarIds);
  }

  /**
   * Установить видимость календарей
   * @param {Array<number>} calendarIds
   */
  function setVisibleCalendars(calendarIds) {
    visibleCalendarIds = new Set(calendarIds);
    render();
    onCalendarsChange(calendars, Array.from(visibleCalendarIds));
  }

  // Инициализация
  loadCalendars();

  // Public API
  return {
    refresh,
    getVisibleCalendarIds,
    setVisibleCalendars,
    loadCalendars
  };
}

/**
 * Модуль для загрузки и отображения новых сотрудников
 * Использует API для получения данных с корректными глобальными URL
 */

export class NewEmployeesScroller {
  constructor(containerId = 'newEmployeesContainer') {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.warn(`Container #${containerId} not found`);
      return;
    }
    this.apiUrl = '/api/v1/employees/';
  }

  /**
   * Инициализация - загрузка и рендеринг
   */
  async init() {
    try {
      const employees = await this.fetchNewEmployees();
      if (employees && employees.length > 0) {
        this.render(employees);
      } else {
        this.container.style.display = 'none';
      }
    } catch (error) {
      console.error('Failed to load new employees:', error);
      this.container.style.display = 'none';
    }
  }

  /**
   * Загрузка новых сотрудников через API
   */
  async fetchNewEmployees() {
    // Дата 14 дней назад
    const since = new Date();
    since.setDate(since.getDate() - 14);
    const sinceISO = since.toISOString();

    const params = new URLSearchParams({
      active: 'true',
      created_at__gte: sinceISO,
      ordering: '-created_at',
      page_size: '10'
    });

    const response = await fetch(`${this.apiUrl}?${params}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.results || data;
  }

  /**
   * Рендеринг списка сотрудников
   */
  render(employees) {
    const scrollerHtml = this.createScrollerHtml(employees);
    this.container.innerHTML = scrollerHtml;
    this.container.style.display = 'block';
    
    // Инициализируем автоскролл после рендеринга
    this.initAutoScroll();
  }

  /**
   * Инициализация автоскролла для созданного скроллера
   */
  async initAutoScroll() {
    try {
      // Динамический импорт модуля автоскролла
      // Добавляем timestamp для обхода кеша браузера
      const timestamp = Date.now();
      const { initAutoScroller } = await import(`/static/js/components/autoScrollerHandler.js?v=${timestamp}`);
      
      // Небольшая задержка для гарантии, что DOM обновился
      setTimeout(() => {
        initAutoScroller({
          selector: '.js-join-scroller',
          speed: 0.5
        });
      }, 100);
    } catch (error) {
      console.warn('Failed to initialize auto-scroller:', error);
    }
  }

  /**
   * Создание HTML разметки скроллера
   */
  createScrollerHtml(employees) {
    const items = employees.map(emp => this.createEmployeeItem(emp)).join('');
    
    return `
      <div>
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 text-secondary"></h6>
        </div>

        <div class="join-scroller js-join-scroller" aria-label="Новые сотрудники">
          <div class="join-rail">
            ${items}
          </div>
        </div>
        
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 text-secondary"></h6>
        </div>
      </div>
    `;
  }

  /**
   * Создание элемента сотрудника
   */
  createEmployeeItem(emp) {
    const empId = emp.id || emp.pk;
    const empName = emp.short_name || emp.full_name || emp.email || 'Сотрудник';
    const deptName = emp.department?.name || emp.department_name || '';
    const avatar = emp.avatar;
    
    // Аватар или иконка
    let avatarHtml;
    if (avatar) {
      avatarHtml = `<img src="${avatar}" alt="" loading="lazy">`;
    } else {
      avatarHtml = `
        <i class="bi-person" aria-hidden="true"></i>
        <span class="visually-hidden">${this.escapeHtml(empName)}</span>
      `;
    }

    // Навыки
    let skillsHtml = '';
    if (emp.skills && emp.skills.length > 0) {
      const skillsList = emp.skills.map(s => this.escapeHtml(s.name)).join(', ');
      skillsHtml = `<div class="skills-line"><b>Навыки:</b> ${skillsList}</div>`;
    }

    return `
      <div class="join-item">
        <a href="/employees/${empId}/"
           class="join-ava text-decoration-none"
           title="${this.escapeHtml(empName)}">
          ${avatarHtml}
        </a>

        <div class="join-info">
          <div class="name">${this.escapeHtml(empName)}</div>
          ${deptName ? `<div class="sub">${this.escapeHtml(deptName)}</div>` : ''}
          ${skillsHtml}
        </div>
      </div>
    `;
  }

  /**
   * Экранирование HTML
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

/**
 * Инициализация при загрузке DOM
 */
export function initNewEmployeesScroller(containerId) {
  const scroller = new NewEmployeesScroller(containerId);
  scroller.init();
  return scroller;
}

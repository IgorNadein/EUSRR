/**
 * Модуль для загрузки и отображения списка сотрудников
 * Использует API для получения данных с корректными глобальными URL
 */

export class EmployeesList {
  constructor(options = {}) {
    this.containerId = options.containerId || 'empList';
    this.container = document.getElementById(this.containerId);
    if (!this.container) {
      console.warn(`Container #${this.containerId} not found`);
      return;
    }
    
    this.apiUrl = '/api/v1/employees/';
    this.employees = [];
    this.loading = false;
    
    // Параметры из URL
    const urlParams = new URLSearchParams(window.location.search);
    this.params = {
      page: urlParams.get('page') || 1,
      ordering: urlParams.get('o') || 'last_name',
      search: urlParams.get('q') || '',
      department: urlParams.get('department') || '',
      position: urlParams.get('position') || '',
      is_active: urlParams.get('is_active') || ''
    };
  }

  /**
   * Инициализация - загрузка и рендеринг
   */
  async init() {
    if (!this.container) return;
    
    try {
      await this.loadEmployees();
      this.render();
    } catch (error) {
      console.error('Failed to load employees:', error);
      this.renderError();
    }
  }

  /**
   * Загрузка сотрудников через API
   */
  async loadEmployees() {
    if (this.loading) return;
    this.loading = true;

    const params = new URLSearchParams();
    Object.entries(this.params).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });

    const response = await fetch(`${this.apiUrl}?${params}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    this.employees = data.results || data;
    this.loading = false;
  }

  /**
   * Рендеринг списка сотрудников
   */
  render() {
    if (this.employees.length === 0) {
      this.container.innerHTML = '<div class="alert alert-info shadow-sm">Нет сотрудников.</div>';
      return;
    }

    const itemsHtml = this.employees.map(emp => this.createEmployeeCard(emp)).join('');
    this.container.innerHTML = itemsHtml;
  }

  /**
   * Создание карточки сотрудника
   */
  createEmployeeCard(emp) {
    const fullName = this.getFullName(emp);
    const position = this.getPosition(emp);
    const departments = this.getDepartments(emp);
    const avatar = this.getAvatarHtml(emp);
    
    return `
      <article class="emp-row list-row"
               data-name="${this.escapeHtml(fullName + ' ' + position)}"
               data-depts="${this.escapeHtml(departments)}">
        <header class="card-header">
          <div class="card-icon">
            ${avatar}
          </div>

          <div class="card-meta flex-grow-1">
            <div class="d-flex align-items-center gap-2 flex-wrap">
              ${emp.id ? 
                `<a href="/employees/${emp.id}/" class="card-title text-decoration-none">${this.escapeHtml(fullName)}</a>` :
                `<span class="card-title">${this.escapeHtml(fullName)}</span>`
              }
              ${position ? `<span class="emp-pos">— ${this.escapeHtml(position)}</span>` : ''}
            </div>
            ${departments ? `<div class="card-subtitle">${departments}</div>` : ''}
          </div>

          <div class="ms-auto d-flex align-items-center gap-2">
            ${this.getActionButtons(emp)}
          </div>
        </header>

        <div class="card-body"></div>
      </article>
    `;
  }

  /**
   * Получение полного имени
   */
  getFullName(emp) {
    let name = `${emp.last_name || ''} ${emp.first_name || ''}`.trim();
    if (emp.patronymic) {
      name += ` ${emp.patronymic}`;
    }
    return name || 'Сотрудник';
  }

  /**
   * Получение должности
   */
  getPosition(emp) {
    if (emp.position?.name) {
      return emp.position.name;
    } else if (emp.position_label) {
      return emp.position_label;
    } else if (emp.position) {
      return `Должность #${emp.position}`;
    }
    return '';
  }

  /**
   * Получение отделов
   */
  getDepartments(emp) {
    if (!emp.departments || emp.departments.length === 0) {
      return '';
    }
    
    return emp.departments
      .filter(d => d.name)
      .map(d => {
        if (d.id) {
          return `<a href="/employees/departments/${d.id}/">${this.escapeHtml(d.name)}</a>`;
        }
        return this.escapeHtml(d.name);
      })
      .join(', ');
  }

  /**
   * Получение HTML аватара
   */
  getAvatarHtml(emp) {
    if (emp.avatar) {
      return `<img src="${emp.avatar}" alt="${this.escapeHtml(this.getFullName(emp))}">`;
    } else {
      return '<i class="bi-person"></i>';
    }
  }

  /**
   * Получение кнопок действий
   */
  getActionButtons(emp) {
    if (!emp.id) return '';
    
    // Получаем ID текущего пользователя из глобальной переменной или data-атрибута
    const currentUserId = window.currentUserId || document.body.dataset.userId;
    if (currentUserId && String(currentUserId) === String(emp.id)) {
      return ''; // Не показываем кнопки для себя
    }

    return `
      <a href="/communications/chats/private/${emp.id}/"
         class="btn btn-ghost action-btn" title="Чат">
        <i class="bi-chat-dots"></i><span class="d-none d-sm-inline ms-1">Чат</span>
      </a>
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

  /**
   * Рендеринг ошибки
   */
  renderError() {
    this.container.innerHTML = `
      <div class="alert alert-danger shadow-sm">
        Не удалось загрузить список сотрудников. Попробуйте обновить страницу.
      </div>
    `;
  }
}

/**
 * Инициализация списка сотрудников
 */
export function initEmployeesList(options) {
  const list = new EmployeesList(options);
  list.init();
  return list;
}
